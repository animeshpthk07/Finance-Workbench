# Portfolio presentation kit

## 90-second demonstration

1. **0–15 seconds — Problem.** Finance reviewers need to understand a signal and trace it back to a source, not just read a generated explanation.
2. **15–35 seconds — Overview.** Load the included Q2 demo. Show the CSV, Excel and supporting PDF, normalized rows, variance table and chart.
3. **35–60 seconds — Investigation.** Open the Travel finding. Inspect its source rows, the supporting PDF excerpt, observed facts, hypotheses and verification checks. Explain why duplicate rows may affect the total and why a reviewer must validate the cause.
4. **60–75 seconds — Review.** Mark one finding reviewed and record a sample note. This records workflow, not a transaction approval.
5. **75–90 seconds — Export and boundaries.** Download Markdown or JSON with evidence and review notes. Explain the optional, consent-gated AI draft and the current limits: no OCR, no durable multi-user database and no claim of real-world detection accuracy.

## LinkedIn draft — prepared, not posted

I built Finance Workbench, an evidence-first financial investigation prototype in Python and Streamlit.

The workflow connects CSV/Excel/PDF intake, deterministic calculations, anomaly checks, source-linked investigations, human review and report export. The included demo highlights duplicate transactions, a material variance and mismatched reporting periods.

One design choice matters especially to me: code owns the calculations; AI only drafts interpretations. The optional OpenAI step requires an explicit action, and observed facts remain separate from unverified hypotheses. The app never approves or posts transactions.

I also added automated regression checks, repeatable evaluation scenarios, a synthetic demo, and exportable reviewer notes. This is a working portfolio prototype—not an accounting system or an audit opinion. Representative financial-data evaluation, OCR and durable multi-user review are future work.

Try the demo: https://finance-workbench-otea96uvyvjtkud27u4a9k.streamlit.app/

Code and validation: https://github.com/animeshpthk07/Finance-Workbench

#Python #Streamlit #FinancialAnalytics #DataAnalytics #AI

## Resume/project description

**Finance Workbench — evidence-first financial investigation prototype**

- Built a Python/Streamlit workflow for CSV, Excel and searchable PDF evidence, budget-versus-actual calculations, anomaly checks, investigations and human review.
- Implemented source-linked findings, explicitly authorized optional AI drafts, deterministic fallback and portable Markdown/JSON review records.
- Added regression and app-navigation checks, synthetic evaluation scenarios, deployment guidance and a public demonstration.

Use screenshots from `docs/screenshots/` alongside the demo. Do not describe mocked AI checks as live model validation, or synthetic scenario pass rates as measured production accuracy.
