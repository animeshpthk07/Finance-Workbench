"""End-to-end, evidence-first financial investigation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import pandas as pd

from backend.ingestion import ParsedDocument, parse_documents
from backend.investigator import investigate_findings
from backend.models import Evidence, Finding, FinancialMetric, Investigation
from backend.normalization import normalize_frame, rows_to_metrics


@dataclass
class WorkspaceRun:
    documents: list[ParsedDocument]
    normalized_rows: pd.DataFrame
    metrics: list[FinancialMetric]
    variance: pd.DataFrame
    findings: list[Finding]
    investigations: list[Investigation]
    ingestion_errors: list[str] = field(default_factory=list)

    @property
    def review_queue(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.requires_human_review and finding.review_status == "pending"]


def _evidence_from_row(row: pd.Series, relevance: str) -> Evidence:
    value = "Unavailable" if pd.isna(row["value"]) else f"{float(row['value']):,.2f}"
    return Evidence(
        source_file=str(row["source_file"]),
        source_location=str(row["source_location"]),
        source_text=f"{row['metric_name']}: {value} {row['currency']}",
        relevance=relevance,
    )


def calculate_variance_table(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    keys = ["metric_name", "department", "period", "currency"]
    grouped = rows.groupby(keys + ["record_type"], dropna=False)["value"].sum().reset_index()
    pivot = grouped.pivot_table(index=keys, columns="record_type", values="value", aggfunc="sum", fill_value=0).reset_index()
    if "budget" not in pivot.columns or "actual" not in pivot.columns:
        return pd.DataFrame()
    result = pivot.rename(columns={"budget": "budget_value", "actual": "actual_value"}).copy()
    result["variance_amount"] = result["actual_value"] - result["budget_value"]
    result["variance_percentage"] = result.apply(
        lambda row: None if row["budget_value"] == 0 else round((row["variance_amount"] / abs(row["budget_value"])) * 100, 2),
        axis=1,
    )
    return result.sort_values("variance_amount", key=lambda values: values.abs(), ascending=False).reset_index(drop=True)


def _duplicate_findings(rows: pd.DataFrame) -> list[Finding]:
    if rows.empty:
        return []
    keys = [column for column in ["transaction_id", "metric_name", "department", "period", "value", "record_type"] if column in rows.columns]
    duplicates = rows[rows.duplicated(subset=keys, keep=False)] if keys else pd.DataFrame()
    findings: list[Finding] = []
    for _, group in duplicates.groupby(keys, dropna=False):
        first = group.iloc[0]
        findings.append(
            Finding(
                finding_type="duplicate_transaction",
                title=f"Possible duplicate: {first['metric_name']}",
                description=f"{len(group)} matching rows were found for the same metric, period, department, value, and record type.",
                severity="high",
                metric_name=str(first["metric_name"]),
                observed_value=float(first["value"]),
                evidence=[_evidence_from_row(row, "Matching source row") for _, row in group.iterrows()],
            )
        )
    return findings


def _missing_value_findings(rows: pd.DataFrame) -> list[Finding]:
    if rows.empty:
        return []
    candidates = rows[rows["value"].isna() | (rows["metric_name"].str.strip() == "")]
    findings: list[Finding] = []
    for _, row in candidates.iterrows():
        missing_fields = []
        if pd.isna(row["value"]):
            missing_fields.append("value")
        if not str(row["metric_name"]).strip():
            missing_fields.append("metric name")
        findings.append(
            Finding(
                finding_type="missing_required_value",
                title="Missing required financial value",
                description=f"The row is missing {', '.join(missing_fields)}.",
                severity="medium",
                evidence=[Evidence(source_file=str(row["source_file"]), source_location=str(row["source_location"]), relevance="Incomplete source row")],
            )
        )
    return findings


def _variance_findings(variance: pd.DataFrame, rows: pd.DataFrame, threshold_percent: float) -> list[Finding]:
    if variance.empty:
        return []
    findings: list[Finding] = []
    for _, item in variance.iterrows():
        percentage = item["variance_percentage"]
        if percentage is None or pd.isna(percentage) or abs(float(percentage)) < threshold_percent:
            continue
        evidence_rows = rows[(rows["metric_name"] == item["metric_name"]) & (rows["department"] == item["department"]) & (rows["period"] == item["period"]) & (rows["record_type"].isin(["budget", "actual"]))]
        severity = "critical" if abs(float(percentage)) >= 50 else "high" if abs(float(percentage)) >= 25 else "medium"
        findings.append(
            Finding(
                finding_type="budget_actual_variance",
                title=f"Material variance: {item['metric_name']}",
                description=f"Actual is {float(percentage):.2f}% {'above' if item['variance_amount'] > 0 else 'below'} budget for {item['period']} ({item['department']}).",
                severity=severity,
                metric_name=str(item["metric_name"]),
                expected_value=float(item["budget_value"]),
                observed_value=float(item["actual_value"]),
                difference=float(item["variance_amount"]),
                evidence=[_evidence_from_row(row, "Budget or actual source value") for _, row in evidence_rows.iterrows()],
            )
        )
    return findings


def _outlier_findings(rows: pd.DataFrame) -> list[Finding]:
    if len(rows) < 4:
        return []
    findings: list[Finding] = []
    for _, group in rows.dropna(subset=["value"]).groupby(["metric_name", "record_type"], dropna=False):
        if len(group) < 4:
            continue
        lower, upper = group["value"].quantile([0.25, 0.75])
        iqr = upper - lower
        if iqr == 0:
            continue
        outliers = group[(group["value"] < lower - 1.5 * iqr) | (group["value"] > upper + 1.5 * iqr)]
        for _, row in outliers.iterrows():
            findings.append(Finding(finding_type="statistical_outlier", title=f"Outlier value: {row['metric_name']}", description="The amount falls outside the interquartile range for comparable source rows.", severity="medium", metric_name=str(row["metric_name"]), observed_value=float(row["value"]), evidence=[_evidence_from_row(row, "Statistical outlier in the source data")]))
    return findings


def attach_pdf_evidence(findings: list[Finding], documents: list[ParsedDocument]) -> list[Finding]:
    """Attach PDF text only when it directly names the finding metric."""
    pdfs = [document for document in documents if document.kind == "pdf" and document.text]
    for finding in findings:
        metric = (finding.metric_name or "").strip()
        if not metric:
            continue
        for document in pdfs:
            source_text = document.text
            position = source_text.lower().find(metric.lower())
            if position < 0:
                continue
            start = max(0, position - 180)
            end = min(len(source_text), position + len(metric) + 360)
            snippet = " ".join(source_text[start:end].split())
            if snippet:
                finding.evidence.append(Evidence(source_file=document.name, source_location=f"PDF text near character {position + 1}", source_text=snippet, relevance=f"Supporting report text that names {metric}; reviewer must validate context."))
    return findings


def run_workspace(sources: Iterable[Any], variance_threshold_percent: float = 10.0) -> WorkspaceRun:
    """Run all local stages and return reviewable, traceable outputs."""
    documents = parse_documents(sources)
    ingestion_errors = [f"{document.name}: {error}" for document in documents for error in document.errors]
    normalized_frames = [normalize_frame(document.frame, document.name) for document in documents if document.frame is not None and not document.errors]
    rows = pd.concat(normalized_frames, ignore_index=True) if normalized_frames else pd.DataFrame()
    metrics = rows_to_metrics(rows) if not rows.empty else []
    variance = calculate_variance_table(rows)
    findings = (_missing_value_findings(rows) + _duplicate_findings(rows) + _variance_findings(variance, rows, variance_threshold_percent) + _outlier_findings(rows)) if not rows.empty else []
    attach_pdf_evidence(findings, documents)
    return WorkspaceRun(documents=documents, normalized_rows=rows, metrics=metrics, variance=variance, findings=findings, investigations=investigate_findings(findings), ingestion_errors=ingestion_errors)
