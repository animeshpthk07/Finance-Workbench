import pandas as pd

from backend.detective.duplicates import (
    detect_duplicate_transactions,
)

from backend.detective.anomalies import (
    detect_missing_values,
)

from backend.detective.reconciliation import (
    reconcile_columns,
)


def test_duplicate_detection():

    df = pd.DataFrame({
        "transaction_id": [
            "TX001",
            "TX002",
            "TX001",
        ],
        "amount": [
            100,
            200,
            100,
        ],
    })

    result = detect_duplicate_transactions(
        df,
        columns=["transaction_id"],
    )

    assert len(result) == 2


def test_missing_value_detection():

    df = pd.DataFrame({
        "transaction_id": [
            "TX001",
            "TX002",
        ],
        "amount": [
            100,
            None,
        ],
    })

    result = detect_missing_values(df)

    assert len(result) == 1


def test_reconciliation():

    df = pd.DataFrame({
        "budget": [
            100,
            200,
        ],
        "actual": [
            100,
            250,
        ],
    })

    result = reconcile_columns(
        df,
        "budget",
        "actual",
    )

    assert len(result) == 1
