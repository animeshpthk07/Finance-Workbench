# Finance Workbench

An evidence-first workspace for finance teams to investigate source documents, calculate financial signals, and prepare review-ready explanations.

> Calculations are deterministic. The optional AI step produces a clearly labelled draft. Every finding requires human review.

## What it does

`Upload → Parse → Normalize → Calculate → Detect → Link evidence → Investigate → Explain → Review`

- Reads CSV, XLSX/XLS, and searchable PDF documents.
- Compares budget, actual, and forecast data with traceable variance calculations.
- Detects material variances, missing values, duplicate source rows, and statistical outliers.
- Links each signal to source rows and relevant PDF excerpts.
- Produces a deterministic investigation playbook; an OpenAI draft is available only after explicit configuration.
- Provides a professional Streamlit workbench, human review queue, and downloadable Markdown report draft.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
streamlit run app.py
```

Use the included `Q2_Actuals.csv`, `Q2_Budget.xlsx`, and `Q2_Report.pdf` to explore the demo workflow.

## Optional AI investigation draft

The application stays deterministic by default. To enable an explicit AI draft, configure both environment values:

```bash
OPENAI_API_KEY=your_key
FINANCE_WORKBENCH_AI_MODEL=your_model
```

Facts and cited evidence remain separate from model interpretation. The app does not submit transactions, change records, or make autonomous finance decisions.

## Quality and documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Validation and reliability](docs/VALIDATION.md)
- [Project validation record](docs/PROJECT_VALIDATION.md)

Run checks locally:

```bash
pytest -q
python evaluation.py
```

## Project structure

```text
app.py                    Streamlit analyst workbench
backend/ingestion.py      CSV, Excel, and PDF parsing
backend/normalization.py  Transparent column mapping
backend/pipeline.py       End-to-end deterministic workflow
backend/investigator.py   Evidence-grounded investigation drafts
backend/reporting.py      Review-ready Markdown report
backend/models/           Typed finance records and evidence contracts
evaluation.py             Portable reliability scenarios
```

## Boundaries

This is a decision-support prototype, not an accounting system or audit opinion. Validate all findings against the linked source evidence before acting.
