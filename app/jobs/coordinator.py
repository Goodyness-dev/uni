"""Coordinator pipeline: orchestrates the multi-agent application workflow."""
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.drafter import run_drafter
from app.agents.edge_finder import run_edge_finder
from app.agents.researcher import run_researcher
from app.api.v1.matches import evaluate_eligibility_and_fit
from app.core.logging import logger
from app.core.tracing import workflow_span
from app.db.models import Application, Job, Profile, Scholarship, User
from app.jobs.queue import enqueue_job, register_job_handler
from app.jobs.state_machine import transition_application


@workflow_span("coordinator_pipeline")
async def run_coordinator_pipeline(
    application_id: uuid.UUID,
    session: AsyncSession,
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
        )
        research_facts = [
            f.model_dump(mode="json") if hasattr(f, "model_dump") else dict(f)
            for f in research_res.facts
        ]

    # Stage 3: researching -> drafting
    draft_output = None
    if app_record.status == "researching":
        if not research_facts:
            # In case status was already researching on entry
            research_res = await run_researcher(
                scholarship_id=app_record.scholarship_id,
                session=session,
            )
            research_facts = [
                f.model_dump(mode="json") if hasattr(f, "model_dump") else dict(f)
                for f in research_res.facts
            ]

        app_record = await transition_application(
            application=app_record,
            new_status="drafting",
            actor="coordinator",
            payload={"facts_discovered": len(research_facts)},
            session=session,
        )

        # Edge finder generates competitive angles
        edge_res = await run_edge_finder(
            user_id=app_record.user_id,
            scholarship_id=app_record.scholarship_id,
            research_facts=research_facts,
            session=session,
        )

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
        )

    # Stage 4: Autonomy Branching
    if app_record.status == "drafting":
        if app_record.mode_used == "review":
            app_record = await transition_application(
                application=app_record,
                new_status="ready_for_review",
                actor="coordinator",
                payload={
                    "draft_id": str(draft_output.draft_id) if draft_output else None,
                    "word_count": draft_output.word_count if draft_output else None,
                    "source_facts_count": len(draft_output.source_facts) if draft_output else 0,
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
