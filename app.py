"""Finance Workbench — evidence-first review workspace."""
from pathlib import Path
import pandas as pd
import streamlit as st
from backend.pipeline import markdown_report, run_workspace

st.set_page_config(page_title="Finance Workbench", page_icon="📊", layout="wide")
st.title("📊 Finance Workbench")
st.caption("Investigate budget, actual, CSV, Excel, and PDF evidence. AI-style drafts are always subject to human review.")

if "run" not in st.session_state: st.session_state.run = None
with st.sidebar:
    st.header("Documents")
    uploads = st.file_uploader("Upload finance documents", type=["csv", "xlsx", "xls", "pdf"], accept_multiple_files=True)
    demo = st.checkbox("Use included Q2 sample files")
    if st.button("Analyze documents", type="primary"):
        sources = uploads or []
        if demo:
            sources = [Path(name) for name in ("Q2_Budget.xlsx", "Q2_Actuals.csv", "Q2_Report.pdf") if Path(name).exists()]
        if not sources:
            st.warning("Upload one or more supported files, or choose the included sample data.")
        else:
            with st.spinner("Extracting evidence and calculating variances..."):
                st.session_state.run = run_workspace(sources)

run = st.session_state.run
if not run:
    st.info("Start by uploading documents or using the included Q2 data. Nothing is sent to an external service.")
    st.stop()

if run.errors:
    for error in run.errors: st.error(error)
metrics, variance, findings = run.metrics, run.variance, run.findings
c1, c2, c3, c4 = st.columns(4)
c1.metric("Documents", len(run.documents))
c2.metric("Metrics extracted", len(metrics))
c3.metric("Review findings", len(findings))
c4.metric("Variance rows", len(variance))

overview, investigate, review, export = st.tabs(["Overview", "Investigate", "Review queue", "Report"])
with overview:
    st.subheader("Budget vs actual")
    if variance.empty: st.info("No matching budget/actual rows were available for a variance calculation.")
    else:
        show = variance.copy()
        for col in ("budget_value", "actual_value", "variance_amount", "variance_percentage"):
            show[col] = show[col].round(2)
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.bar_chart(show.set_index("account")["variance_amount"])
with investigate:
    st.subheader("Evidence-led investigation drafts")
    if not findings: st.success("No material exceptions crossed the configured review threshold.")
    for index, finding in enumerate(findings, 1):
        with st.expander(f"{finding['severity'].title()} · {finding['type'].replace('_',' ')}", expanded=True):
            st.write(finding["description"])
            st.caption("Evidence: " + finding["evidence"])
            st.info("Suggested next step: validate the source record, account mapping, and period before accepting this draft.")
with review:
    st.subheader("Human review required")
    if findings:
        for index, finding in enumerate(findings, 1):
            st.selectbox(f"Finding {index}: {finding['type']}", ["Pending review", "Confirmed", "Dismissed", "Needs follow-up"], key=f"review_{index}")
    st.caption("This workspace does not make financial decisions or finalize approvals.")
with export:
    st.subheader("Review-ready outputs")
    st.download_button("Download investigation report", markdown_report(run), "finance-workbench-report.md", "text/markdown")
    if not variance.empty:
        st.download_button("Download variance table", variance.to_csv(index=False), "variance-analysis.csv", "text/csv")
    if not metrics.empty:
        st.download_button("Download extracted metrics", metrics.to_csv(index=False), "extracted-metrics.csv", "text/csv")
