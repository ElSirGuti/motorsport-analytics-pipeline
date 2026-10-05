# Deployment: local, Docker Compose and Kubernetes

[Leer en Español](DEPLOYMENT.es.md)

This document covers three ways to run the app: directly on your machine, with Docker Compose
(backend + frontend + PostgreSQL), and on Kubernetes (Kustomize manifests, tested layout for
kind/minikube/Docker Desktop, production-shaped overlay).

> **Verification status.** Docker Compose (PostgreSQL 16 + backend + frontend) and Kubernetes on
> kind (overlay `local`) were **built and run** on the author's machine (Windows 11, Docker Desktop,
> kind). The production overlay, HPA/PDB/NetworkPolicy enforcement, cert-manager/TLS, ExternalSecrets
> and multi-replica performance were **not** exercised. See
> [Verification done and pending](#verification-done-and-pending) for the exact list.

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
| `LAPTIME_HISTORY_DB` | backend | `<STORAGE_DIR>/laptime_history.db` if `STORAGE_DIR` is set, else `./data/laptime_history.db` | unset: the lap-history SQLite file lives in the `storage` volume. Set it only to put it elsewhere (the folder is created on demand and must be writable) |
| `UVICORN_WORKERS` | container entrypoint | n/a | `1` |
| `RUN_MIGRATIONS` | container entrypoint | n/a | `1` in compose runs `alembic upgrade head` on start |
| `UPLOAD_DIR` | backend | `<STORAGE_DIR>/uploads` if `STORAGE_DIR` is set, else `<TEMP_DIR>/uploads` | unset (uses the `storage` volume / PVC) |
| `UPLOAD_TTL_HOURS` | backend | `24` | uploads unused for this long are deleted |
| `SESSION_CACHE_MAX_MB` | backend | `1024` | per process; keep below the pod memory limit minus one analysis |
| `SESSION_CACHE_TTL_MIN` | backend | `60` | idle time before a parsed session leaves memory |
| `CORNER_DETECTION` | backend | `map` | `map` = every endpoint takes its corners from the unified corner map (`docs/CORNER_DETECTION.md`); `legacy` = the previous per-module detectors, to compare or to roll back. Read on every request; in `legacy` the response has no `corner_map` object |
| `API_HOST` / `API_PORT` / `API_RELOAD` | `python main.py` | `0.0.0.0` / `8000` / `false` | not used (the entrypoint starts uvicorn on 8000); `API_RELOAD=true` only for development |
| `VITE_API_URL` | frontend build / Vite | `http://localhost:8000/api` | the production build uses the relative `/api` when it is unset |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | compose | `motorsport` / `change-me-local-only` / `motorsport` | the password is **required** (compose refuses to start without it); example values are for local use only |
| `FRONTEND_PORT` | compose | `8080` | host port where the UI is published |
| `BACKEND_DEV_PORT` | compose (`dev` profile) | `8010` | host port of `backend-dev` (bound to 127.0.0.1) |
| `NATIVE_MAX_ROWS` | backend | `2000000` | row cap for `.ibt` / `.ld` imports (not in `.env.example`) |
| `BACKEND_URL` / `PROXY_TIMEOUT` | frontend nginx | n/a | `http://backend:8000` / `900s` (ConfigMap in Kubernetes); `BACKEND_URL` must have no path |

In Docker Compose, `DATABASE_URL` and `STORAGE_DIR` are fixed by `docker-compose.yml` (PostgreSQL and
`/app/data/storage`), so values in `.env` for those two are ignored. `.env.example` is the reference for every
other variable.

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

Requirements: Docker Engine / Docker Desktop with Compose v2 (on Windows, see
[Windows: install the tools and repeat the verification](#windows-install-the-tools-and-repeat-the-verification)).

```bash
cp .env.example .env          # edit POSTGRES_PASSWORD; values in the example are NOT for production
docker compose up --build -d
docker compose ps             # wait until backend is "healthy"
# UI: http://localhost:8080   (FRONTEND_PORT in .env)
```

The first `docker build` of the backend takes more than 10 minutes (scientific stack); later builds use the
layer cache. In Windows PowerShell use `curl.exe` (not `curl`, which is an alias) to test
`http://localhost:8080/api/health`.

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
Then open <http://localhost:8088>. The `migrate` initContainer may fail once or twice with
`failed to resolve host postgres` while PostgreSQL starts, and then succeeds (see Troubleshooting). The namespace
enforces Pod Security `restricted`, so a debug pod without a `securityContext` is rejected: that is intended.

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

### Upload once (`file_id`) and the analysis cache

The UI uploads a session file once with `POST /api/files` and the analysis endpoints
(`analyze-session`, `stint/analyze`, `optimal-lap`, `compare-session-laps`, `telemetry/analyze`,
`setups/detect`) accept the returned `file_id` (the SHA-256 of the content) instead of the file.
Sending the file as before still works.

- **Disk is the source of truth, memory is a cache.** The file lives in `UPLOAD_DIR` (default: the
  `storage` volume in the container images). Each process keeps parsed/filtered DataFrames in an LRU
  bounded by `SESSION_CACHE_MAX_MB` with a `SESSION_CACHE_TTL_MIN` idle TTL; callers get private copies.
- **Several replicas.** Memory is never shared between pods/workers. If a replica does not have the
  frames it re-parses the stored file (a few seconds for a large CSV, then cached locally). That only
  works if all replicas see the same `UPLOAD_DIR`: use an RWX volume (or sticky sessions). Without a
  shared volume, a request that lands on a replica that never received the upload gets **HTTP 410**
  (translated message) and the UI uploads the file again and retries once, so it is slower but correct.
- **Cleanup.** Uploads older than `UPLOAD_TTL_HOURS` (by last use) are removed by a throttled
  background thread. Size the volume for roughly `uploads per day x file size`. If `UPLOAD_DIR` falls
  back to `TEMP_DIR` on a tmpfs, those files count against the pod memory.
- Analysis endpoints run in the thread pool (they no longer block the event loop); simultaneous
  requests for the same file parse it once (lock per cache key).

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

<a id="what-has-been-verified"></a>
## Verification done and pending

Tested on the author's machine: Windows 11 Home, Intel i5-11400, Python 3.11.5, Node 21, Docker Desktop
4.93 (Docker 29.8.1, Compose v5.5.1), kind v0.33.0.

### Verified end to end (Docker Compose and kind)

- **Docker Compose.** `docker compose up` starts PostgreSQL 16, backend and frontend, all healthy. The UI answers on
  <http://localhost:8080> and `/api/health` returns 200. The backend runs as uid 10001 with a read-only filesystem
  (`touch /app/x` fails). Alembic migrations were applied on a real PostgreSQL: tables `alembic_version` and
  `library_sessions`, revision `0001`.
- **Kubernetes on kind.** `scripts\kind-up.ps1` creates the cluster `motorsport`, installs ingress-nginx (controller
  v1.11.2), loads the images and applies `k8s/overlays/local`. The UI answers on <http://localhost:8088>; the
  `backend`, `frontend` and `postgres-0` pods are Running. The namespace enforces Pod Security `restricted`.
- **Performance** (Imola, 57 MB CSV): first result in about 2 s and the complete analysis in about 3 s
  (Compose 3.1 s, kind 2.6 s).

### Still NOT verified

- The production overlay (`k8s/overlays/prod`): rendered and schema-validated, never applied.
- HPA, PodDisruptionBudgets and NetworkPolicies as enforced objects (kind's default CNI does not enforce
  NetworkPolicies).
- cert-manager / TLS and ExternalSecrets.
- Performance and behaviour with several backend replicas (RWX volume, HTTP 410 fallback).

### Static validation (done)

Also validated statically with the official standalone tools: `docker compose config`, `kustomize build`
(local: 16 objects, prod: 18), `kubeconform` 1.30 strict, `hadolint`, `shellcheck`, `yamllint`, `checkov`,
`nginx -t`, and a simulation of the entrypoint. Details:

| Tool (version) | What was run | Result |
|---|---|---|
| `docker-compose` v2.29.7 | `config -q` (with `POSTGRES_PASSWORD` set) and `--profile dev config -q` | valid; without `POSTGRES_PASSWORD` it fails with the intended message |
| `kustomize` v5.8.2 | `build k8s/overlays/local` and `k8s/overlays/prod` | renders: 16 and 18 objects |
| `kubeconform` v0.8.0 | `-strict -kubernetes-version 1.30.0` on both rendered overlays | 16/16 and 18/18 valid, 0 errors, 0 skipped |
| `hadolint` v2.15.1 | `Dockerfile`, `frontend/Dockerfile` | clean after the fixes below, except DL3008 (apt packages not version-pinned: deliberate, versions drift per Debian release) |
| `shellcheck` v0.11.0 | `docker/entrypoint.sh`, `frontend/docker/15-upload-limit.envsh`, `scripts/kind-up.sh` | no findings |
| `yamllint` 1.38 | `k8s/`, compose files | clean |
| `checkov` 3.3.22 | Dockerfiles; rendered Kubernetes overlays | Dockerfiles: 157 passed, 0 failed (after adding an explicit `USER` to the frontend image). Kubernetes: 535 passed, 20 failed on local+prod, all of these accepted kinds: image not pinned by digest (CKV_K8S_43), pull policy not `Always` (CKV_K8S_15; `Always` would break kind-loaded local images), secrets as env vars instead of files (CKV_K8S_35), UID below 10000 for the frontend (101) and PostgreSQL (70), imposed by the upstream images (CKV_K8S_40). The security items that matter (`runAsNonRoot`, read-only root filesystem, dropped capabilities, no privilege escalation, seccomp, resource limits) pass |
| `scripts/validate_k8s.py` | cross-reference checks | 0 errors, 1 expected warning (the prod Secret is created outside the repo) |
| `nginx` 1.27.5 (Windows build) | `nginx -t` on the template rendered with three sets of `BACKEND_URL` / `MAX_UPLOAD_MB` / `PROXY_TIMEOUT`, using the same logic as the official entrypoint (the `.envsh` script sourced by `sh`, then substitution of defined variables only) | all valid; `client_max_body_size` is `4097m` (2048), `201m` (100) and `3m` (1); no `${...}` left over |
| `nginx` live | The rendered config serving `frontend/dist` and proxying to the real backend | `/healthz` 200, `/api/health` 200 (JSON, `no-store`), `/` and SPA routes 200 with `no-cache`, CSP and `X-Frame-Options`, a missing asset 404 |
| Backend start-up simulation | `docker/entrypoint.sh` with `RUN_MIGRATIONS=1`, `UVICORN_WORKERS=2` (and 1), `API_PORT=8260`, temporary SQLite `DATABASE_URL`, `STORAGE_DIR`/`TEMP_DIR` in a temp folder | `alembic upgrade head` creates `library_sessions` and `alembic_version` (revision `0001`), uvicorn starts the workers, `/api/health` returns 200; stopped afterwards |
| `.dockerignore` | Simulated against the 405 tracked files | `alembic/`, `alembic.ini`, `src/` (including `src/data/circuits.json`, `src/locales/` and `src/locales/extra/`), `main.py`, `docker/` and `requirements.txt` are included; tests, docs, k8s, frontend sources, `data/`, CSVs and caches are not. Guarded now by `tests/test_container_build_context.py` |

A caveat on the nginx rows: a trailing slash in `BACKEND_URL` (for example `http://backend:8000/`) still
passes `nginx -t`, but because `proxy_pass` would then have a URI part, `/api/` would be rewritten and
the API would break. Use `BACKEND_URL` without a path.

### Found and fixed during this verification

- **`alembic upgrade head` failed in the container** with `ModuleNotFoundError: No module named 'src'`:
  the `alembic` console script does not put the working directory on `sys.path`, so
  `alembic/env.py` could not import `src.db`. This would have broken `RUN_MIGRATIONS=1` and the
  Kubernetes `migrate` initContainer. Fixed with `prepend_sys_path = .` in `alembic.ini` and
  `PYTHONPATH=/app` in the backend image.
- Backend image: the builder stage copied `requirements.txt` to a relative path without `WORKDIR`
  (now `/build`); both HEALTHCHECKs use the exec form (no shell).
- Frontend image: explicit `USER 101` (the nginx-unprivileged user, same as the Kubernetes
  `runAsUser`).
- `.dockerignore`: `__pycache__` and `*.pyc` were only excluded at the root (the file is anchored);
  they are now excluded at any depth.
- `.gitattributes`: forced LF for `*.envsh` and `frontend/nginx.conf` (a CRLF checkout on Windows would
  break the script and the template inside the Linux image).
- `Makefile`: `kind-up` ran `sh scripts/kind-up.sh`, but the script is bash (`set -o pipefail`);
  it now runs `bash`.

### Windows: install the tools and repeat the verification

1. Enable virtualization (VT-x / SVM) in the BIOS/UEFI, install WSL 2 (`wsl --install`, then reboot) and check that
   `wsl --status` says `Default Version: 2`.
2. Install Docker Desktop, kind and kubectl from PowerShell (Docker Desktop already includes kubectl):

   ```powershell
   winget install -e --id Docker.DockerDesktop
   winget install -e --id Kubernetes.kind
   winget install -e --id Kubernetes.kubectl
   # optional, to use the Makefile on Windows:
   winget install -e --id ezwinports.make
   ```

   Reboot or log out if Docker Desktop asks for it, start it, and check `docker version`,
   `kind version` and `kubectl version --client`.
3. From the repository root, in this order (stop at the first failure and keep the output):

   ```powershell
   Copy-Item .env.example .env            # then edit POSTGRES_PASSWORD
   docker compose config -q               # syntax and variables
   docker build -t motorsport-backend:dev .        # first build: more than 10 minutes
   docker build -t motorsport-frontend:dev ./frontend
   docker run --rm motorsport-backend:dev python -c "import xgboost, reportlab, matplotlib, psycopg"
   docker compose up --build -d
   curl.exe -f http://localhost:8080/api/health
   docker compose exec backend id         # expect uid=10001
   docker compose exec backend sh -c "touch /app/x"   # expect: Read-only file system
   docker compose logs backend            # look for "[entrypoint] alembic upgrade head"
   docker compose down
   ```

4. Kubernetes with kind (ports 8088/8443 must be free):

   ```powershell
   .\scripts\kind-up.ps1                   # or: make kind-up
   kubectl -n motorsport get pods          # postgres, backend, frontend Ready
   kubectl -n motorsport logs deploy/backend -c migrate
   kubectl kustomize k8s/overlays/local | kubectl apply --dry-run=server -f -
   curl.exe -f http://localhost:8088/api/health
   make kind-down                          # or: kind delete cluster --name motorsport
   ```

5. Optional extra scanning: `trivy config .` and `trivy image motorsport-backend:dev`.
6. To repeat the static checks without Docker, download the same standalone binaries (`docker-compose`,
   `kustomize`, `kubeconform`, `hadolint`, `shellcheck` from their GitHub releases) and run
   `kustomize build k8s/overlays/local | kubeconform -strict -kubernetes-version 1.30.0 -summary`,
   `docker-compose config -q`, `hadolint Dockerfile frontend/Dockerfile`, `python scripts/validate_k8s.py`
   and `python -m pytest tests/test_container_build_context.py tests/test_k8s_manifests.py`.

If a step fails, keep the failing command and its output; Troubleshooting below lists the real incidents of the
first deployment.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `required variable POSTGRES_PASSWORD is missing a value` on `docker compose up` | You did not create `.env` (`cp .env.example .env`, then set the password). |
| Docker Desktop: "Virtualization support not detected" | Enable VT-x/SVM in the BIOS/UEFI, run `wsl --install`, reboot. |
| `docker build` of the backend takes more than 10 minutes, or fails with `TimeoutError: The read operation timed out` (pip) | The first build downloads the whole scientific stack; the timeout is a transient network error. Run the build again (cached layers are reused). |
| In kind, the `migrate` initContainer fails 1-2 times with `failed to resolve host postgres` | Normal: it starts in parallel with PostgreSQL and then succeeds. Watch `kubectl -n motorsport get pods`; investigate only if it keeps failing. |
| `Essential channel Speed has no valid numeric values` inside the container | pandas 3 was installed. `requirements.txt` now pins `pandas<3` and `numpy<2`: rebuild the image. |
| `/api/telemetry/analyze` returns 500 `unable to open database file` | The lap-history database (`laptime_history.db`) had no writable folder. It is now stored in `STORAGE_DIR` or in the path given by `LAPTIME_HISTORY_DB`; make sure that folder is writable (the storage volume is). |
| Browser console: `violates Content-Security-Policy ... script-src 'self'` | An inline script is blocked by the CSP. The theme script must be an external file (`frontend/public/theme-init.js`; already fixed). |
| The UI in production calls `http://localhost:8000` | An API client does not use the relative `/api`. Fixed in `library.js` and `setups.js`; every client must fall back to `/api` in production. |
| PowerShell: `curl` gives odd output or an error | `curl` is an alias of `Invoke-WebRequest`; use `curl.exe`. |
| A debug pod is rejected in the `motorsport` namespace | Pod Security `restricted` requires a `securityContext` (non-root, no privilege escalation, dropped capabilities); this is correct. |
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
