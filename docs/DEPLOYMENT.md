# Deployment: local, Docker Compose and Kubernetes

[Leer en Español](DEPLOYMENT.es.md)

This document covers three ways to run the app: directly on your machine, with Docker Compose
(backend + frontend + PostgreSQL), and on Kubernetes (Kustomize manifests, tested layout for
kind/minikube/Docker Desktop, production-shaped overlay).

> **Honesty note.** The container images, the Compose file and the Kubernetes manifests were
> written and statically validated (YAML syntax, Kubernetes schemas, cross-reference checks,
> `bash -n`, PowerShell parser) on a machine **without Docker or Kubernetes**. They have not been
> built or applied yet. See [What has been verified](#what-has-been-verified) for the exact list
> and the commands to run on your own machine.

## Architecture

```
                       browser
                          |
                          v
              +-----------------------+
              | Ingress (nginx)       |   k8s only; compose publishes the frontend directly
              | body 4097m, timeout 900s
              +-----------+-----------+
                          |  /
                          v
              +-----------------------+
              | frontend  (nginx, :8080)
              |  - serves the React SPA
              |  - /api/*  --proxy-->  |
              +-----------+-----------+
                          |  http://backend:8000
                          v
              +-----------------------+
              | backend  (FastAPI/uvicorn, :8000)
              |  /api/health, analysis endpoints
              |  /tmp (emptyDir)  /app/data/storage (volume/PVC)
              +-----------+-----------+
                          |  postgresql+psycopg://...@postgres:5432/motorsport
                          v
              +-----------------------+
              | postgres 16 (StatefulSet / compose service, 1 instance)
              +-----------------------+
```

The browser only talks to one origin. The production frontend build calls the relative path
`/api` (`import.meta.env.PROD` without `VITE_API_URL`); nginx forwards it to the backend, so no
CORS is involved. In development the frontend still calls `http://localhost:8000/api` directly.

### Environment contract

| Variable | Used by | Default (local) | In containers |
|---|---|---|---|
| `MAX_UPLOAD_MB` | backend, frontend nginx, Ingress | `2048` | same value everywhere (per file) |
| `CORS_ORIGINS` | backend | localhost:5173/3000 | origin(s) of the UI if the API is called cross-origin |
| `LOG_LEVEL` | backend | `INFO` | `INFO` |
| `TEMP_DIR` | backend | `./tmp` | `/tmp/motorsport-analytics` (tmpfs / emptyDir) |
| `DATABASE_URL` | backend (library/DB features) | `sqlite:///data/motorsport.db` | `postgresql+psycopg://user:pass@postgres:5432/motorsport` |
| `STORAGE_DIR` | backend | `./data/storage` | `/app/data/storage` (volume / PVC) |
| `AC_SETUPS_DIR` | backend | Assetto Corsa setups folder | usually unset; optional read-only bind mount |
| `UVICORN_WORKERS` | container entrypoint | n/a | `1` |
| `RUN_MIGRATIONS` | container entrypoint | n/a | `1` in compose runs `alembic upgrade head` on start |

`MAX_UPLOAD_MB` is enforced for real: the backend rejects an upload larger than the limit with
HTTP 413 (translated message, partial file deleted) while streaming it to disk, and rejects
requests whose `Content-Length` is clearly above it. nginx derives `client_max_body_size` as
`2 x MAX_UPLOAD_MB + 1` MB (a comparison request carries two files). The Ingress annotation
`proxy-body-size` (`4097m`) is set by hand: change it together with the ConfigMap.

## 1. Local, without Docker

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

cd frontend && npm install && npm run dev            # http://localhost:5173
```

Optional: run `VITE_API_URL=/api npm run dev` and Vite proxies `/api` to
`VITE_PROXY_TARGET` (default `http://localhost:8000`), so the browser stays same-origin like in
production.

## 2. Docker Compose

Requirements: Docker Engine / Docker Desktop with Compose v2.

```bash
cp .env.example .env          # edit POSTGRES_PASSWORD; values in the example are NOT for production
docker compose up --build -d
docker compose ps             # wait until backend is "healthy"
# UI: http://localhost:8080   (FRONTEND_PORT in .env)
```

Shortcuts: `make up | down | logs | test | lint` (Linux/macOS/WSL) or
`.\scripts\dev.ps1 up | down | logs | test | lint` (PowerShell).

What you get:

- `postgres`: `postgres:16-alpine`, named volume `pgdata`, `pg_isready` healthcheck, only on an
  internal network (not reachable from the host).
- `backend`: built from `Dockerfile` (multi-stage, non-root uid 10001, read-only root filesystem,
  tmpfs `/tmp`, volume `storage`), waits for a healthy Postgres, runs migrations if `alembic.ini`
  exists. Not published to the host by default.
- `frontend`: nginx-unprivileged on `:8080`, waits for a healthy backend.
- Memory/CPU limits per service (backend 4 GiB, 2 CPUs).

Dev profile (hot reload backend in a container, frontend with local Vite):

```bash
docker compose --profile dev up postgres backend-dev     # API on http://127.0.0.1:8010
cd frontend && VITE_API_URL=http://localhost:8010/api npm run dev
```

Assetto Corsa setups folder (read-only): copy `docker-compose.override.example.yml` to
`docker-compose.override.yml`, edit the host path, and restart.

Reset everything including data: `docker compose down -v`.

## 3. Kubernetes with Kustomize

Layout:

```
k8s/
  base/                 namespace, ServiceAccount, ConfigMap, Postgres StatefulSet (+headless Service),
                        backend (PVC, Service, Deployment with migrate initContainer, HPA, PDB),
                        frontend (Service, Deployment, PDB), Ingress, NetworkPolicies
  overlays/local/       kind/minikube/Docker Desktop: 1 replica, :dev images, throwaway Secret, host localhost
  overlays/prod/        2+ replicas, bigger resources, TLS (cert-manager placeholder), RWX storage, HPA 2-6
```

The base never contains a real Secret. `overlays/local` generates a throwaway one;
`overlays/prod` expects you to create `motorsport-db` yourself (`secret.example.yaml`,
`externalsecret.example.yaml`; sealed-secrets or external-secrets recommended). Because the
database URL is assembled from the three keys, use only URL-safe characters in the password.

### kind (recommended for a first test)

Requirements: Docker, [kind](https://kind.sigs.k8s.io/), kubectl.

```bash
make kind-up                       # or: bash scripts/kind-up.sh   |   .\scripts\kind-up.ps1
```

The script creates the cluster (`scripts/kind-cluster.yaml`, host port 8088 -> ingress 80),
installs ingress-nginx, builds `motorsport-backend:dev` and `motorsport-frontend:dev`, loads
them with `kind load docker-image`, applies `k8s/overlays/local` and waits for the rollouts.
Then open <http://localhost:8088>.

Manual equivalent:

```bash
kind create cluster --name motorsport --config scripts/kind-cluster.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.2/deploy/static/provider/kind/deploy.yaml
docker build -t motorsport-backend:dev . && docker build -t motorsport-frontend:dev ./frontend
kind load docker-image motorsport-backend:dev motorsport-frontend:dev --name motorsport
kubectl apply -k k8s/overlays/local
kubectl -n motorsport get pods -w
```

### minikube / Docker Desktop Kubernetes

- minikube: `minikube addons enable ingress`, build into its daemon with
  `minikube image build -t motorsport-backend:dev .` (and the frontend), then
  `kubectl apply -k k8s/overlays/local` and `minikube tunnel`; use `http://localhost`.
- Docker Desktop: enable Kubernetes, install ingress-nginx
  (`.../provider/cloud/deploy.yaml`), build the images with `docker build` (they are visible to the
  cluster directly), apply the local overlay, open `http://localhost`.
- No ingress at all: `kubectl -n motorsport port-forward svc/frontend 8080:80`.

### Production-shaped overlay

1. Push images to a registry; set `images:` in `overlays/prod/kustomization.yaml`
   (`ghcr.io/OWNER/...` is a placeholder; nothing is published today and there is no CI).
2. Create the `motorsport-db` Secret (see above) in the `motorsport` namespace.
3. Set your host in `ingress-patch.yaml` and the CORS value in the kustomization; install
   cert-manager and a ClusterIssuer if you want automatic TLS.
4. Choose an RWX StorageClass in `storage-patch.yaml` (or drop the replicas to 1).
5. `kubectl apply -k k8s/overlays/prod`

Render without applying: `kubectl kustomize k8s/overlays/prod`.

## What is production-ready and what is NOT

Reasonable already:

- Non-root containers, read-only root filesystems, dropped capabilities, seccomp RuntimeDefault,
  namespace Pod Security `restricted`.
- Probes (startup/readiness/liveness), resource requests and limits, PodDisruptionBudgets, HPA,
  default-deny NetworkPolicies, no secrets in git, pinned/overridable image tags.
- Same-origin proxy with long timeouts and enforced upload limit.

NOT production-ready (be upfront about this):

- **No authentication or authorization.** Anyone who can reach the URL can upload and analyse.
  Put it behind a VPN, an authenticating proxy (oauth2-proxy) or add auth before exposing it.
- **PostgreSQL is a single StatefulSet replica**: no replication, backups or failover. Use a
  managed database or an operator (CloudNativePG, Zalando) for anything that matters, and set
  up backups. `DATABASE_URL` is all the backend needs.
- **Backend replicas and in-memory analysis.** Each analysis runs in the memory of the replica that
  receives the request and is returned in the response; there is no shared cache or session
  state. Several replicas work for independent requests, but memory per pod must fit your largest
  CSV (limits default to 4 GiB; prod 8 GiB) and `UVICORN_WORKERS` multiplies that.
  Library files in `STORAGE_DIR` need an RWX volume once there is more than one replica.
- **Migrations run in an initContainer.** Fine for 1 replica; with several replicas starting
  together two migrations could race. For strict production run `alembic upgrade head` as a
  separate Job (or Helm/Argo pre-sync hook) before the rollout.
- Autoscaling by CPU does not capture memory spikes of large uploads. No metrics, tracing or
  log aggregation are configured. No rate limiting.
- NetworkPolicies are only enforced by CNIs that support them (not kind's default).
- Images are not scanned or signed; no registry or CI pipeline is set up (deliberately).

## What has been verified

Done on a machine without Docker/Kubernetes:

- `python scripts/validate_k8s.py`: YAML parses; selectors vs labels; Service ports vs container
  ports; ConfigMap/Secret/PVC references and keys; probes; volumes; HPA/PDB/NetworkPolicy targets;
  overlay patch targets; security rules (also run by `tests/test_k8s_manifests.py`).
- `kubernetes-validate` strict schema validation of the base objects against Kubernetes 1.30.
- `yamllint` on `k8s/`, `docker-compose.yml` and the override example; compose file parsed with PyYAML.
- Unit tests for the upload limit (`tests/test_upload_limit.py`), real code path in `main.py`.
- Syntax check of `kind-up.sh` (`bash -n`) and the PowerShell scripts (parser).

NOT verified (needs Docker/kind): image builds, container start-up and healthchecks, nginx
template rendering and proxying, `docker compose config/up`, Kustomize rendering
(`kubectl kustomize`), server-side validation, probes and read-only filesystems at runtime,
NetworkPolicy behaviour, Alembic migrations in the cluster (depends on the database feature
being merged: `alembic.ini` and `psycopg` in `requirements.txt`), ingress-nginx version URL.

Commands to run once Docker Desktop / kind are installed:

```bash
docker compose config -q                                   # compose syntax and variables
docker build -t motorsport-backend:dev . && docker build -t motorsport-frontend:dev ./frontend
docker run --rm motorsport-backend:dev python -c "import xgboost, reportlab, matplotlib"
docker compose up --build -d && curl -f http://localhost:8080/api/health
kubectl kustomize k8s/overlays/local | kubectl apply --dry-run=server -f -   # after kind-up
make kind-up && kubectl -n motorsport get pods
```

Optional extra linters: `hadolint Dockerfile frontend/Dockerfile`, `kubeconform`, `trivy config .`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `POSTGRES_PASSWORD` error on `docker compose up` | You did not create `.env` (`cp .env.example .env`). |
| Upload fails with 413 | File above `MAX_UPLOAD_MB` (backend) or body limit (nginx/Ingress). Raise all of them together. |
| Analysis returns 504 / connection reset | A proxy timeout is shorter than the analysis: check `PROXY_TIMEOUT`, Ingress `proxy-read-timeout`, load balancer idle timeout. |
| Backend pod `OOMKilled` | Memory limit smaller than the CSV needs; raise limits, lower `UVICORN_WORKERS`. |
| Pod `CrashLoopBackOff` in `migrate` init | `alembic.ini` missing from the image, wrong DB credentials, or Postgres not ready yet (`kubectl logs <pod> -c migrate`). |
| `ImagePullBackOff` locally | Image not loaded into the cluster: `kind load docker-image ...`; tags must be `:dev`. |
| 404/502 at `http://localhost:8088` | Ingress controller not ready (`kubectl -n ingress-nginx get pods`) or frontend not ready. |
| nginx: `host not found in upstream "backend"` | The frontend started outside the compose/cluster network or without the backend Service. |
| `kubectl apply` of prod overlay: secret not found | Create `motorsport-db` first. |
| Frontend in dev cannot reach API | Backend on :8000? CORS_ORIGINS includes the Vite origin? Or use `VITE_API_URL=/api`. |

## Security notes

- The example credentials in `.env.example` and the local overlay are throwaway values for a
  laptop. Never reuse them. `.env` is git-ignored.
- Do not commit real Secrets; use sealed-secrets or external-secrets.
- Containers run as non-root with a read-only root filesystem; writable paths are `/tmp` and the
  storage volume only.
- nginx sends `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy` and a Content-Security-Policy (allows Google Fonts, which the UI loads).
  Add HSTS at the TLS-terminating layer (Ingress/load balancer).
- The app has no authentication yet (see above); do not expose it to the internet as is.
