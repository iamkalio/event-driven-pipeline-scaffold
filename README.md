# Intro

This project is a production-grade scaffold for a runtime platform backend. It demonstrates high-volume Kafka ingestion, a Redis-backed stream join and idempotency layer, PostgreSQL storage with partitioning-aware repositories, multi-tier AI processing hooks, alert fan-out to Slack and Jira, and a FastAPI surface for dashboards and health checks.

## Architecture

- `src/ingestion`: source-specific event normalization and a resilient Kafka producer.
- `src/streaming`: manual-commit Kafka consumer base, retry policy, DLQ publisher, and runtime pipeline bootstrap.
- `src/processing`: join, idempotency, enrichment, threat evaluation, and orphan handling services.
- `src/storage`: asyncpg pool lifecycle and repository-only SQL access.
- `src/alerting`: alert deduplication and async delivery adapters.
- `src/api`: dashboard-oriented read endpoints and dependency wiring.
- `src/observability`: JSON logging and Prometheus metrics objects.

## Local development

1. Copy `.env.example` to `.env` and adjust values for your machine.
2. Run `uv sync` to install dependencies.
3. Start infrastructure with `docker compose up -d postgres redis zookeeper kafka prometheus`.
4. Apply the bootstrap schema with `infra/postgres/init.sql` or let your preferred migration runner execute `src/storage/migrations/001_initial.sql`.
5. Start the API with `uv run uvicorn src.main:app --host 0.0.0.0 --port 8000`.
6. Start the consumer with `uv run python -m src.streaming.router`.

## Notes

- The schema includes a `runtime_event_registry` helper table because PostgreSQL partitioned tables cannot enforce a standalone `PRIMARY KEY (id)` and `UNIQUE (event_id)` without including the partition key.
- The AI modules are intentionally scaffolded around inference contracts only. They are ready for generated gRPC stubs, but do not include model training or production authn/authz flows.
