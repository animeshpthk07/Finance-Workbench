"""Streamlit interface for an evidence-first Finance Workbench."""

from pathlib import Path
import os

import pandas as pd
import streamlit as st

from backend.pipeline import WorkspaceRun, run_workspace
from backend.investigator import InvestigatorConfig, investigate_finding
from backend.reporting import build_json_report, build_markdown_report

st.set_page_config(page_title="Finance Workbench", page_icon="📊", layout="wide")
public_demo = os.getenv("FINANCE_WORKBENCH_PUBLIC_DEMO", "").lower() == "true"
ai_config = InvestigatorConfig.from_environment()
st.markdown("""<style>
.block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1500px;}
[data-testid="stMetric"] {background: #eef5fa; border: 1px solid #d9e6ee; border-radius: 12px; padding: 18px;}
[data-testid="stMetricLabel"] {color: #456174;}
[data-testid="stMetricValue"] {color: #153d52;}
</style>""", unsafe_allow_html=True)


def run_demo() -> WorkspaceRun:
    root = Path(__file__).parent
    return run_workspace([root / "Q2_Budget.xlsx", root / "Q2_Actuals.csv", root / "Q2_Report.pdf"])


def get_workspace() -> WorkspaceRun | None:
    return st.session_state.get("workspace_run")


with st.sidebar:
    st.title("📊 Finance Workbench")
    st.caption("Evidence-first financial investigation")
    page = st.radio("Workspace", ["Overview", "Investigate", "Review queue", "Report"], label_visibility="collapsed")
    st.divider()
    st.caption("PUBLIC DEMO" if public_demo else "ANALYST WORKSPACE")
    st.caption("AI drafting: available on request" if ai_config.enabled else "AI drafting: not configured · local playbooks active")
    st.caption("Code calculates. AI drafts. Finance professionals decide.")
    st.caption("Session-only workspace. Export review records before closing.")

st.title("Finance Workbench")
st.caption("Trace every signal to its evidence. Review every conclusion before acting.")

if public_demo:
    st.info("Public portfolio demo · synthetic Q2 data only. Uploads and external AI calls are disabled.")
    uploads = []
else:
    uploads = st.file_uploader("Add budget, actual, or supporting report documents", type=["csv", "xlsx", "xls", "pdf"], accept_multiple_files=True)
    st.caption("Documents are processed on the machine hosting this app, not necessarily your device. Use only data approved for that host. No external AI call is made during analysis.")
actions = st.columns([2, 2, 2])
if actions[0].button("Analyze documents", type="primary", disabled=not uploads):
    with st.spinner("Normalizing documents and building the review queue..."):
        st.session_state.workspace_run = run_workspace(uploads)
if actions[1].button("Use included Q2 demo"):
    with st.spinner("Loading the included finance documents..."):
        st.session_state.workspace_run = run_demo()

workspace = get_workspace()
if workspace is None:
    st.info("Start with the Q2 demo or upload CSV, Excel, and optional PDF reports. The default workflow is local and deterministic.")
    st.stop()

if workspace.ingestion_errors:
    st.warning("Some documents could not be fully read:")
    for error in workspace.ingestion_errors:
        st.write(f"- {error}")

if page == "Overview":
    high_priority = sum(finding.severity in {"high", "critical"} for finding in workspace.findings)
    documents, metrics, findings, reviews = st.columns(4)
    documents.metric("Documents", len(workspace.documents))
    metrics.metric("Normalized metrics", len(workspace.metrics))
    findings.metric("Findings", len(workspace.findings))
    reviews.metric("Pending reviews", len(workspace.review_queue), delta=f"{high_priority} high priority", delta_color="inverse")

    st.subheader("Document intake")
    intake = pd.DataFrame([{
        "Document": document.name,
        "Type": document.kind.upper(),
        "Rows extracted": 0 if document.frame is None else len(document.frame),
        "PDF text captured": len(document.text),
    } for document in workspace.documents])
    st.dataframe(intake, width="stretch", hide_index=True)

    st.subheader("Deterministic budget versus actual")
    if workspace.variance.empty:
        st.info("Upload budget and actual files to generate a variance comparison.")
    else:
        st.dataframe(workspace.variance, width="stretch", hide_index=True)
        if workspace.variance["currency"].nunique() == 1:
            st.bar_chart(workspace.variance.set_index("metric_name")[["budget_value", "actual_value"]], color=["#97b8ca", "#087f8c"])
        else:
            st.caption("Multiple currencies detected; no combined chart or currency conversion is shown.")

elif page == "Investigate":
    st.subheader("Evidence-linked investigation drafts")
    if not workspace.findings:
        st.success("No deterministic signals crossed the configured review threshold.")
    for index, (finding, investigation) in enumerate(zip(workspace.findings, workspace.investigations)):
        with st.expander(f"[{finding.severity.upper()}] {finding.title}", expanded=finding.severity in {"high", "critical"}):
            st.write(finding.description)
            st.write(investigation.summary)
            st.markdown("**Evidence**")
            for evidence in finding.evidence:
                st.code(f"{evidence.source_file} · {evidence.source_location or 'source'}\n{evidence.source_text or evidence.relevance or ''}")
            st.markdown("**Observed facts**")
            for fact in investigation.facts:
                st.write(f"- {fact}")
            st.markdown("**Draft interpretations to validate**")
            for interpretation in investigation.interpretations:
                st.write(f"- {interpretation}")
            st.markdown("**Verification checks**")
            for check in investigation.verification_checks:
                st.write(f"- {check}")
            st.markdown("**Recommended verification step**")
            st.write(investigation.recommended_next_step)
            st.caption(f"Draft source: {investigation.generation_mode}. All interpretations require human validation.")
            if investigation.model_error:
                st.warning(investigation.model_error)
            with st.popover("Show AI investigation prompt"):
                st.caption("This exact prompt is sent to OpenAI only when you authorize the optional draft below. Up to 12 truncated evidence excerpts are included.")
                st.code(investigation.llm_ready_prompt)
            if ai_config.enabled:
                consent = st.checkbox("I am authorized to send this finding and the shown evidence to OpenAI; API charges may apply.", key=f"ai-consent-{finding.finding_id}")
                if st.button("Generate optional AI draft", key=f"ai-draft-{finding.finding_id}", disabled=not consent):
                    with st.spinner("Requesting one evidence-linked draft..."):
                        workspace.investigations[index] = investigate_finding(finding, ai_config)
                    st.rerun()

elif page == "Review queue":
    st.subheader("Human review queue")
    st.caption("Review status records workflow only; it does not approve or post any financial action.")
    for finding in workspace.findings:
        with st.container(border=True):
            left, right = st.columns([4, 1])
            left.markdown(f"**{finding.title}**")
            left.caption(f"{finding.description} · Severity: {finding.severity.title()}")
            reviewed = right.checkbox("Reviewed", value=finding.review_status == "reviewed", key=f"reviewed-{finding.finding_id}")
            finding.review_status = "reviewed" if reviewed else "pending"
            finding.reviewer_note = st.text_area("Reviewer note", value=finding.reviewer_note, key=f"note-{finding.finding_id}", placeholder="Add a verified explanation or next action.", max_chars=4000)

else:
    st.subheader("Exportable investigation draft")
    report = build_markdown_report(workspace)
    downloads = st.columns(2)
    downloads[0].download_button("Download Markdown report", data=report, file_name="finance-workbench-investigation-draft.md", mime="text/markdown")
    downloads[1].download_button("Download JSON review record", data=build_json_report(workspace), file_name="finance-workbench-review-record.json", mime="application/json")
    st.markdown(report)
