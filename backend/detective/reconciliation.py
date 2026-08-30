import pandas as pd


def reconcile_columns(
    df: pd.DataFrame,
    first_column: str,
    second_column: str,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """
    Compare two numerical columns and return rows
    where the values differ beyond the allowed tolerance.
    """

    required_columns = [
        first_column,
        second_column,
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    result = df.copy()

    result["_difference"] = (
        pd.to_numeric(
            result[first_column],
            errors="coerce",
        )
        -
        pd.to_numeric(
            result[second_column],
            errors="coerce",
        )
    )

    result["_absolute_difference"] = (
        result["_difference"].abs()
    )

    return result.loc[
        result["_absolute_difference"] > tolerance
    ].copy()
