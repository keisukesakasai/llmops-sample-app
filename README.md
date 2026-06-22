# Budget Guru – LLMOps Sample App

A sample application demonstrating how to build, instrument, and evaluate an
LLM-powered investment assistant using **Datadog Agent Observability** (LLM
Observability) and **Datadog LLM Experiments / Datasets**.

## Overview

| Component | Description |
|---|---|
| `app/` | FastAPI chat API ("Budget Guru") |
| `experiments/` | Offline evaluation runner with Datadog Experiments integration |
| `datasets/` | Sample Q&A CSV for evaluation |

## Prerequisites

- Python 3.11+
- An OpenAI-compatible API key (or a local/proxy endpoint)
- A Datadog account with an API key, APP key, and your site (e.g. `datadoghq.com`)

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and edit the environment file
cp .env.example .env       # then fill in your keys
```

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | API key for the LLM provider |
| `OPENAI_BASE_URL` | No | `https://api.openai.com` | Custom base URL for OpenAI-compatible APIs |
| `LLM_MODEL` | No | `gpt-4.1` | Model identifier |
| `DD_API_KEY` | Yes (LLM Obs) | — | Datadog API key |
| `DD_APP_KEY` | Yes (Experiments) | — | Datadog APP key |
| `DD_SITE` | No | `datadoghq.com` | Datadog site (e.g. `us5.datadoghq.com`) |
| `DD_LLMOBS_ENABLED` | No | `false` | Enable LLM Observability tracing |
| `DD_LLMOBS_ML_APP` | No | `budget-guru-ml-app` | ML app name shown in the Datadog UI |
| `DD_LLMOBS_PROJECT_NAME` | No | `budget-guru-experiments` | Experiments project name |
| `DD_LLMOBS_AGENTLESS_ENABLED` | No | `false` | Send traces directly (no local Agent) |
| `DD_TRACE_ENABLED` | No | `true` | Enable APM tracing |

## Running the Chat API

```bash
uvicorn app.main:app --reload
```

### Health check

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### Chat endpoint

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-001",
    "message": "What is the difference between stocks and bonds?",
    "prompt_variant": "P4"
  }'
```

Expected response:

```json
{
  "answer": "Stocks are pieces of ownership in a company ...",
  "prompt_variant": "P4",
  "model": "gpt-4.1"
}
```

The `prompt_variant` field selects one of four system prompts (P1–P4) defined
in `app/prompts.py`.  Switching variants lets you compare answer styles in the
Datadog LLM Observability UI.

## Datadog LLM Observability

1. Set `DD_LLMOBS_ENABLED=true` and provide `DD_API_KEY` / `DD_SITE`.
2. Start the app (`uvicorn app.main:app`).
3. Send a few `/chat` requests.
4. Open **Datadog → LLM Observability → Traces** to see span details,
   token counts, latency, and model metadata.

When `DD_LLMOBS_AGENTLESS_ENABLED=false` (default), traces are forwarded via a
locally running Datadog Agent.  Set it to `true` to send directly to the
Datadog intake endpoint (no Agent required).

## Running Offline Experiments

```bash
python -m experiments.run_experiments \
  --dataset ./datasets/budget_guru_investment_qa.csv \
  --models model_A model_B \
  --prompts P1 P2 P3 P4
```

### Expected console output

```
INFO Dataset loaded: 8 records
INFO Datadog dataset_id: dummy-dataset-id-00000000
INFO Running experiment: model_A/P1 (8 records)
INFO   record=1 scores={'exact_match': 0.0, 'contains_keywords': 0.72, 'information_accuracy': 0.5, 'brand_voice_consistency': 1.0}
...

======================================================
Budget Guru – Experiments Summary
======================================================
Experiment                 exact_match  contains_keywords  information_accuracy  brand_voice_consistency
------------------------------------------------------
model_A/P1                      0.0000             0.7200                0.5000                   1.0000
model_A/P4                      0.0000             0.7500                0.5000                   1.0000
...
======================================================
```

### Dataset

`datasets/budget_guru_investment_qa.csv` contains 8 sample investment Q&A rows
with the following columns:

| Column | Description |
|---|---|
| `id` | Unique row ID |
| `input` | User question |
| `expected_output` | Ideal reference answer |
| `topic` | Subject area (e.g. `etf`, `bonds`) |
| `difficulty` | `beginner` or `intermediate` |
| `age_group` | Target age range |

## Customization Guide

| What to change | Where |
|---|---|
| System prompts (P1–P4) | `app/prompts.py` |
| LLM provider / model | `app/config.py` + env vars |
| Evaluator logic | `experiments/evaluators.py` |
| Add new evaluators | `experiments/evaluators.py` → add to `EVALUATORS` dict |
| Datadog Dataset upload | `experiments/datasets.py` → `create_or_get_dataset_in_datadog()` |
| Datadog Experiments logging | `experiments/run_experiments.py` → `log_experiment_result_to_datadog()` |

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Environment variable config
│   ├── llm_client.py              # LLM abstraction layer
│   ├── prompts.py                 # System prompt variants P1–P4
│   └── datadog_instrumentation.py # Datadog APM + LLM Obs init
├── experiments/
│   ├── __init__.py
│   ├── datasets.py                # CSV loader + Datadog Dataset stub
│   ├── evaluators.py              # Deterministic + LLM-as-a-judge evaluators
│   └── run_experiments.py         # CLI Experiments runner
├── datasets/
│   └── budget_guru_investment_qa.csv
├── requirements.txt
└── README.md
```
