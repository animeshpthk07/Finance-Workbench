from typing import List
from backend.models.schemas import FinancialMetric, Finding, Evidence


def reconcile_metrics(
    metrics: List[FinancialMetric],
    tolerance: float = 0.01
) -> List[Finding]:

    findings = []

    grouped = {}

    for metric in metrics:
        key = (
            metric.metric_name.lower().strip(),
            metric.period,
            metric.entity
        )

        grouped.setdefault(key, []).append(metric)

    for key, items in grouped.items():

        if len(items) < 2:
            continue

        reference = items[0]

        for item in items[1:]:

            difference = abs(reference.value - item.value)

            if difference > tolerance:

                findings.append(
                    Finding(
                        finding_type="numerical_mismatch",
                        title=f"Numerical mismatch: {reference.metric_name}",
                        description=(
                            f"{reference.metric_name} differs between "
                            f"{reference.source_file} and "
                            f"{item.source_file}."
                        ),
                        severity="high",
                        metric_name=reference.metric_name,
                        expected_value=reference.value,
                        observed_value=item.value,
                        difference=difference,
                        evidence=[
                            Evidence(
                                source_file=reference.source_file or "Unknown",
                                source_location=reference.source_location
                            ),
                            Evidence(
                                source_file=item.source_file or "Unknown",
                                source_location=item.source_location
                            ),
                        ],
                        requires_human_review=True,
                    )
                )

    return findings
