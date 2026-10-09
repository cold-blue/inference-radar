# Inference Radar

A personal intelligence radar for LLM inference acceleration engineers.

## What it does

- Collects recent GitHub PRs/releases from inference-related repositories
- Collects recent arXiv papers for inference/serving/kernel/MoE/KV-cache topics
- Deduplicates items
- Uses an OpenAI-compatible LLM API to classify, score, and summarize items
- Generates a Markdown daily report
- Stores raw items and analyses in SQLite

## Quick start

```bash
cd inference-radar
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set your API key/base URL/model

python -m radar init-db
python -m radar collect
python -m radar analyze
python -m radar report
```

Or run everything:

```bash
python -m radar run
```

Report:
`reports/YYYY-MM-DD.md`

## Configuration

Edit `config.yaml`.

The initial watchlist focuses on:

- vLLM
- SGLang
- TensorRT-LLM
- FlashInfer
- CUTLASS
- Triton
- PyTorch
- NCCL
- NVIDIA Dynamo
- DeepEP
- DeepGEMM

Add/remove repositories and arXiv queries as needed.

## Environment variables

See `.env.example`.

The LLM analyzer expects an OpenAI-compatible `/chat/completions` endpoint.
It can point to OpenAI or another compatible provider/local gateway.

## Cron

Example, every day at 08:00:

```cron
0 8 * * * cd /path/to/inference-radar && /path/to/.venv/bin/python -m radar run >> radar.log 2>&1
```

## Design

```text
GitHub ─┐
arXiv  ─┼─> Collect ─> SQLite ─> Analyze ─> Rank ─> Markdown
        └─> Deduplicate
```

This is intentionally a V0.1. The next useful extensions are benchmark tracking,
GitHub merged-PR detection, RSS/blog sources, knowledge-graph relations, and
personal research-topic tracking.
