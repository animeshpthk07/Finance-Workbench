"""Evidence-first local finance analysis pipeline."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import pandas as pd
from .ingestion import ParsedDocument, parse_documents

@dataclass
class WorkspaceRun:
    documents: list[ParsedDocument]
    metrics: pd.DataFrame = field(default_factory=pd.DataFrame)
    variance: pd.DataFrame = field(default_factory=pd.DataFrame)
    findings: list[dict] = field(default_factory=list)
    investigations: list[dict] = field(default_factory=list)
    @property
    def errors(self):
        return [f"{d.name}: {e}" for d in self.documents for e in d.errors]

def _find(columns, choices):
    normalized = {str(c).strip().lower().replace(" ", "_"): c for c in columns}
    for choice in choices:
        if choice in normalized: return normalized[choice]
    return None

def _number(series):
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False).str.replace("$", "", regex=False), errors="coerce")

def _metrics(documents):
    rows=[]
    for doc in documents:
        if doc.frame is None or doc.frame.empty: continue
        df=doc.frame.copy(); account=_find(df.columns,["account","category","description","line_item","name"])
        period=_find(df.columns,["period","month","date","quarter"])
        budget=_find(df.columns,["budget","budget_value","planned"]); actual=_find(df.columns,["actual","actual_value","amount","value"])
        labels=df[account] if account else pd.Series(["Unclassified"]*len(df)); periods=df[period] if period else pd.Series(["Unspecified"]*len(df))
        for i in df.index:
            base={"account":str(labels.loc[i]),"period":str(periods.loc[i]),"source_file":doc.name,"source_row":int(i)+2}
            if budget: rows.append(base|{"kind":"budget","value":_number(df.loc[[i],budget]).iloc[0]})
            if actual: rows.append(base|{"kind":"actual","value":_number(df.loc[[i],actual]).iloc[0]})
    return pd.DataFrame(rows, columns=["account","period","source_file","source_row","kind","value"])

def calculate_variance_table(metrics):
    if metrics.empty: return pd.DataFrame(columns=["account","period","budget_value","actual_value","variance_amount","variance_percentage"])
    grouped=metrics.pivot_table(index=["account","period"],columns="kind",values="value",aggfunc="sum").reset_index()
    for col in ("budget","actual"):
        if col not in grouped: grouped[col]=0.0
    grouped["variance_amount"]=grouped["actual"]-grouped["budget"]
    grouped["variance_percentage"]=grouped["variance_amount"].div(grouped["budget"].replace(0,pd.NA)).mul(100).fillna(0)
    return grouped.rename(columns={"budget":"budget_value","actual":"actual_value"})

def _findings(metrics, variance):
    items=[]
    if not metrics.empty:
        for _,r in metrics[metrics.value.isna()].iterrows():
            items.append({"type":"missing_value","severity":"high","description":f"Missing numeric value for {r.account} ({r.period}).","evidence":f"{r.source_file}, row {r.source_row}"})
        dupe=metrics.duplicated(["account","period","kind","value"],keep=False)
        for _,r in metrics[dupe].drop_duplicates(["account","period","kind","value"]).iterrows():
            items.append({"type":"duplicate","severity":"medium","description":f"Possible duplicate {r.kind} record for {r.account} ({r.period}).","evidence":f"{r.source_file}, row {r.source_row}"})
    if not variance.empty:
        for _,r in variance[variance.variance_percentage.abs()>=10].iterrows():
            sev="high" if abs(r.variance_percentage)>=25 else "medium"
            items.append({"type":"variance","severity":sev,"description":f"{r.account} is {r.variance_percentage:.1f}% {'over' if r.variance_amount>0 else 'under'} budget in {r.period}.","evidence":f"Budget {r.budget_value:,.2f}; actual {r.actual_value:,.2f}"})
    return items

def _investigate(findings):
    return [{"finding_type":f["type"],"draft":"Review the cited source record, validate the period and account mapping, then approve or correct the finding.","evidence":f["evidence"],"requires_human_review":True} for f in findings]

def run_workspace(sources: list[Any]) -> WorkspaceRun:
    documents=parse_documents(sources); metrics=_metrics(documents); variance=calculate_variance_table(metrics); findings=_findings(metrics,variance)
    return WorkspaceRun(documents,metrics,variance,findings,_investigate(findings))

def markdown_report(run: WorkspaceRun) -> str:
    lines=["# Finance Workbench Report","",f"Documents reviewed: {len(run.documents)}",f"Metrics extracted: {len(run.metrics)}",f"Findings requiring review: {len(run.findings)}","","## Findings"]
    lines += [f"- **{f['severity'].title()} — {f['type']}**: {f['description']} Evidence: {f['evidence']}" for f in run.findings] or ["- No material exceptions detected."]
    lines += ["","All outputs are review drafts; a finance professional must validate conclusions before use."]
    return "
".join(lines)
