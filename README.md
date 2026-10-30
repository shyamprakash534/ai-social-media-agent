# Orbit Social — AI Social Media Agent

LinkedIn-first AI social content MVP. See the full setup and deployment details in this repository.

## Stack
- Next.js + React + TypeScript dashboard
- FastAPI + Python backend
- LangGraph workflow with human approval checkpoint
- PostgreSQL, Redis, Celery worker and scheduler
- Optional OpenAI and Slack integrations
- LinkedIn OAuth and text-post publishing adapter

## Quick start
1. Copy `.env.example` to `.env` and replace the secrets.
2. Run `docker compose up --build`.
3. Open http://localhost:3000 and API docs at http://localhost:8000/docs.

Default publishing mode is `demo`; no external social post is created unless explicitly configured for live LinkedIn publishing.

## Scope and security
This is a single-workspace portfolio/MVP, not a hardened multi-tenant SaaS. The dashboard/API do not currently implement user login or role-based access control. Do not expose it publicly for real use until authentication and authorization are added. Live publishing is LinkedIn text-only; other platforms are draft-only.

## Deployment
A Render Blueprint is provided in `render.yaml`. Review it and configure secrets such as `OPENAI_API_KEY`, LinkedIn credentials, and Slack credentials in Render before using those integrations. Keep `PUBLISH_MODE=demo` until LinkedIn OAuth and posting permissions have been verified.
