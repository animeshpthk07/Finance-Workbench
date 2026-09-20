# Validation and reliability

Run the regression suite:

```bash
pytest -q
```

Run the portable evaluation scenarios:

```bash
python evaluation.py
```

The evaluation covers a correct low-variance case, material cross-document variance, duplicate rows, missing values, zero-budget safety, and mandatory human review. The tests also check source evidence, PDF evidence attachment, deterministic investigator grounding, and report wording.

## Known limits

- Header mapping is transparent but is not a substitute for a customer-specific chart-of-accounts mapping.
- PDF extraction supplies searchable supporting text; it does not guarantee table reconstruction.
- The optional model creates a review draft, not an audit conclusion. Reviewers validate all interpretations against cited evidence.
- Threshold calibration and performance should be evaluated against representative, approved historical data before operational use.
