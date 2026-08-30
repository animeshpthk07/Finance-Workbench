from datetime import date
from typing import Optional, Literal
from pydantic import BaseModel, Field


class FinancialMetric(BaseModel):
    metric_name: str
    value: float
    currency: Optional[str] = None
    unit: Optional[str] = None
    period: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    entity: Optional[str] = None

    source_file: Optional[str] = None
    source_location: Optional[str] = None
    source_text: Optional[str] = None

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Evidence(BaseModel):
    source_file: str
    source_location: Optional[str] = None
    source_text: Optional[str] = None
    relevance: Optional[str] = None


class Finding(BaseModel):
    finding_type: str
    title: str
    description: str

    severity: Literal["low", "medium", "high", "critical"] = "medium"

    metric_name: Optional[str] = None

    expected_value: Optional[float] = None
    observed_value: Optional[float] = None

    difference: Optional[float] = None

    evidence: list[Evidence] = []

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    requires_human_review: bool = True
