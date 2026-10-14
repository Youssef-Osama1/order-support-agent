# Order Support Agent

A customer support agent that answers order questions by calling tools over order data, built on a hand-written tool-calling loop.

## Quick Start

```bash
uv sync
cp .env.example .env    # add your LLM_API_KEY
uv run uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs.

## Project Structure

```text
├── app/
│   ├── api/          # Routes, dependencies and request/response models
│   ├── config/       # Settings loaded from .env
│   ├── core/         # Logging and exceptions
│   ├── prompts/      # System prompts
│   ├── schemas/      # Pydantic models the LLM fills in
│   ├── services/     # LLM client and business logic
│   └── main.py       # FastAPI app entry point
├── docker/           # Docker configurations
├── docs/             # Documentation files
├── evals/            # Datasets for measuring output quality
├── playground/       # Experimental code, never imported by app/
├── tests/            # Tests that run without network access
├── .env.example      # Environment variables template
├── pyproject.toml    # Project dependencies and metadata
└── uv.lock           # Locked dependencies
```

## Adding a Use Case

Add a schema in `app/schemas/`, a prompt in `app/prompts/`, and a service in `app/services/`
that calls `LLMClient.extract`. Then expose it through an endpoint in `app/api/endpoints/`.
