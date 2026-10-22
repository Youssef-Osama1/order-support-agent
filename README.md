# Order Support Agent

[![CI](https://github.com/Youssef-Osama1/order-support-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Youssef-Osama1/order-support-agent/actions/workflows/ci.yml)

A customer support agent that answers order questions by calling tools over order data, built on a hand-written tool-calling loop.

Send a customer message and the agent decides which tools to call, runs them against the order
data, and replies from the results in the customer's language.

## How It Works

1. **Ask**: the model gets the message and three tools: `get_order`, `check_return_eligibility`
   and `get_return_policy`.
2. **Run**: Python validates the arguments, runs the tool and sends the result back.
3. **Repeat**: until the model replies with text, or stops after `AGENT_MAX_STEPS` calls.

The customer's email is bound to the tools in Python, so the model only passes an order number
and cannot read another customer's order. Return eligibility is computed in Python, not by the model.

## Quick Start

```bash
uv sync
cp .env.example .env    # add your LLM_API_KEY
uv run uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs.

## Usage

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Where is my order 1042? Can I return it?", "customer_email": "sara@example.com"}'
```

The response holds the reply and a trace of the tools called, their arguments and whether they succeeded.

| Status | Meaning |
|--------|---------|
| 200 | Reply and tool trace |
| 422 | Empty or too long message, or invalid email |
| 502 | The model made an invalid tool call, gave an empty reply, or hit the step limit |

## Development

```bash
uv run pytest                                        # tests, no network access
uv run python -m evals.run_support                   # evals against the real model
uv run python -m playground.try_support              # a few messages through the agent
```

The evals check whether the agent called the right tools with the right arguments, not only the reply.

## Docker

```bash
docker build -f docker/Dockerfile -t order-support-agent .
docker run --rm -p 8000:8000 --env-file .env order-support-agent
```

The image installs runtime dependencies only, includes `data/orders.json`, runs as a
non-root user and listens on `$PORT` (default 8000). `.env` is never copied into the
image, so secrets are passed at run time. Values in `.env` must not be quoted for
`--env-file`.

## CI and Deployment

Every push to `main` and every pull request runs `.github/workflows/ci.yml`: ruff lint,
ruff format check, pytest and a Docker build.

The app runs on Render as a Docker web service:

| Setting | Value |
|---|---|
| Dockerfile path | `./docker/Dockerfile` |
| Build context | `.` |
| Health check path | `/health` |
| Auto-deploy | After CI checks pass |
| Environment | `LLM_API_KEY`, `TODAY_OVERRIDE` (other settings have defaults) |

`TODAY_OVERRIDE` fixes the date used for return eligibility, so answers match the sample
orders. Without it, eligibility is checked against the real date and return windows close
over time.

## Project Structure

```text
├── .github/          # CI workflow
├── app/
│   ├── api/          # Routes, dependencies and request/response models
│   ├── config/       # Settings loaded from .env
│   ├── core/         # Logging and exceptions
│   ├── prompts/      # System prompt and tool descriptions
│   ├── repositories/ # Order data lookups
│   ├── schemas/      # Order and return policy models
│   ├── services/     # LLM client, agent loop and support service
│   ├── tools/        # Order tools
│   └── main.py       # FastAPI app entry point
├── data/             # Sample orders and return policies
├── docker/           # Dockerfile
├── docs/             # Documentation files
├── evals/            # Eval cases and runner
├── playground/       # Experimental code, never imported by app/
├── tests/            # Tests that run without network access
├── .env.example      # Environment variables template
├── pyproject.toml    # Project dependencies and metadata
└── uv.lock           # Locked dependencies
```
