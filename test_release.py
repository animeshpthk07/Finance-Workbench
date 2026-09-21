"""Release checks: review exports, currency isolation, AI boundaries and UI."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from backend.investigator import InvestigatorConfig, _model_draft, investigate_finding
from backend.models import Finding
from backend.normalization import normalize_frame
from backend.pipeline import calculate_variance_table, run_workspace
from backend.reporting import build_json_report, build_markdown_report

ROOT = Path(__file__).parent


def demo():
    return run_workspace([ROOT / "Q2_Budget.xlsx", ROOT / "Q2_Actuals.csv", ROOT / "Q2_Report.pdf"])


def test_review_exports_include_notes_status_and_evidence():
    run = demo()
    run.findings[0].review_status = "reviewed"
    run.findings[0].reviewer_note = "Verified against the invoice | owner review pending.\nFollow up tomorrow."
    markdown = build_markdown_report(run)
    record = json.loads(build_json_report(run))
    assert "Verified against the invoice \\|" in markdown
    assert "reviewed" in markdown
    assert "Observed facts" in markdown
    assert record["findings"][0]["reviewer_note"] == run.findings[0].reviewer_note
    assert record["findings"][0]["evidence"]
    assert "OPENAI_API_KEY" not in build_json_report(run)


def test_pipeline_never_calls_ai_implicitly(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-placeholder")
    monkeypatch.setenv("FINANCE_WORKBENCH_AI_MODEL", "unit-test-model")
    def forbidden(*args):
        raise AssertionError("Unexpected external AI call")
    monkeypatch.setattr("backend.investigator._model_draft", forbidden)
    assert all(item.generation_mode == "deterministic" and not item.model_error for item in demo().investigations)


def test_public_demo_disables_server_ai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-placeholder")
    monkeypatch.setenv("FINANCE_WORKBENCH_AI_MODEL", "unit-test-model")
    monkeypatch.setenv("FINANCE_WORKBENCH_PUBLIC_DEMO", "true")
    assert not InvestigatorConfig.from_environment().enabled


@pytest.mark.parametrize("response", [{}, {"summary": 123}, {"summary": "x", "recommended_next_step": "Check", "likely_causes": [], "verification_checks": ["Check"], "interpretations": ["Maybe"]}])
def test_malformed_ai_output_keeps_local_draft(monkeypatch, response):
    monkeypatch.setattr("backend.investigator._model_draft", lambda *_: response)
    result = investigate_finding(Finding(finding_type="variance", title="Variance", description="Actual exceeds budget."), InvestigatorConfig("test", True))
    assert result.generation_mode == "deterministic"
    assert result.model_error


def test_openai_request_is_bounded_and_does_not_store(monkeypatch):
    calls = {}
    payload = {"summary": "Draft", "recommended_next_step": "Verify source.", "likely_causes": ["Mapping may differ."], "verification_checks": ["Verify."], "interpretations": ["Unconfirmed."]}
    def create(**kwargs):
        calls["request"] = kwargs
        return SimpleNamespace(status="completed", output_text=json.dumps(payload))
    def client(**kwargs):
        calls["client"] = kwargs
        return SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=client))
    assert _model_draft(Finding(finding_type="variance", title="Test", description="Test"), InvestigatorConfig("test-model", True)) == payload
    assert calls["client"] == {"timeout": 45.0, "max_retries": 0}
    assert calls["request"]["store"] is False
    assert calls["request"]["max_output_tokens"] == 2000
    assert calls["request"]["text"]["format"]["strict"] is True


def test_currency_evidence_is_not_mixed(tmp_path):
    paths = []
    for name, amounts in [("Budget.csv", [100, 200]), ("Actuals.csv", [150, 200])]:
        path = tmp_path / name
        pd.DataFrame({"Category": ["Sales", "Sales"], "Amount": amounts, "Currency": ["INR", "USD"]}).to_csv(path, index=False)
        paths.append(path)
    run = run_workspace(paths)
    variance = [item for item in run.findings if item.finding_type == "budget_actual_variance"]
    assert len(variance) == 1
    assert all("INR" in evidence.source_text for evidence in variance[0].evidence)
    assert not any(item.finding_type == "duplicate_transaction" for item in run.findings)


def test_missing_side_is_not_assumed_to_be_zero():
    frame = pd.concat([
        normalize_frame(pd.DataFrame({"Category": ["Sales"], "Amount": [100]}), "Budget.csv"),
        normalize_frame(pd.DataFrame({"Category": ["Travel"], "Amount": [25]}), "Actuals.csv"),
    ], ignore_index=True)
    assert calculate_variance_table(frame)["variance_percentage"].isna().all()


def test_unknown_columns_do_not_turn_ids_into_amounts():
    rows = normalize_frame(pd.DataFrame({"Invoice Number": [12345]}), "Actuals.csv")
    assert rows["value"].isna().all()
    assert rows["metric_name"].eq("").all()


def test_zero_budget_actual_is_reviewed(tmp_path):
    paths = []
    for name, amount in [("Budget.csv", 0), ("Actuals.csv", 25)]:
        path = tmp_path / name
        pd.DataFrame({"Category": ["Travel"], "Amount": [amount]}).to_csv(path, index=False)
        paths.append(path)
    run = run_workspace(paths)
    assert any(item.finding_type == "unbudgeted_actual" for item in run.findings)
    assert "n/a" in build_markdown_report(run)
    assert json.loads(build_json_report(run))["variance"][0]["variance_percentage"] is None


def test_all_app_pages_review_notes_and_exports(monkeypatch):
    monkeypatch.delenv("FINANCE_WORKBENCH_AI_MODEL", raising=False)
    monkeypatch.delenv("FINANCE_WORKBENCH_PUBLIC_DEMO", raising=False)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    next(item for item in app.button if item.label == "Use included Q2 demo").click().run()
    assert not app.exception
    original_pending = len(app.session_state["workspace_run"].review_queue)
    for page in ["Investigate", "Review queue", "Report", "Review queue", "Overview"]:
        app.radio[0].set_value(page).run()
        assert not app.exception, [item.message for item in app.exception]
        if page == "Review queue":
            app.checkbox[0].check().run()
            app.text_area[0].set_value("Verified demo source evidence.").run()
        if page == "Report":
            assert len(app.get("download_button")) == 2
            assert "Verified demo source evidence." in build_markdown_report(app.session_state["workspace_run"])
    assert app.session_state["workspace_run"].findings[0].reviewer_note == "Verified demo source evidence."
    assert len(app.session_state["workspace_run"].review_queue) == original_pending - 1


def test_public_demo_has_no_upload_or_ai_controls(monkeypatch):
    monkeypatch.setenv("FINANCE_WORKBENCH_PUBLIC_DEMO", "true")
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.get("file_uploader")
    next(item for item in app.button if item.label == "Use included Q2 demo").click().run()
    app.radio[0].set_value("Investigate").run()
    assert not app.exception
    assert not any(item.label == "Generate optional AI draft" for item in app.button)
