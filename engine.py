import pandas as pd
from pydantic import BaseModel
from typing import List
from collections import defaultdict

class FinancialMetric(BaseModel):
    metric_name: str
    value: float
    currency: str = "INR"
    period: str
    department: str
    source_file: str

class Inconsistency(BaseModel):
    issue_type: str
    severity: str
    description: str
    evidence: List[str]

def process_files(uploaded_files):
    metrics = []
    for file in uploaded_files:
        filename = file.name
        try:
            if filename.endswith('.xlsx'):
                df = pd.read_excel(file)
            elif filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                continue
                
            for index, row in df.iterrows():
                try:
                    metrics.append(FinancialMetric(
                        metric_name=row['Category'],
                        value=row['Amount_INR'],
                        period=row['Period'],
                        department=row['Department'],
                        source_file=filename
                    ))
                except:
                    pass
        except:
            pass
    return metrics

def calculate_variance(metrics):
    if not metrics: return pd.DataFrame()
    df = pd.DataFrame([m.model_dump() for m in metrics])
    
    budget_df = df[df['source_file'].str.contains('Budget')].copy()
    actuals_df = df[df['source_file'].str.contains('Actuals')].copy()
    
    if budget_df.empty or actuals_df.empty: return pd.DataFrame()
    
    budget_summary = budget_df.groupby('metric_name')['value'].sum().reset_index().rename(columns={'value': 'Budget_Value'})
    actuals_summary = actuals_df.groupby('metric_name')['value'].sum().reset_index().rename(columns={'value': 'Actual_Value'})
    
    variance_report = pd.merge(budget_summary, actuals_summary, on='metric_name', how='outer').fillna(0)
    variance_report['Variance_Amount'] = variance_report['Actual_Value'] - variance_report['Budget_Value']
    variance_report['Variance_Percentage'] = variance_report.apply(
        lambda row: (row['Variance_Amount'] / row['Budget_Value'] * 100) if row['Budget_Value'] != 0 else 0, axis=1
    ).round(2)
    
    return variance_report

def run_detective(metrics):
    findings = []
    seen = {}
    
    for m in metrics:
        key = (m.metric_name, m.department, m.period, m.source_file)
        if key in seen:
            findings.append(Inconsistency(
                issue_type="Duplicate Transaction",
                severity="High",
                description=f"Multiple entries found for '{m.metric_name}' in '{m.department}'.",
                evidence=[f"Source: {m.source_file}", f"Value: {m.value:,.0f} {m.currency}"]
            ))
        else:
            seen[key] = m
            
        if m.period != "Q2 FY2026":
            findings.append(Inconsistency(
                issue_type="Date/Period Mismatch",
                severity="Medium",
                description=f"Unexpected period ({m.period}) for '{m.metric_name}'.",
                evidence=[f"Source: {m.source_file}", f"Found: {m.period}"]
            ))
            
    grouped = defaultdict(list)
    for m in metrics:
        grouped[(m.metric_name, m.department, m.period)].append(m)
        
    for key, m_list in grouped.items():
        if len(m_list) > 1:
            base_val = m_list[0].value
            if any(m.value != base_val for m in m_list):
                evidence = [f"{m.source_file} -> {m.value:,.0f}" for m in m_list]
                findings.append(Inconsistency(
                    issue_type="Cross-Document Mismatch",
                    severity="High",
                    description=f"Conflicting values for '{key[0]}' across files.",
                    evidence=evidence
                ))
    return findings
