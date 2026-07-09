# mlflow-relay

Receives batched chat-turn logs POSTed by the STAI repo's
`src/stai/log_shipper.py` and replays each one into MLflow as a run. Runs on
a separate, dedicated server from the STAI demo box - see the parent repo's
`README.md` "Shipping logs to a remote MLflow relay" section for the sender
side.

## Why this exists

The STAI box has no spare inbound ports to run an MLflow UI locally. Instead
of pointing an MLflow client directly at a remote tracking server (blocked -
that box can't `pip install mlflow` or reach arbitrary hosts), it POSTs a
small JSON batch to the one pre-approved URL this relay exposes, and this
relay does the real `mlflow` client calls server-side.

## Run locally

```powershell
uv sync
$env:RELAY_SHARED_SECRET = "dev-secret"

# in one terminal: the real mlflow backend + UI
uv run mlflow server --backend-store-uri sqlite:///./data/mlflow.db `
  --default-artifact-root ./data/artifacts --host 127.0.0.1 --port 5000

# in another: the relay
uv run uvicorn relay.api:app --host 127.0.0.1 --port 8080 --reload
```

## Deploy

### With Docker

Plain-IP mode (no domain/TLS needed - just an open port on the host):

```powershell
docker compose -f deploy/docker-compose.yml up -d
```

Point the STAI box's `STAI_LOG_SERVER_URL` at
`http://<this-host>:8080/log-batch`. `mlflow-server` stays internal-only
(OSS MLflow's own tracking API has no auth), so it's not reachable directly -
`docker compose exec` or an SSH tunnel to view the UI in this mode.

Add HTTPS + a browsable UI later by uncommenting the `caddy` service in
`deploy/docker-compose.yml` and filling in `deploy/Caddyfile`.

### Without Docker (LXC on Proxmox, matching the STAI repo's own deployment)

If this runs on an LXC container - the same style as the STAI demo box, which
also has no Docker and uses systemd directly - two units instead of two
containers, both bound to `127.0.0.1` except the one port you actually
forward:

```bash
sudo useradd --system --home /opt/mlflow-relay mlflow-relay
sudo mkdir -p /opt/mlflow-relay/data
sudo chown -R mlflow-relay:mlflow-relay /opt/mlflow-relay

cd /opt/mlflow-relay
git clone <this-project> .        # or copy the mlflow-relay/ folder over
uv sync
cp .env.example .env              # fill in RELAY_SHARED_SECRET
```

```powershell
sudo cp deploy/mlflow-server.service deploy/mlflow-relay-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mlflow-server mlflow-relay-api
```

Only `mlflow-relay-api` needs an external/NAT-forwarded port (8080 in the
unit file) - `mlflow-server` binds `127.0.0.1` only, same reasoning as the
Docker path's `expose:` (no `ports:`). Add an entry to this LXC's NAT table
alongside the STAI repo's existing `2143 -> 7860` / `2163 -> 8000` forwards,
e.g. `2183 -> 8080`, and point `STAI_LOG_SERVER_URL` at
`http://<lxc-host>:2183/log-batch`.

To view the MLflow UI (port 5000, localhost-only by design) without adding
another forwarded port, SSH-tunnel instead:

```powershell
ssh -L 5000:127.0.0.1:5000 <lxc-user>@<lxc-host> -p <ssh-forward-port>
# then open http://127.0.0.1:5000 locally
```

## Verify end-to-end

```powershell
curl http://127.0.0.1:8080/health

curl -X POST http://127.0.0.1:8080/log-batch `
  -H "Authorization: Bearer dev-secret" -H "Content-Type: application/json" `
  -d '{"runs":[{"experiment_name":"smoke-test","run_name":"manual-curl","start_time_ms":1751000000000,"end_time_ms":1751000001500,"tags":{"route":"api"},"metrics":{"latency_ms":1500}}]}'

# open http://127.0.0.1:5000 -> experiment "smoke-test" -> run "manual-curl"
```

## Tests

```powershell
uv run pytest
```
