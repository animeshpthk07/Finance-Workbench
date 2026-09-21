"""Repeatable, local reliability checks for the primary investigation pipeline."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backend.pipeline import WorkspaceRun, run_workspace


@dataclass(frozen=True)
class EvaluationCase:
    name: str
    passed: bool
    detail: str


def _write_csv(folder: Path, name: str, rows: dict[str, list[object]]) -> Path:
    path = folder / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _has_finding(workspace: WorkspaceRun, finding_type: str) -> bool:
    return any(finding.finding_type == finding_type for finding in workspace.findings)


def run_evaluation() -> dict[str, object]:
    """Run deterministic scenarios without Colab paths, network calls, or secrets."""
    cases: list[EvaluationCase] = []
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        clean = run_workspace([_write_csv(root, "Clean_Budget.csv", {"Category": ["Revenue"], "Amount_INR": [100], "Period": ["Q2"], "Department": ["Sales"]}), _write_csv(root, "Clean_Actuals.csv", {"Category": ["Revenue"], "Amount_INR": [105], "Period": ["Q2"], "Department": ["Sales"]})])
        cases.append(EvaluationCase("correct_budget_actual_no_material_variance", not _has_finding(clean, "budget_actual_variance"), "A 5% variance remains below the default 10% threshold."))
        material = run_workspace([_write_csv(root, "Material_Budget.csv", {"Category": ["Software"], "Amount_INR": [100], "Period": ["Q2"], "Department": ["Technology"]}), _write_csv(root, "Material_Actuals.csv", {"Category": ["Software"], "Amount_INR": [160], "Period": ["Q2"], "Department": ["Technology"]})])
        cases.append(EvaluationCase("cross_document_budget_actual_mismatch", _has_finding(material, "budget_actual_variance"), "A material variance is detected with evidence from both documents."))
        duplicate = run_workspace([_write_csv(root, "Duplicate_Actuals.csv", {"Category": ["Travel", "Travel"], "Amount_INR": [500, 500], "Period": ["Q2", "Q2"], "Department": ["Operations", "Operations"]})])
        cases.append(EvaluationCase("duplicate_source_row", _has_finding(duplicate, "duplicate_transaction"), "Matching source rows enter the review queue."))
        missing = run_workspace([_write_csv(root, "Missing_Actuals.csv", {"Category": ["Revenue"], "Amount_INR": [None], "Period": ["Q2"], "Department": ["Sales"]})])
        cases.append(EvaluationCase("missing_required_value", _has_finding(missing, "missing_required_value"), "An unavailable amount is identified without failing the run."))
        zero_budget = run_workspace([_write_csv(root, "Zero_Budget.csv", {"Category": ["New initiative"], "Amount_INR": [0], "Period": ["Q2"], "Department": ["Strategy"]}), _write_csv(root, "Zero_Actuals.csv", {"Category": ["New initiative"], "Amount_INR": [250], "Period": ["Q2"], "Department": ["Strategy"]})])
        percentage = zero_budget.variance.loc[0, "variance_percentage"]
        cases.append(EvaluationCase("zero_budget_safe_handling", percentage is None, "A zero budget never produces an infinite percentage."))
        cases.append(EvaluationCase("human_review_required", all(finding.requires_human_review and investigation.requires_human_review for finding, investigation in zip(material.findings, material.investigations)), "Signals and investigations remain drafts for an accountable reviewer."))
    passed = sum(case.passed for case in cases)
    return {"passed": passed, "total": len(cases), "cases": [asdict(case) for case in cases]}


if __name__ == "__main__":
    results = run_evaluation()
    print(f"Evaluation: {results['passed']}/{results['total']} passed")
    for case in results["cases"]:
        print(f"[{'PASS' if case['passed'] else 'FAIL'}] {case['name']}: {case['detail']}")
    raise SystemExit(0 if results["passed"] == results["total"] else 1)
