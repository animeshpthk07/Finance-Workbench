"""Column normalization with source-level traceability."""
from __future__ import annotations

import re
from typing import Iterable
import pandas as pd
from backend.models import FinancialMetric

COLUMN_ALIASES = {
    "metric_name": {"metricname", "metric", "category", "account", "accountname", "description", "item"},
    "value": {"amountinr", "amount", "value", "amountvalue", "actualamount", "budgetamount"},
    "period": {"period", "quarter", "month", "fiscalperiod", "reportingperiod"},
    "department": {"department", "costcenter", "businessunit", "team"},
    "currency": {"currency", "currencycode"},
    "unit": {"unit", "units", "measure"},
    "entity": {"entity", "company", "legalentity"},
    "transaction_id": {"transactionid", "transaction", "id", "invoiceid", "reference"},
}


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _rename_columns(frame: pd.DataFrame) -> pd.DataFrame:
    aliases = {alias: canonical for canonical, values in COLUMN_ALIASES.items() for alias in values}
    renamed: dict[object, str] = {}
    used: set[str] = set()
    for column in frame.columns:
        candidate = aliases.get(_key(column), str(column).strip())
        if candidate not in used:
            renamed[column] = candidate
            used.add(candidate)
    return frame.rename(columns=renamed).copy()


def infer_record_type(filename: str) -> str:
    lowered = filename.lower()
    if "budget" in lowered or "plan" in lowered or "forecast" in lowered:
        return "budget"
    if "actual" in lowered or "ledger" in lowered or "transaction" in lowered:
        return "actual"
    return "source"


def normalize_frame(frame: pd.DataFrame, source_file: str, record_type: str | None = None) -> pd.DataFrame:
    data = _rename_columns(frame)
    if "metric_name" not in data.columns:
        data["metric_name"] = ""
    if "value" not in data.columns:
        data["value"] = pd.NA
    for column, default in {"period": "Unspecified period", "department": "Unspecified department", "currency": "INR", "unit": "", "entity": ""}.items():
        if column not in data.columns:
            data[column] = default
        data[column] = data[column].fillna(default).astype(str).str.strip()
    data["metric_name"] = data["metric_name"].fillna("").astype(str).str.strip()
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data["record_type"] = record_type or infer_record_type(source_file)
    data["source_file"] = source_file
    data["source_location"] = [f"row {index + 2}" for index in range(len(data))]
    return data.reset_index(drop=True)


def rows_to_metrics(frame: pd.DataFrame) -> list[FinancialMetric]:
    metrics: list[FinancialMetric] = []
    for row in frame.to_dict(orient="records"):
        if pd.isna(row["value"]):
            continue
        metrics.append(FinancialMetric(metric_name=row["metric_name"], value=float(row["value"]), currency=row["currency"] or "INR", unit=row["unit"] or None, period=row["period"] or None, department=row["department"] or None, entity=row["entity"] or None, record_type=row["record_type"], source_file=row["source_file"], source_location=row["source_location"], source_text=f"{row['metric_name']}: {float(row['value']):,.2f} {row['currency']}"))
    return metrics


def normalize_frames(frames: Iterable[tuple[pd.DataFrame, str]]) -> pd.DataFrame:
    normalized = [normalize_frame(frame, name) for frame, name in frames]
    return pd.concat(normalized, ignore_index=True) if normalized else pd.DataFrame()
