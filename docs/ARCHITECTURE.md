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
Human review queue --> Markdown report draft
```

`backend/pipeline.py` is the single primary workflow. `engine.py` remains only as a compatibility layer for the original notebook-era helpers.

## Safety boundaries

- Calculations and detection are deterministic Python code.
- A PDF passage is attached only when it directly names a finding metric; it never becomes a calculated value.
- The OpenAI enhancement is disabled unless both `OPENAI_API_KEY` and `FINANCE_WORKBENCH_AI_MODEL` are explicitly configured.
- Model text is an interpretation, distinct from evidence-derived facts.
- Every finding and investigation requires human review. The app cannot post transactions, approve entries, or make autonomous decisions.
