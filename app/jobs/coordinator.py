"""Coordinator pipeline: orchestrates the multi-agent application workflow."""
import uuid
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.drafter import run_drafter
from app.agents.edge_finder import run_edge_finder
from app.agents.researcher import run_researcher
from app.api.v1.matches import evaluate_eligibility_and_fit
from app.core.logging import logger
from app.core.tracing import workflow_span, application_context, trace_block, trace_identifier
from app.core.config import settings
from app.agents.planner import run_application_agent
from app.core.runtime import is_demo_portal
from app.integrations.portal_adapters import handoff_real_portal
from app.db.models import Application, Job, Profile, Scholarship, User, Draft, ApplicationEvent
from app.jobs.queue import enqueue_job, register_job_handler
from app.jobs.state_machine import transition_application


@workflow_span("coordinator_pipeline")
async def run_coordinator_pipeline(
    application_id: uuid.UUID,
    session: AsyncSession,
    live_research: bool | None = None,
) -> Dict[str, Any]:
    """Orchestrates an application through matching, research, edge-finding, drafting, and submission."""
    logger.info(f"Coordinator pipeline started for application {application_id}")

    app_record = await session.get(Application, application_id)
    if not app_record:
        raise ValueError(f"Application {application_id} not found.")

    user = await session.get(User, app_record.user_id)
    scholarship = await session.get(Scholarship, app_record.scholarship_id)
    if not scholarship:
        raise ValueError(f"Scholarship {app_record.scholarship_id} not found.")

    profile_stmt = select(Profile).where(Profile.user_id == app_record.user_id)
    profile = (await session.execute(profile_stmt)).scalar_one_or_none()

    # Stage 1: discovered -> matched
    if app_record.status == "discovered":
        eval_res = evaluate_eligibility_and_fit(profile, scholarship) if profile else None
        if eval_res is None:
            await transition_application(
                app_record, "withdrawn", "coordinator",
                {"reason": "Profile missing or scholarship eligibility criteria not met."}, session,
            )
            return {"application_id": str(app_record.id), "status": "withdrawn"}
        fit_score = eval_res[0]

        app_record = await transition_application(
            application=app_record,
            new_status="matched",
            actor="coordinator",
            payload={"fit_score": fit_score},
            session=session,
        )

    if settings.AGENT_ENABLED and settings.LLM_DRAFTING and (scholarship.eligibility_rules or {}).get("ai_policy") in {"allowed", "disclose"} and app_record.status in {"matched", "researching", "drafting"}:
        if settings.NEATLOGS_CAPTURE_CONTENT:
            fictional_email = json.loads(Path("backend/data/synthetic/preferences.json").read_text(encoding="utf-8"))["email"]
            if not user or user.email != fictional_email:
                raise ValueError("Full prompt capture is restricted to the repository's fictional demo identity.")
        if app_record.status == "matched":
            await transition_application(app_record, "researching", "coordinator", {"agent": True}, session)
        with application_context(str(app_record.id), str(scholarship.id), app_record.mode_used):
            with trace_block("application_agent", "AGENT") as span:
                identifier = trace_identifier(span)
                if identifier:
                    session.add(ApplicationEvent(application_id=app_record.id, actor="coordinator", event_type="neatlogs_trace",
                        payload={"trace_id": identifier, "export_enabled": True}))
                    await session.commit()
                return await run_application_agent(app_record, scholarship, session, live_research)

    # Stage 2: matched -> researching
    research_facts: List[Dict[str, Any]] = []
    if app_record.status == "matched":
        app_record = await transition_application(
            application=app_record,
            new_status="researching",
            actor="coordinator",
            payload={"scholarship_title": scholarship.title},
            session=session,
        )

        research_res = await run_researcher(
            scholarship_id=app_record.scholarship_id,
            session=session,
            live_research=live_research,
        )
        research_facts = [
            f.model_dump(mode="json") if hasattr(f, "model_dump") else dict(f)
            for f in research_res.facts
        ]

    # Stage 3: researching -> drafting
    stored_draft = (await session.execute(select(Draft).where(Draft.application_id == app_record.id, Draft.kind == "essay")
        .order_by(Draft.version.desc()))).scalars().first()
    draft_output = None
    if app_record.status == "researching" or (app_record.status == "drafting" and stored_draft is None):
        if not research_facts:
            # In case status was already researching on entry
            research_res = await run_researcher(
                scholarship_id=app_record.scholarship_id,
                session=session,
                live_research=live_research,
            )
            research_facts = [
                f.model_dump(mode="json") if hasattr(f, "model_dump") else dict(f)
                for f in research_res.facts
            ]

        if app_record.status == "researching":
            app_record = await transition_application(
                application=app_record, new_status="drafting", actor="coordinator",
                payload={"facts_discovered": len(research_facts)}, session=session,
            )

        # Edge finder generates competitive angles
        edge_res = await run_edge_finder(
            user_id=app_record.user_id,
            scholarship_id=app_record.scholarship_id,
            research_facts=research_facts,
            session=session,
        )

        session.add(ApplicationEvent(application_id=app_record.id, actor="researcher", event_type="research_evidence", payload={"facts": research_facts}))
        session.add(ApplicationEvent(application_id=app_record.id, actor="edge_finder", event_type="source_angles", payload={"angles": [angle.model_dump() for angle in edge_res.angles]}))
        await session.commit()
        # Drafter generates grounded essay with verifier validation
        rules = scholarship.eligibility_rules if scholarship.eligibility_rules else {}
        essay_prompt = rules.get(
            "essay_prompt",
            "Explain how your proposed study will enable you to make a meaningful contribution.",
        )
        word_limit = rules.get("essay_word_limit", 500)

        draft_output = await run_drafter(
            application_id=app_record.id,
            user_id=app_record.user_id,
            scholarship_id=app_record.scholarship_id,
            angles=edge_res.angles,
            essay_prompt=essay_prompt,
            word_limit=word_limit,
            session=session,
            research_facts=research_facts,
        )

    # Stage 4: Autonomy Branching
    if app_record.status == "drafting" and not is_demo_portal(scholarship.application_url):
        return await handoff_real_portal(app_record, scholarship, session)
    if app_record.status == "drafting":
        manual_only = not is_demo_portal(scholarship.application_url) or (scholarship.eligibility_rules or {}).get("ai_policy", "unknown") not in {"allowed", "disclose"}
        if app_record.mode_used == "review" or manual_only:
            app_record = await transition_application(
                application=app_record,
                new_status="ready_for_review",
                actor="coordinator",
                payload={
                    "draft_id": str(draft_output.draft_id) if draft_output else None,
                    "word_count": draft_output.word_count if draft_output else None,
                    "source_facts_count": len(draft_output.source_facts) if draft_output else 0,
                    "manual_only": manual_only,
                },
                session=session,
            )
            return {
                "application_id": str(app_record.id),
                "status": app_record.status,
                "mode": "review",
                "draft_id": str(draft_output.draft_id) if draft_output else None,
                "message": "Draft created. Application paused in ready_for_review awaiting user review.",
            }
        else:
            # Autopilot mode: enqueue submit_application background job
            job = await enqueue_job(
                "submit_application",
                {"application_id": str(app_record.id)},
                session=session,
            )
            return {
                "application_id": str(app_record.id),
                "status": app_record.status,
                "mode": "autopilot",
                "draft_id": str(draft_output.draft_id) if draft_output else None,
                "submission_job_id": str(job.id),
                "message": "Draft created in autopilot mode. Submitter job enqueued.",
            }

    return {
        "application_id": str(app_record.id),
        "status": app_record.status,
        "mode": app_record.mode_used,
    }


@register_job_handler("coordinator_pipeline")
async def coordinator_pipeline_job_handler(
    job: Job,
    payload: Dict[str, Any],
    session: AsyncSession,
) -> Dict[str, Any]:
    """Queue worker job handler for 'coordinator_pipeline' jobs."""
    effective_payload = payload or job.payload or {}
    application_id = uuid.UUID(effective_payload["application_id"])
    return await run_coordinator_pipeline(application_id, session)
