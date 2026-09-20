"""Regression checks for calculations, evidence, investigation and reporting."""
import pandas as pd
from backend.ingestion import ParsedDocument
from backend.investigator import InvestigatorConfig, investigate_finding
from backend.models import Evidence, Finding
from backend.pipeline import attach_pdf_evidence, calculate_variance_table, run_workspace
from backend.reporting import build_markdown_report
from evaluation import run_evaluation


def test_variance_table_calculates_amount_and_percent():
    rows = pd.DataFrame([
        {"metric_name": "Revenue", "department": "Sales", "period": "Q2", "currency": "INR", "record_type": "budget", "value": 100.0},
        {"metric_name": "Revenue", "department": "Sales", "period": "Q2", "currency": "INR", "record_type": "actual", "value": 125.0},
    ])
    result = calculate_variance_table(rows)
    assert result.loc[0, "variance_amount"] == 25.0
    assert result.loc[0, "variance_percentage"] == 25.0


def test_variance_table_handles_no_metrics():
    assert calculate_variance_table(pd.DataFrame()).empty


def _pair(tmp_path, budget=100, actual=140):
    for name, amount in [("Budget.csv", budget), ("Actuals.csv", actual)]:
        pd.DataFrame({"Category": ["Revenue"], "Amount_INR": [amount], "Period": ["Q2"], "Department": ["Sales"]}).to_csv(tmp_path / name, index=False)
    return run_workspace([tmp_path / "Budget.csv", tmp_path / "Actuals.csv"])


def test_pipeline_builds_variance_evidence_and_investigation(tmp_path):
    workspace = _pair(tmp_path)
    assert len(workspace.metrics) == 2
    assert len(workspace.variance) == 1
    assert any(f.finding_type == "budget_actual_variance" for f in workspace.findings)
    assert all(i.requires_human_review for i in workspace.investigations)
    assert all(len(f.evidence) == 2 for f in workspace.findings)


def test_duplicate_rows_are_flagged(tmp_path):
    pd.DataFrame({"Category": ["Travel", "Travel"], "Amount_INR": [500, 500], "Period": ["Q2", "Q2"], "Department": ["Operations", "Operations"]}).to_csv(tmp_path / "Actuals.csv", index=False)
    workspace = run_workspace([tmp_path / "Actuals.csv"])
    assert any(f.finding_type == "duplicate_transaction" for f in workspace.findings)


def test_zero_budget_does_not_produce_infinite_percentage(tmp_path):
    assert _pair(tmp_path, budget=0, actual=250).variance.loc[0, "variance_percentage"] is None


def test_report_is_explicitly_reviewable(tmp_path):
    report = build_markdown_report(_pair(tmp_path))
    assert "requires human validation" in report
    assert "Material variance" in report
    assert "40.00" in report


def test_pdf_text_is_attached_only_when_the_metric_matches():
    finding = Finding(finding_type="budget_actual_variance", title="Material variance: Revenue", description="Actual is above budget.", metric_name="Revenue", evidence=[Evidence(source_file="Actuals.csv", source_location="row 2", source_text="Revenue: 140.00 INR")])
    attach_pdf_evidence([finding], [ParsedDocument(name="Q2_Report.pdf", kind="pdf", text="Board report: Revenue grew because of a new sales channel."), ParsedDocument(name="Unrelated.pdf", kind="pdf", text="Travel spending remained flat.")])
    pdf_evidence = [item for item in finding.evidence if item.source_file.endswith(".pdf")]
    assert len(pdf_evidence) == 1
    assert "Revenue" in pdf_evidence[0].source_text
    assert "character" in pdf_evidence[0].source_location


def test_investigator_keeps_facts_separate_from_interpretations(monkeypatch):
    finding = Finding(finding_type="budget_actual_variance", title="Material variance: Software", description="Actual is 40% above budget.", metric_name="Software", expected_value=100, observed_value=140, difference=40, evidence=[Evidence(source_file="Budget.csv", source_location="row 2", source_text="Software: 100.00 INR")])
    monkeypatch.setattr("backend.investigator._model_draft", lambda *_: {"summary": "Verify the source mapping.", "likely_causes": ["Mapping may differ."], "verification_checks": ["Compare source rows."], "recommended_next_step": "Ask the finance owner to validate the mapping.", "interpretations": ["A mapping difference is possible, not confirmed."]})
    investigation = investigate_finding(finding, InvestigatorConfig(model_name="test-model", api_key_available=True))
    assert investigation.generation_mode == "openai"
    assert "Budget.csv" in " ".join(investigation.facts)
    assert investigation.interpretations == ["A mapping difference is possible, not confirmed."]
    assert investigation.requires_human_review


def test_optional_ai_failure_retains_deterministic_draft(monkeypatch):
    def unavailable(*_):
        raise RuntimeError("test outage")
    monkeypatch.setattr("backend.investigator._model_draft", unavailable)
    finding = Finding(finding_type="missing_required_value", title="Missing amount", description="A source amount is missing.")
    investigation = investigate_finding(finding, InvestigatorConfig(model_name="test-model", api_key_available=True))
    assert investigation.generation_mode == "deterministic"
    assert investigation.model_error
    assert investigation.requires_human_review


def test_portable_evaluation_scenarios_all_pass():
    result = run_evaluation()
    assert result["passed"] == result["total"]
    assert result["total"] >= 6
