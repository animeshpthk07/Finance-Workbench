"""Typed, evidence-first records used throughout Finance Workbench."""
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "critical"]
ReviewStatus = Literal["pending", "reviewed", "dismissed"]


class FinancialMetric(BaseModel):
    metric_name: str
    value: float
    currency: str = "INR"
    unit: Optional[str] = None
    period: Optional[str] = None
    department: Optional[str] = None
    entity: Optional[str] = None
    record_type: Optional[str] = None
    source_file: str
    source_location: Optional[str] = None
    source_text: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Evidence(BaseModel):
    source_file: str
    source_location: Optional[str] = None
    source_text: Optional[str] = None
    relevance: Optional[str] = None


class Finding(BaseModel):
    finding_id: str = Field(default_factory=lambda: str(uuid4()))
    finding_type: str
    title: str
    description: str
    severity: Severity = "medium"
    metric_name: Optional[str] = None
    expected_value: Optional[float] = None
    observed_value: Optional[float] = None
    difference: Optional[float] = None
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    requires_human_review: bool = True
    review_status: ReviewStatus = "pending"
    reviewer_note: str = ""


class Investigation(BaseModel):
    investigation_id: str = Field(default_factory=lambda: str(uuid4()))
    finding_id: str
    summary: str
    likely_causes: list[str] = Field(default_factory=list)
    verification_checks: list[str] = Field(default_factory=list)
    recommended_next_step: str = "Verify the cited evidence with an accountable reviewer."
    evidence_summary: list[str] = Field(default_factory=list)
    llm_ready_prompt: str
    facts: list[str] = Field(default_factory=list)
    interpretations: list[str] = Field(default_factory=list)
    generation_mode: Literal["deterministic", "openai"] = "deterministic"
    model_name: Optional[str] = None
    model_error: Optional[str] = None
    requires_human_review: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
