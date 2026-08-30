from typing import Optional


def calculate_variance(
    actual: float,
    budget: float
) -> float:
    """
    Absolute variance between actual and budget.
    """
    return actual - budget


def calculate_variance_percentage(
    actual: float,
    budget: float
) -> Optional[float]:
    """
    Percentage variance between actual and budget.
    """
    if budget == 0:
        return None

    return ((actual - budget) / abs(budget)) * 100


def calculate_growth(
    current: float,
    previous: float
) -> Optional[float]:
    """
    Period-over-period growth percentage.
    """
    if previous == 0:
        return None

    return ((current - previous) / abs(previous)) * 100


def calculate_margin(
    profit: float,
    revenue: float
) -> Optional[float]:
    """
    Profit margin percentage.
    """
    if revenue == 0:
        return None

    return (profit / revenue) * 100
