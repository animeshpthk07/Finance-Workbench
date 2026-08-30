import pandas as pd


def detect_duplicate_transactions(
    df: pd.DataFrame,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Detect duplicate transactions in a financial DataFrame.

    Parameters
    ----------
    df:
        Transaction DataFrame.

    columns:
        Columns used to identify duplicate transactions.
        If None, pandas' complete-row duplicate detection is used.

    Returns
    -------
    pd.DataFrame
        Rows identified as duplicates.
    """

    if df.empty:
        return df.copy()

    if columns:
        missing_columns = [
            column for column in columns
            if column not in df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing columns: {missing_columns}"
            )

        mask = df.duplicated(
            subset=columns,
            keep=False,
        )
    else:
        mask = df.duplicated(
            keep=False,
        )

    return df.loc[mask].copy()
