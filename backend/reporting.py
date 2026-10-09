"""Local first-draft reporting. No report is sent or published automatically."""
from __future__ import annotations
import json
import re
import unicodedata
from datetime import datetime, timezone
import pandas as pd
from backend.pipeline import WorkspaceRun


_MARKDOWN_PUNCTUATION = frozenset("\\`*_{}[]()#+-!|~=@:$")


def _literal(value: object) -> str:
    """Render a single-line value as text, never Markdown instructions.

    Escape punctuation before placing values in headings, lists, tables or body
    text. HTML delimiters and existing entities are escaped separately. Colons,
    at signs and www prefixes are escaped to prevent GFM automatic links too.
    Line breaks, controls and invisible format characters become spaces, so a
    value cannot create a new block or hide a direction-changing character.
    The JSON export retains the original values and original whitespace.
    """
    normalized = " ".join("".join(
        " " if char.isspace() or unicodedata.category(char) in {"Cc", "Cf", "Cs"} else char
        for char in str(value)
    ).split())
    escaped = "".join(
        {"&": "&amp;", "<": "&lt;", ">": "&gt;"}.get(char)
        or ("\\" + char if char in _MARKDOWN_PUNCTUATION else char)
        for char in normalized
    )
    # Periods stay readable in amounts and ordinary prose. Escape the two
    # contexts where an otherwise plain period can start Markdown structure.
    escaped = re.sub(r"(?<!\S)(\d{1,9})\.(?=\s)", r"\1\\.", escaped)
    return re.sub(r"(?i)\b(www)\.", r"\1\\.", escaped)


def _table(rows: list[list[str]], headings: list[str]) -> str:
    if not rows:
        return "No rows."
    lines = ["| " + " | ".join(_literal(value) for value in headings) + " |", "| " + " | ".join(["---"] * len(headings)) + " |"]
    lines.extend("| " + " | ".join(_literal(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def build_markdown_report(workspace: WorkspaceRun) -> str:
    files = ", ".join(_literal(document.name) for document in workspace.documents) or "None"
    def amount(value):
        return "n/a" if pd.isna(value) else f"{value:,.2f}"
    variance_rows = [[row.metric_name, row.department, row.period, row.currency, amount(row.budget_value), amount(row.actual_value), amount(row.variance_amount), "n/a" if pd.isna(row.variance_percentage) else f"{row.variance_percentage:.2f}%"] for row in workspace.variance.itertuples(index=False)] if not workspace.variance.empty else []
    finding_rows = [[finding.severity.upper(), finding.title, finding.description, finding.review_status, finding.reviewer_note or "Not recorded", "; ".join(item.source_file for item in finding.evidence)] for finding in workspace.findings]
    investigation_rows = [[finding.title, investigation.generation_mode, investigation.recommended_next_step, "; ".join(investigation.evidence_summary)] for finding, investigation in zip(workspace.findings, workspace.investigations)]
    detail = []
    for finding, investigation in zip(workspace.findings, workspace.investigations):
        detail.extend([f"### {_literal(finding.title)}", _literal(investigation.summary), "", "Observed facts:"])
        detail.extend(f"- {_literal(fact)}" for fact in investigation.facts)
        detail.append("\nInterpretations — unverified:")
        detail.extend(f"- {_literal(item)}" for item in investigation.interpretations)
        detail.append("\nVerification checks:")
        detail.extend(f"- {_literal(item)}" for item in investigation.verification_checks)
        detail.append("")
    return "\n".join(["# Finance Workbench — Investigation Draft", "", "## Review status", "This report is a first draft. It is evidence-linked, but every finding requires human validation before a financial decision is made.", f"Pending reviews: {len(workspace.review_queue)} of {len(workspace.findings)} findings.", "", "## Source documents", files, "", "## Deterministic budget-versus-actual analysis", _table(variance_rows, ["Metric", "Department", "Period", "Currency", "Budget", "Actual", "Variance", "Variance %"]), "", "## Findings and reviewer record", _table(finding_rows, ["Severity", "Finding", "Description", "Review status", "Reviewer note", "Evidence files"]), "", "## Investigation drafts", _table(investigation_rows, ["Finding", "Draft source", "Recommended verification", "Evidence references"]), "", *detail, "## Suggested reviewer workflow", "1. Verify each cited source row or document page.", "2. Record the business explanation and supporting evidence.", "3. Mark the finding reviewed only after an accountable person has validated it.", "4. Download the report or JSON review record before closing the session."])


def build_json_report(workspace: WorkspaceRun) -> str:
    """Portable review record, including notes and evidence but no raw uploads or secrets."""
    def record(model):
        return json.loads(model.model_dump_json() if hasattr(model, "model_dump_json") else model.json())
    return json.dumps({
        "schema_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "requires_human_validation": True,
        "documents": [{"name": item.name, "kind": item.kind, "errors": item.errors} for item in workspace.documents],
        "variance": json.loads(workspace.variance.to_json(orient="records")),
        "findings": [record(item) for item in workspace.findings],
        "investigations": [record(item) for item in workspace.investigations],
        "ingestion_errors": workspace.ingestion_errors,
    }, indent=2, ensure_ascii=False, allow_nan=False)
