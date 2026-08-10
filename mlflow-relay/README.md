# AISHA MLflow relay

The relay is the authenticated third stage in AISHA's protected telemetry path:

`local bounded JSONL → batch shipper → authenticated relay → separate MLflow server`

It accepts privacy-safe schema-v2 operation metadata, validates closed experiment/tag/metric values, and maps accepted events to MLflow. It must never receive Hire identifiers, conversation or policy text, certificate content, OCR/extracted values, diagnosis, filename, document fingerprint, or raw errors. Product operations remain successful when logging, shipping, relay, or MLflow fails.

## Delivery contract

- Random `event_id` values provide retry-stable idempotency.
- Batch responses partially acknowledge accepted, retryable, and permanently rejected events.
- Duplicate accepted event IDs do not create duplicate MLflow runs.
- Authentication uses a shared bearer secret and privacy-safe errors.
- MLflow remains separately hosted and is not exposed through this API.
- Fixed experiments and allowlisted tags/metrics prevent content from being encoded into arbitrary names.

The sender sanitizes legacy v1 records into the v2 allowlist, quarantines invalid records, retries only appropriate events, and enforces seven-day/100 MB local retention.

## Run locally

```bash
uv sync
export RELAY_SHARED_SECRET='dev-secret'

# terminal 1
uv run mlflow server \
  --backend-store-uri sqlite:///./data/mlflow.db \
  --default-artifact-root ./data/artifacts \
  --host 127.0.0.1 --port 5000

# terminal 2
uv run uvicorn relay.api:app --host 127.0.0.1 --port 8080
```

Set the AISHA sender's `STAI_LOG_SERVER_URL` to `http://<relay-host>:8080/log-batch` and configure the same secret. Only the relay API needs an externally reachable port; keep the MLflow tracking API localhost-only or on an internal container network.

## Docker deployment

```bash
docker compose -f deploy/docker-compose.yml up -d
```

The included compose file keeps `mlflow-server` internal. The optional Caddy configuration can add HTTPS for an authorized deployment. For systemd/LXC, install `deploy/mlflow-server.service` and `deploy/mlflow-relay-api.service`; retain the same network separation.

## Verify

```bash
uv run pytest
curl http://127.0.0.1:8080/health
```

End-to-end verification should use a valid schema-v2 fixture from the parent repository tests rather than entering user content into a manual request.
