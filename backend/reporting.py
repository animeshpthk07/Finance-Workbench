"""Local first-draft reporting. No report is sent or published automatically."""
from __future__ import annotations
from backend.pipeline import WorkspaceRun


def _table(rows: list[list[str]], headings: list[str]) -> str:
    if not rows:
        return "No rows."
    lines = ["| " + " | ".join(headings) + " |", "| " + " | ".join(["---"] * len(headings)) + " |"]
    lines.extend("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |" for row in rows)
    return "\n".join(lines)


def build_markdown_report(workspace: WorkspaceRun) -> str:
    files = ", ".join(document.name for document in workspace.documents) or "None"
    variance_rows = [[row.metric_name, row.department, row.period, f"{row.budget_value:,.2f}", f"{row.actual_value:,.2f}", f"{row.variance_amount:,.2f}", "n/a" if row.variance_percentage is None else f"{row.variance_percentage:.2f}%"] for row in workspace.variance.itertuples(index=False)] if not workspace.variance.empty else []
    finding_rows = [[finding.severity.upper(), finding.title, finding.description, "; ".join(item.source_file for item in finding.evidence)] for finding in workspace.findings]
    investigation_rows = [[finding.title, investigation.generation_mode, investigation.recommended_next_step, "; ".join(investigation.evidence_summary)] for finding, investigation in zip(workspace.findings, workspace.investigations)]
    return "\n".join(["# Finance Workbench — Investigation Draft", "", "## Review status", "This report is a first draft. It is evidence-linked, but every finding requires human validation before a financial decision is made.", "", "## Source documents", files, "", "## Deterministic budget-versus-actual analysis", _table(variance_rows, ["Metric", "Department", "Period", "Budget", "Actual", "Variance", "Variance %"]), "", "## Findings requiring review", _table(finding_rows, ["Severity", "Finding", "Description", "Evidence files"]), "", "## Investigation drafts", _table(investigation_rows, ["Finding", "Draft source", "Recommended verification", "Evidence references"]), "", "## Suggested reviewer workflow", "1. Verify each cited source row or document page.", "2. Record the business explanation and supporting evidence.", "3. Mark the finding reviewed only after an accountable person has validated it."])
