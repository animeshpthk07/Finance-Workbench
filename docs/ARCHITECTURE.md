# Architecture

```text
CSV / XLSX / XLS / PDF
          |
          v
Local ingestion and normalization
          |
          +--> PDF text is retained as supporting evidence
          v
Deterministic calculations and checks
- budget vs actual variance
- missing values
- duplicate source rows
- statistical outliers
          |
          v
Evidence-linked findings
          |
          +--> optional OpenAI investigation draft (explicit opt-in)
          v
Human review queue --> Markdown / JSON review record
```

`backend/pipeline.py` is the single primary workflow. `engine.py` contains separate legacy notebook-era helpers; the application does not use it.

## Safety boundaries

- Calculations and detection are deterministic Python code.
- A PDF passage is attached only when it directly names a finding metric; it never becomes a calculated value.
- Normal analysis never calls OpenAI. Both `OPENAI_API_KEY` and `FINANCE_WORKBENCH_AI_MODEL` must be configured, public-demo mode must be off, and the reviewer must consent and request one draft explicitly in the UI.
- Public-demo mode disables uploads and server-funded AI; documents on other hosted instances are processed on their host, not in the viewer's browser.
- Structured AI outputs are type-checked, bounded to 2,000 output tokens and a 45-second SDK timeout. Failure retains the deterministic playbook.
- Model text is an interpretation, distinct from evidence-derived facts.
- Every finding and investigation requires human review. The app cannot post transactions, approve entries, or make autonomous decisions.
