from pydantic import BaseModel, Field


class IntakeFact(BaseModel):
    category: str
    text: str
    sensitive: bool = False


class IntakeOut(BaseModel):
    facts: list[IntakeFact] = Field(default_factory=list)


class MatcherOut(BaseModel):
    fit_score: int
    fit_reason: str
    strongest_fact_ids: list[str] = Field(default_factory=list)
    missing_criteria: list[str] = Field(default_factory=list)


class ResearchFact(BaseModel):
    topic: str
    text: str
    snippet: str


class ResearcherOut(BaseModel):
    facts: list[ResearchFact] = Field(default_factory=list)


class EdgeItem(BaseModel):
    profile_fact_ids: list[str]
    dossier_fact_ids: list[str]
    reason: str
    use_in: str
    strength: float


class GapItem(BaseModel):
    criterion: str
    question: str


class EdgeOut(BaseModel):
    edges: list[EdgeItem] = Field(default_factory=list)
    gaps: list[GapItem] = Field(default_factory=list)


class SegmentOut(BaseModel):
    text: str
    source_ids: list[str] = Field(default_factory=list)


class TailorOut(BaseModel):
    cv_summary: list[SegmentOut] = Field(default_factory=list)
    cv_bullets: list[SegmentOut] = Field(default_factory=list)
    essay: list[SegmentOut] = Field(default_factory=list)


class ReviseItem(BaseModel):
    section: str
    segment_index: int
    text: str
    source_ids: list[str] = Field(default_factory=list)


class ReviseOut(BaseModel):
    revisions: list[ReviseItem] = Field(default_factory=list)


class ExtractedClaim(BaseModel):
    text: str
    section: str
    segment_index: int


class ExtractOut(BaseModel):
    claims: list[ExtractedClaim] = Field(default_factory=list)


class JudgeItem(BaseModel):
    claim_id: str
    verdict: str
    reason: str


class JudgeOut(BaseModel):
    verdicts: list[JudgeItem] = Field(default_factory=list)


class ChallengeItem(BaseModel):
    claim_id: str
    outcome: str
    reason: str


class ChallengeOut(BaseModel):
    challenges: list[ChallengeItem] = Field(default_factory=list)


class OutlineSection(BaseModel):
    title: str
    notes: str
    fact_ids: list[str] = Field(default_factory=list)


class OutlineOut(BaseModel):
    sections: list[OutlineSection] = Field(default_factory=list)
