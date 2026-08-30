import streamlit as st
from engine import process_files, calculate_variance, run_detective

st.set_page_config(page_title="Finance Workbench", layout="wide", page_icon="📊")

with st.sidebar:
    st.title("📊 Finance Workbench")
    st.caption("AI-Powered Analysis")
    st.divider()
    page = st.radio("Navigation", ["Dashboard", "Data Detective"])
    st.divider()
    st.caption("Status: Deterministic Engine Online")

st.title("Q2 Performance Analysis")
st.markdown("Upload your financial documents to begin deterministic variance analysis.")

uploaded_files = st.file_uploader(
    "Upload Financial Data (Budget & Actuals)", 
    type=["csv", "xlsx"], 
    accept_multiple_files=True
)

if uploaded_files:
    with st.spinner("Parsing files and running Data Detective..."):
        metrics = process_files(uploaded_files)
        variance_df = calculate_variance(metrics)
        findings = run_detective(metrics)
        
        high_priority = sum(1 for f in findings if f.severity == "High")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Files Analyzed", len(uploaded_files))
        col2.metric("Metrics Extracted", len(metrics))
        col3.metric("Inconsistencies", len(findings), delta=f"-{high_priority} High Priority", delta_color="inverse")
        col4.metric("Human Reviews", high_priority)
        
        st.divider()
        
        if not variance_df.empty:
            st.subheader("📊 Variance Analysis (Deterministic)")
            st.dataframe(variance_df, use_container_width=True, hide_index=True)
        
        if findings:
            st.subheader("🚨 Detective Findings & Evidence")
            for finding in findings:
                with st.expander(f"[{finding.severity}] {finding.issue_type}"):
                    st.write(finding.description)
                    st.write("**Evidence Trail:**")
                    for ev in finding.evidence:
                        st.code(ev)
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Files Analyzed", 0)
    col2.metric("Metrics Extracted", 0)
    col3.metric("Inconsistencies", 0)
    col4.metric("Human Reviews", 0)
    st.info("No active workspace. Please upload Q2_Budget.xlsx and Q2_Actuals.csv to begin.")
