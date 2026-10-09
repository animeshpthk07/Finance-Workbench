# Deployment and optional AI setup

## Live portfolio demo

[Open Finance Workbench](https://finance-workbench-otea96uvyvjtkud27u4a9k.streamlit.app/).

The public portfolio should use synthetic data only. Set the following in Streamlit's app settings under **Secrets** (TOML):

```toml
FINANCE_WORKBENCH_PUBLIC_DEMO = "true"
```

When enabled, this disables document uploads and server-funded AI requests. Do not put an API key in an anonymous public demo. The expected app configuration is `animeshpthk07/Finance-Workbench`, branch `main`, entrypoint `app.py`; verify those values and public-demo mode in the hosting account before publishing. Source checks do not establish the live host's configuration. Python 3.12 is the verified runtime.

For a fresh deployment, select that repository, branch, entrypoint and Python version in Community Cloud. Source changes on the selected branch redeploy automatically. See the [official Streamlit deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

## Run the full analyst workspace locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The application processes documents on its hosting machine. Local hosting keeps parsing on your own computer; a hosted instance receives uploaded files on that server. Review state is per-session and not a durable database. Export Markdown or JSON before closing. There is no JSON import or identity-verified audit trail in this release.

## Input limits and parser boundaries

`backend.ingestion.IngestionLimits` defines the following defaults. Both `parse_document` and `parse_documents` enforce them; callers can supply a stricter immutable limits object. These are code-level options, not environment variables or user-facing settings.

| Input | Default limit |
| --- | --- |
| Files per batch | 10 |
| Raw bytes per file / per batch | 20 MiB / 40 MiB |
| Table rows / columns | 50,000 / 100 |
| XLSX archive members | 512 |
| Expanded bytes per XLSX member / archive | 16 MiB / 64 MiB |
| XLSX member expansion ratio | 200:1 |
| PDF pages | 50 |
| Decoded PDF page content / total content streams | 4 MiB / 16 MiB |
| Extracted PDF text, including page separators | 1,000,000 characters |

Files are read in bounded chunks. A capacity violation rejects the entire batch with a visible error and no partial analysis; invalid formats retain per-file errors. Tables are checked after reading at most one row beyond the limit, and only the first Excel worksheet is used. Archive metadata and actual expanded member sizes are checked before Excel parsing. A ZIP-based workbook renamed `.xls` receives the same archive checks as `.xlsx`. Explicit `openpyxl` and `xlrd` engines prevent automatic selection of unrelated spreadsheet formats; encrypted workbook archives are rejected.

These controls reduce accepted workload but do not bound every parser allocation or execution time. ZIP directory parsing, Excel shared strings/styles, wide CSV tables and legacy XLS structures can allocate memory before the relevant checks. PDF page discovery, decompression and text extraction can also allocate memory before their size checks. There is no isolated parsing worker, OS-enforced memory quota or hard timeout. Keep uploads restricted to approved users until authentication, rate limits and process-level resource isolation are in place. The public-demo flag is a feature switch, not authentication.

Markdown report exports escape untrusted text so source values and reviewer notes cannot inject report links, images or HTML. JSON preserves exact original content. This output protection does not sanitize other user interfaces or turn source content into trusted evidence.

## Optional OpenAI draft — private/local use

1. Choose a Responses API model available to your account that supports structured JSON outputs.
2. Set an API spending limit in your provider account before enabling paid requests.
3. Configure `OPENAI_API_KEY` and `FINANCE_WORKBENCH_AI_MODEL` as environment variables, or in an untracked `.streamlit/secrets.toml` for Streamlit. `.env.example` is documentation, not an automatic loader.
4. Leave public-demo mode off only on an approved private/local deployment.
5. Analyze the included synthetic demo. In **Investigate**, inspect **Show AI investigation prompt**, consent to sending that finding to OpenAI, and click **Generate optional AI draft**.

Each click requests one draft: up to 12 evidence excerpts, a 2,000-output-token cap, a 45-second SDK timeout and no automatic retries. Normal analysis, navigation and report export never call the model. An outage, refusal, incomplete or malformed output retains the deterministic playbook. The displayed draft source indicates whether the model actually succeeded.

The integration uses the [official OpenAI Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create), structured JSON and `store=False`. This does not promise zero provider retention or make the output an audited financial conclusion. Never send confidential financial evidence without authorization for that destination.

Real secrets belong only in a local ignored file or [Streamlit secrets settings](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management), never in GitHub, notebooks, screenshots or chat messages. A live paid request was not part of the automated release checks; simulated success, malformed output and outages are tested.

## Containers

```bash
docker build -t finance-workbench .
docker run --rm -p 8501:8501 -e FINANCE_WORKBENCH_PUBLIC_DEMO=true finance-workbench
```

The Docker recipe is supplied for portability; this release was tested with Python/Streamlit, not a Docker daemon. Keep uploads private and add authentication, quotas, durable storage, representative evaluation and operational monitoring before a production deployment.
