# PPE comparison

A small English-language assistant for the supplied Polish investment KIDs. It
compares documented strategy, risks, costs and holding terms against stated
preferences, with Polish quotations and access to the original PDFs. It does not
choose an investment or prescribe allocations.

## Run locally

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Configure your Azure OpenAI deployment in your private `.env`:

```dotenv
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-resource-key
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_REASONING_EFFORT=medium
```

Copy the endpoint and key from your Azure resource. Use the resource root endpoint,
without `/openai/deployments/...` or `/chat/completions`. The deployment value is
the **deployment name in Azure**, which may differ from the model name. Select a
deployment supporting Chat Completions and strict JSON-schema output;
set an API version supported by that resource and deployment.
Reasoning effort defaults to `medium`. Native JSON-schema output allows the
configured model to reason while producing validated structured answers. Set
`AZURE_OPENAI_REASONING_EFFORT=` (empty) to omit this parameter for deployments
that do not accept it.
For key authentication, leave `AZURE_OPENAI_AD_TOKEN` unset.

Conversation requests use Azure endpoint and key authentication through
`AzureChatOpenAI`. The `langchain-openai` and `openai` packages remain because they
provide the Azure client; no OpenAI account or direct OpenAI API connection is
used (see the [SDK's Azure support](https://developers.openai.com/api/reference/python#azure-openai)).

```powershell
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

Open [the app](http://127.0.0.1:8502). PDFs in `info/KID` are parsed locally once
when the app initializes, before questions are accepted. Every rerun and chat
shares the fixed catalogue; restart the app to ingest different documents.
Questions and selected Polish evidence are sent to the configured Azure deployment.
One model request plans retrieval, the read-only tools run once, and another
request produces the validated answer. One final repair is allowed (three calls maximum).

LLM instructions live in `ppe/prompts/`: `policy.txt`, `route.txt`, `answer.txt`
and `repair.txt`. Tool descriptions are in `tool_descriptions.json` in the same
folder. Restart the app after editing these files.

## Docker and tracing

With Docker running and `.env` configured:

```powershell
docker compose up --build -d
docker compose ps
# Stop services while preserving traces:
docker compose down
```

The app uses port **8502** and MLflow uses **5001**, both bound to loopback.
Compose mounts the PDFs read-only and persists MLflow data. Evidence stays in memory.
No secrets, PDFs, slides or development documents are baked into the image.

Local tracing is optional. For a local tracking server:

```powershell
uv run mlflow server --host 127.0.0.1 --port 5001 --backend-store-uri sqlite:///mlflow.db --artifacts-destination ./mlartifacts
```

Use `MLFLOW_TRACKING_URI=http://127.0.0.1:5001` for host runs; Compose supplies
the internal URL. Default traces contain operational metadata. Set
`PPE_TRACE_CONTENT=true` explicitly to persist questions, answers and evidence, or
`PPE_TRACING_ENABLED=false` to disable tracing. Tracing outages do not block answers.

## Checks and troubleshooting

```powershell
uv run ruff check .
uv run ruff format --check .
docker compose config --quiet
```

A live conversation requires valid
Azure credentials and an accessible deployment; offline checks do not establish
deployment access or model compatibility.

If chat is disabled, fill in all four Azure settings and restart the app. For
authentication failures, check that the key belongs to the configured resource.
For deployment-not-found errors, check the Azure deployment name and resource
endpoint. For unsupported API or structured-output errors, check the API version
and deployment capabilities. For rate limits, check the deployment's Azure quota.

Compose passes the same private `.env` to the app. After changing it, recreate the
app container with `docker compose up -d --force-recreate app`.

## Project documentation

See [Architecture decisions](ADR.md) for the design choices and trade-offs, and
[Future plans](FUTURE_PLANS.md) for planned improvements.
