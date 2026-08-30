import pandas as pd


def detect_missing_values(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return rows containing one or more missing values.
    """

    if df.empty:
        return df.copy()

    mask = df.isna().any(axis=1)

    return df.loc[mask].copy()


def detect_negative_values(
    df: pd.DataFrame,
    column: str,
) -> pd.DataFrame:
    """
    Detect negative values in a numeric financial column.
    """

    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found."
        )

    mask = pd.to_numeric(
        df[column],
        errors="coerce"
    ) < 0

    return df.loc[mask].copy()
  
