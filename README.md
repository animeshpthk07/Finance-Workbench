# 📊 Finance Workbench

### AI-Powered Financial Analysis, Data Investigation, and Workflow Assistant

Finance Workbench is an enterprise-grade AI workspace designed to augment finance professionals. It automates repetitive spreadsheet preparation, cross-document reconciliation, variance analysis, and data-cleaning tasks while keeping humans strictly responsible for judgment and final decision-making.

---

## 🏛️ Core Architecture Principle

> **Deterministic Computation > AI Reasoning**

The system uses standard vectorized Python/Pandas logic for arithmetic, totals, and variance reconciliation, and strictly limits AI/LLMs to document interpretation, anomaly investigation explanation, and management report drafting. 

---

## 🚀 Key Features

* **Deterministic Variance Engine:** Computes Budget vs. Actuals, absolute variances, and percentage changes without LLM math errors.
* **Data Detective:** Automatically scans ingested files for duplicate transactions, date mismatches, and unit variances.
* **Cross-Document Evidence System:** Cross-references data across Excel (`.xlsx`), CSV (`.csv`), and PDF (`.pdf`) files, tracking exact source trails and cell/page locations.
* **AI Investigator:** Generates contextual explanations for detected inconsistencies with configurable confidence scores.
* **Human-in-the-Loop Review Controls:** Every AI output and draft report is explicitly flagged as `AI-generated draft — human review required`.

---

## 🛠️ Technology Stack

* **Backend:** Python, FastAPI, Pandas, Pydantic
* **Frontend:** Streamlit (Python-native enterprise UI)
* **AI Layer:** OpenAI API (Configurable via environment variables)
* **Document Processing:** Openpyxl, PyPDF, ReportLab

---
