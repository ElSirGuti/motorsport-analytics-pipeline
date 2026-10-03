# Despliegue: local, Docker Compose y Kubernetes

[Read in English](DEPLOYMENT.md)

Este documento cubre tres formas de ejecutar la aplicación: directamente en tu máquina, con Docker
Compose (backend + frontend + PostgreSQL) y en Kubernetes (manifiestos Kustomize, estructura
pensada para kind/minikube/Docker Desktop y un overlay de producción).

> **Nota de honestidad.** Las imágenes, el archivo Compose y los manifiestos de Kubernetes se
> escribieron y validaron solo de forma estática (sintaxis YAML, esquemas de Kubernetes,
> comprobaciones cruzadas, `bash -n`, parser de PowerShell) en una máquina **sin Docker ni
> Kubernetes**. Todavía no se han construido ni aplicado. Consulta
> [Verificación realizada y pendiente](#verificación-realizada-y-pendiente) para la lista exacta y los comandos que debes
> ejecutar en tu equipo.

## Arquitectura

```
                       navegador
                          |
                          v
              +-----------------------+
              | Ingress (nginx)       |   solo k8s; compose publica el frontend directamente
              | body 4097m, timeout 900s
              +-----------+-----------+
                          |  /
                          v
              +-----------------------+
              | frontend  (nginx, :8080)
              |  - sirve la SPA React
              |  - /api/*  --proxy-->  |
              +-----------+-----------+
                          |  http://backend:8000
                          v
              +-----------------------+
              | backend  (FastAPI/uvicorn, :8000)
              |  /api/health, endpoints de análisis
              |  /tmp (emptyDir)  /app/data/storage (volumen/PVC)
              +-----------+-----------+
                          |  postgresql+psycopg://...@postgres:5432/motorsport
                          v
              +-----------------------+
              | postgres 16 (StatefulSet / servicio compose, 1 instancia)
              +-----------------------+
```

El navegador habla con un solo origen. El build de producción del frontend llama a la ruta relativa
`/api` (`import.meta.env.PROD` sin `VITE_API_URL`); nginx la reenvía al backend, así que no hay
CORS. En desarrollo el frontend sigue llamando directamente a `http://localhost:8000/api`.

### Contrato de entorno

| Variable | Usada por | Valor local | En contenedores |
|---|---|---|---|
| `MAX_UPLOAD_MB` | backend, nginx del frontend, Ingress | `2048` | mismo valor en todos (por archivo) |
| `CORS_ORIGINS` | backend | localhost:5173/3000 | origen(es) de la UI si la API se llama entre orígenes |
| `LOG_LEVEL` | backend | `INFO` | `INFO` |
| `TEMP_DIR` | backend | `./tmp` | `/tmp/motorsport-analytics` (tmpfs / emptyDir) |
| `DATABASE_URL` | backend (biblioteca/BD) | `sqlite:///data/motorsport.db` | `postgresql+psycopg://user:pass@postgres:5432/motorsport` |
| `STORAGE_DIR` | backend | `./data/storage` | `/app/data/storage` (volumen / PVC) |
| `AC_SETUPS_DIR` | backend | carpeta de setups de Assetto Corsa | normalmente sin definir; bind-mount opcional de solo lectura |
| `UVICORN_WORKERS` | entrypoint del contenedor | n/a | `1` |
| `RUN_MIGRATIONS` | entrypoint del contenedor | n/a | `1` en compose ejecuta `alembic upgrade head` al arrancar |
| `UPLOAD_DIR` | backend | `<STORAGE_DIR>/uploads` si hay `STORAGE_DIR`, si no `<TEMP_DIR>/uploads` | sin definir (usa el volumen / PVC `storage`) |
| `UPLOAD_TTL_HOURS` | backend | `24` | las subidas sin uso durante este tiempo se borran |
| `SESSION_CACHE_MAX_MB` | backend | `1024` | por proceso; mantenlo por debajo del límite de memoria del pod menos un análisis |
| `SESSION_CACHE_TTL_MIN` | backend | `60` | minutos de inactividad antes de sacar una sesión de memoria |

`MAX_UPLOAD_MB` se aplica de verdad: el backend rechaza con HTTP 413 (mensaje traducido, archivo
parcial borrado) cualquier subida que supere el límite mientras la copia a disco, y también los
requests cuyo `Content-Length` lo excede claramente. nginx deriva `client_max_body_size` como
`2 x MAX_UPLOAD_MB + 1` MB (una comparación lleva dos archivos). La anotación `proxy-body-size` del
Ingress (`4097m`) se fija a mano: cámbiala junto con el ConfigMap.

## 1. Local, sin Docker

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

cd frontend && npm install && npm run dev            # http://localhost:5173
```

Opcional: con `VITE_API_URL=/api npm run dev` Vite hace proxy de `/api` a `VITE_PROXY_TARGET`
(por defecto `http://localhost:8000`), de modo que el navegador usa el mismo origen que en producción.

## 2. Docker Compose

Requisitos: Docker Engine / Docker Desktop con Compose v2.

```bash
cp .env.example .env          # edita POSTGRES_PASSWORD; los valores de ejemplo NO son para producción
docker compose up --build -d
docker compose ps             # espera a que backend esté "healthy"
# UI: http://localhost:8080   (FRONTEND_PORT en .env)
```

Atajos: `make up | down | logs | test | lint` (Linux/macOS/WSL) o
`.\scripts\dev.ps1 up | down | logs | test | lint` (PowerShell).

Qué obtienes:

- `postgres`: `postgres:16-alpine`, volumen con nombre `pgdata`, healthcheck `pg_isready`, solo en
  una red interna (no accesible desde el host).
- `backend`: construido desde `Dockerfile` (multi-stage, no root uid 10001, sistema de archivos raíz
  de solo lectura, tmpfs `/tmp`, volumen `storage`), espera un Postgres sano y ejecuta migraciones
  si existe `alembic.ini`. No se publica al host por defecto.
- `frontend`: nginx-unprivileged en `:8080`, espera a un backend sano.
- Límites de memoria/CPU por servicio (backend 4 GiB, 2 CPUs).

Perfil dev (backend con recarga en contenedor, frontend con Vite local):

```bash
docker compose --profile dev up postgres backend-dev     # API en http://127.0.0.1:8010
cd frontend && VITE_API_URL=http://localhost:8010/api npm run dev
```

Carpeta de setups de Assetto Corsa (solo lectura): copia `docker-compose.override.example.yml` a
`docker-compose.override.yml`, edita la ruta del host y reinicia.

Borrar todo incluidos los datos: `docker compose down -v`.

## 3. Kubernetes con Kustomize

Estructura:

```
k8s/
  base/                 namespace, ServiceAccount, ConfigMap, StatefulSet de Postgres (+Service headless),
                        backend (PVC, Service, Deployment con initContainer de migración, HPA, PDB),
                        frontend (Service, Deployment, PDB), Ingress, NetworkPolicies
  overlays/local/       kind/minikube/Docker Desktop: 1 réplica, imágenes :dev, Secret desechable, host localhost
  overlays/prod/        2+ réplicas, más recursos, TLS (placeholder de cert-manager), almacenamiento RWX, HPA 2-6
```

La base nunca contiene un Secret real. `overlays/local` genera uno desechable; en
`overlays/prod` debes crear tú `motorsport-db` (`secret.example.yaml`,
`externalsecret.example.yaml`; se recomienda sealed-secrets o external-secrets). Como la URL de la
base de datos se compone con las tres claves, usa solo caracteres seguros para URL en la contraseña.

### kind (recomendado para una primera prueba)

Requisitos: Docker, [kind](https://kind.sigs.k8s.io/), kubectl.

```bash
make kind-up                       # o: bash scripts/kind-up.sh   |   .\scripts\kind-up.ps1
```

El script crea el clúster (`scripts/kind-cluster.yaml`, puerto del host 8088 -> ingress 80),
instala ingress-nginx, construye `motorsport-backend:dev` y `motorsport-frontend:dev`, las carga con
`kind load docker-image`, aplica `k8s/overlays/local` y espera los rollouts. Después abre
<http://localhost:8088>.

Equivalente manual:

```bash
kind create cluster --name motorsport --config scripts/kind-cluster.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.2/deploy/static/provider/kind/deploy.yaml
docker build -t motorsport-backend:dev . && docker build -t motorsport-frontend:dev ./frontend
kind load docker-image motorsport-backend:dev motorsport-frontend:dev --name motorsport
kubectl apply -k k8s/overlays/local
kubectl -n motorsport get pods -w
```

### minikube / Kubernetes de Docker Desktop

- minikube: `minikube addons enable ingress`, construye en su daemon con
  `minikube image build -t motorsport-backend:dev .` (y el frontend), luego
  `kubectl apply -k k8s/overlays/local` y `minikube tunnel`; usa `http://localhost`.
- Docker Desktop: activa Kubernetes, instala ingress-nginx (`.../provider/cloud/deploy.yaml`),
  construye con `docker build` (el clúster las ve directamente), aplica el overlay local y abre
  `http://localhost`.
- Sin ingress: `kubectl -n motorsport port-forward svc/frontend 8080:80`.

### Overlay de producción

1. Sube las imágenes a un registro y ajusta `images:` en `overlays/prod/kustomization.yaml`
   (`ghcr.io/OWNER/...` es un placeholder; hoy no se publica nada y no hay CI).
2. Crea el Secret `motorsport-db` (ver arriba) en el namespace `motorsport`.
3. Pon tu host en `ingress-patch.yaml` y el valor de CORS en el kustomization; instala cert-manager y
   un ClusterIssuer si quieres TLS automático.
4. Elige una StorageClass RWX en `storage-patch.yaml` (o baja las réplicas a 1).
5. `kubectl apply -k k8s/overlays/prod`

Renderizar sin aplicar: `kubectl kustomize k8s/overlays/prod`.

### Subir una vez (`file_id`) y la caché de análisis

La interfaz sube la sesión una sola vez con `POST /api/files` y los endpoints de análisis
(`analyze-session`, `stint/analyze`, `optimal-lap`, `compare-session-laps`, `telemetry/analyze`,
`setups/detect`) aceptan el `file_id` devuelto (el SHA-256 del contenido) en lugar del archivo.
Enviar el archivo como antes sigue funcionando.

- **El disco es la fuente de verdad, la memoria es una caché.** El archivo vive en `UPLOAD_DIR` (por
  defecto el volumen `storage` en las imágenes). Cada proceso mantiene los DataFrames ya leídos y
  filtrados en un LRU acotado por `SESSION_CACHE_MAX_MB` con TTL de inactividad
  `SESSION_CACHE_TTL_MIN`; cada petición recibe copias privadas.
- **Varias réplicas.** La memoria nunca se comparte entre pods/workers. Si una réplica no tiene los
  frames, vuelve a leer el archivo guardado (unos segundos con un CSV grande; luego queda en su
  caché). Eso solo funciona si todas las réplicas ven el mismo `UPLOAD_DIR`: usa un volumen RWX (o
  afinidad de sesión). Sin volumen compartido, una petición que cae en una réplica que nunca recibió la
  subida obtiene **HTTP 410** (mensaje traducido) y la interfaz vuelve a subir el archivo y reintenta
  una vez: es más lento pero correcto.
- **Limpieza.** Las subidas con más de `UPLOAD_TTL_HOURS` sin uso se borran en un hilo en segundo plano
  con frecuencia limitada. Dimensiona el volumen para `subidas por día x tamaño del archivo`. Si
  `UPLOAD_DIR` cae en `TEMP_DIR` sobre un tmpfs, esos archivos cuentan contra la memoria del pod.
- Los endpoints de análisis se ejecutan en el pool de hilos (ya no bloquean el event loop); varias
  peticiones simultáneas del mismo archivo lo leen una sola vez (bloqueo por clave de caché).

## Qué está listo para producción y qué NO

Razonable ya:

- Contenedores no root, sistemas de archivos raíz de solo lectura, capabilities eliminadas, seccomp
  RuntimeDefault, Pod Security `restricted` en el namespace.
- Probes (startup/readiness/liveness), requests y limits, PodDisruptionBudgets, HPA, NetworkPolicies
  con denegación por defecto, sin secretos en git, tags de imagen configurables.
- Proxy de mismo origen con timeouts largos y límite de subida aplicado.

NO está listo para producción (hay que decirlo claro):

- **Sin autenticación ni autorización.** Quien llegue a la URL puede subir y analizar. Ponlo detrás
  de una VPN, de un proxy con autenticación (oauth2-proxy) o añade auth antes de exponerlo.
- **PostgreSQL es una sola réplica de StatefulSet**: sin replicación, backups ni failover. Usa una
  base gestionada o un operador (CloudNativePG, Zalando) para algo importante y configura backups.
  El backend solo necesita `DATABASE_URL`.
- **Réplicas del backend y análisis en memoria.** Cada análisis se ejecuta en la memoria de la réplica
  que recibe la petición y se devuelve en la respuesta; no hay caché ni estado de sesión
  compartido. Varias réplicas funcionan para peticiones independientes, pero la memoria por pod debe
  alcanzar para tu CSV más grande (limits por defecto 4 GiB; prod 8 GiB) y `UVICORN_WORKERS` la
  multiplica. Los archivos de la biblioteca en `STORAGE_DIR` necesitan un volumen RWX con más de una
  réplica.
- **Las migraciones corren en un initContainer.** Bien con 1 réplica; con varias arrancando a la vez dos
  migraciones podrían competir. En producción estricta ejecuta `alembic upgrade head` como Job
  aparte (o hook pre-sync de Helm/Argo) antes del rollout.
- El autoescalado por CPU no refleja los picos de memoria de subidas grandes. No hay métricas, trazas
  ni agregación de logs. No hay rate limiting.
- Las NetworkPolicies solo se aplican con CNIs que las soportan (no el CNI por defecto de kind).
- Las imágenes no se escanean ni se firman; no hay registro ni pipeline de CI (decisión deliberada).

<a id="que-se-ha-verificado"></a>
## Verificación realizada y pendiente

Sé preciso con lo que aquí significa "verificado": **todavía no se ha construido ni ejecutado nada
dentro de Docker o Kubernetes** (la máquina de desarrollo no tiene ninguno). Lo hecho el 2026-10-03 es
una verificación estática real con las herramientas oficiales standalone (descargadas de sus releases de
GitHub a una carpeta temporal, sin daemon y sin instalar nada en el repositorio), más una simulación del
arranque del backend y del proxy nginx en el equipo anfitrión.

### Realizado

| Herramienta (versión) | Qué se ejecutó | Resultado |
|---|---|---|
| `docker-compose` v2.29.7 | `config -q` (con `POSTGRES_PASSWORD` definida) y `--profile dev config -q` | válido; sin `POSTGRES_PASSWORD` falla con el mensaje previsto |
| `kustomize` v5.8.2 | `build k8s/overlays/local` y `k8s/overlays/prod` | renderiza: 16 y 18 objetos |
| `kubeconform` v0.8.0 | `-strict -kubernetes-version 1.30.0` sobre ambos overlays renderizados | 16/16 y 18/18 válidos, 0 errores, 0 omitidos |
| `hadolint` v2.15.1 | `Dockerfile`, `frontend/Dockerfile` | limpio tras las correcciones de abajo, salvo DL3008 (paquetes apt sin versión fijada: deliberado, las versiones cambian con cada release de Debian) |
| `shellcheck` v0.11.0 | `docker/entrypoint.sh`, `frontend/docker/15-upload-limit.envsh`, `scripts/kind-up.sh` | sin hallazgos |
| `yamllint` 1.38 | `k8s/`, archivos compose | limpio |
| `checkov` 3.3.22 | Dockerfiles; overlays de Kubernetes renderizados | Dockerfiles: 157 superados, 0 fallidos (tras añadir un `USER` explícito a la imagen del frontend). Kubernetes: 535 superados, 20 fallidos en local+prod, todos de estos tipos aceptados: imagen sin fijar por digest (CKV_K8S_43), pull policy distinta de `Always` (CKV_K8S_15; `Always` rompería las imágenes locales cargadas en kind), secretos como variables de entorno y no como archivos (CKV_K8S_35), UID menor de 10000 en frontend (101) y PostgreSQL (70), impuesto por las imágenes originales (CKV_K8S_40). Los puntos de seguridad que importan (`runAsNonRoot`, sistema raíz de solo lectura, capabilities eliminadas, sin escalada de privilegios, seccomp, límites de recursos) pasan |
| `scripts/validate_k8s.py` | comprobaciones cruzadas | 0 errores, 1 aviso esperado (el Secret de prod se crea fuera del repo) |
| `nginx` 1.27.5 (build para Windows) | `nginx -t` sobre la plantilla renderizada con tres combinaciones de `BACKEND_URL` / `MAX_UPLOAD_MB` / `PROXY_TIMEOUT`, con la misma lógica del entrypoint oficial (el script `.envsh` cargado con `sh`, luego sustitución solo de las variables definidas) | todas válidas; `client_max_body_size` es `4097m` (2048), `201m` (100) y `3m` (1); no queda ningún `${...}` |
| `nginx` en vivo | La configuración renderizada sirviendo `frontend/dist` y haciendo proxy al backend real | `/healthz` 200, `/api/health` 200 (JSON, `no-store`), `/` y rutas SPA 200 con `no-cache`, CSP y `X-Frame-Options`, un asset inexistente 404 |
| Simulación del arranque del backend | `docker/entrypoint.sh` con `RUN_MIGRATIONS=1`, `UVICORN_WORKERS=2` (y 1), `API_PORT=8260`, `DATABASE_URL` SQLite temporal, `STORAGE_DIR`/`TEMP_DIR` en carpeta temporal | `alembic upgrade head` crea `library_sessions` y `alembic_version` (revisión `0001`), uvicorn arranca los workers, `/api/health` devuelve 200; se apagó después |
| `.dockerignore` | Simulado sobre los 405 archivos versionados | se incluyen `alembic/`, `alembic.ini`, `src/` (con `src/data/circuits.json`, `src/locales/` y `src/locales/extra/`), `main.py`, `docker/` y `requirements.txt`; no se incluyen tests, docs, k8s, fuentes del frontend, `data/`, CSV ni cachés. Ahora lo protege `tests/test_container_build_context.py` |

Una salvedad sobre las filas de nginx: una barra final en `BACKEND_URL` (por ejemplo `http://backend:8000/`)
sigue pasando `nginx -t`, pero como `proxy_pass` tendría entonces parte de URI, `/api/` se reescribiría y
la API dejaría de funcionar. Usa `BACKEND_URL` sin ruta.

### Hallado y corregido durante esta verificación

- **`alembic upgrade head` fallaba en el contenedor** con `ModuleNotFoundError: No module named 'src'`:
  el script de consola `alembic` no pone el directorio de trabajo en `sys.path`, así que `alembic/env.py`
  no podía importar `src.db`. Habría roto `RUN_MIGRATIONS=1` y el initContainer `migrate` de Kubernetes.
  Corregido con `prepend_sys_path = .` en `alembic.ini` y `PYTHONPATH=/app` en la imagen del backend.
- Imagen del backend: la etapa builder copiaba `requirements.txt` a una ruta relativa sin `WORKDIR`
  (ahora `/build`); ambos HEALTHCHECK usan la forma exec (sin shell).
- Imagen del frontend: `USER 101` explícito (el usuario de nginx-unprivileged, igual que el `runAsUser`
  de Kubernetes).
- `.dockerignore`: `__pycache__` y `*.pyc` solo se excluían en la raíz (el archivo está anclado); ahora se
  excluyen a cualquier profundidad.
- `.gitattributes`: se fuerza LF para `*.envsh` y `frontend/nginx.conf` (un checkout con CRLF en Windows
  rompería el script y la plantilla dentro de la imagen Linux).
- `Makefile`: `kind-up` ejecutaba `sh scripts/kind-up.sh`, pero el script es bash (`set -o pipefail`);
  ahora ejecuta `bash`.

### NO verificado (requiere Docker, kind o PostgreSQL)

- Construir cualquiera de las imágenes (`pip install` del stack científico en Linux, `apt`, `npm ci`), el
  tamaño de la imagen, y que el usuario no root (uid 10001) pueda ejecutar todo con el sistema raíz de
  solo lectura y los montajes `tmpfs` / volumen (la simulación anterior corrió con tu usuario de Windows).
- El propio entrypoint oficial de `nginxinc/nginx-unprivileged` (que cargue los `*.envsh` antes del paso
  de plantillas y corra como uid 101 sobre un sistema de solo lectura): reproducido por razonamiento y
  por la emulación anterior, no ejecutando la imagen.
- Healthchecks de Docker, `depends_on: service_healthy`, las redes de compose (`backend-net` interna),
  `docker compose up`.
- PostgreSQL: el backend solo se ejercitó con SQLite. `psycopg` no está instalado en la máquina de
  desarrollo y la migración `0001` inspecciona la conexión viva, por lo que tampoco funciona
  `alembic upgrade head --sql` (SQL offline para revisión). La ruta Postgres (`postgresql+psycopg://`,
  columna JSONB) no está verificada.
- Todo lo que necesita un clúster: `kubectl apply`, dry run del lado servidor, admisión Pod Security
  `restricted`, probes, enlace de PVC, el HPA (necesita metrics-server), `ingress-nginx` y la URL con
  `INGRESS_NGINX_VERSION` fijada, y la aplicación de NetworkPolicy (el CNI por defecto de kind no la aplica).
- Los flujos completos de `scripts/kind-up.ps1` y `scripts/kind-up.sh`.

### Lo que solo puede hacer el propietario (Windows)

1. Instalar Docker Desktop (backend WSL 2), kind y kubectl, por ejemplo desde PowerShell:

   ```powershell
   winget install -e --id Docker.DockerDesktop
   winget install -e --id Kubernetes.kind
   winget install -e --id Kubernetes.kubectl
   # opcional, para usar el Makefile en Windows:
   winget install -e --id ezwinports.make
   ```

   Reinicia o cierra sesión si Docker Desktop lo pide, arráncalo y comprueba `docker version`,
   `kind version` y `kubectl version --client`.
2. Desde la raíz del repositorio, en este orden (detente en el primer fallo y guarda la salida):

   ```powershell
   Copy-Item .env.example .env            # luego edita POSTGRES_PASSWORD
   docker compose config -q               # sintaxis y variables
   docker build -t motorsport-backend:dev .
   docker build -t motorsport-frontend:dev ./frontend
   docker run --rm motorsport-backend:dev python -c "import xgboost, reportlab, matplotlib, psycopg"
   docker compose up --build -d
   curl.exe -f http://localhost:8080/api/health
   docker compose exec backend id         # espera uid=10001
   docker compose exec backend sh -c "touch /app/x"   # espera: Read-only file system
   docker compose logs backend            # busca "[entrypoint] alembic upgrade head"
   docker compose down
   ```

3. Kubernetes con kind (los puertos 8088/8443 deben estar libres):

   ```powershell
   .\scripts\kind-up.ps1                   # o: make kind-up
   kubectl -n motorsport get pods          # postgres, backend, frontend Ready
   kubectl -n motorsport logs deploy/backend -c migrate
   kubectl kustomize k8s/overlays/local | kubectl apply --dry-run=server -f -
   curl.exe -f http://localhost:8088/api/health
   make kind-down                          # o: kind delete cluster --name motorsport
   ```

4. Escaneo extra opcional: `trivy config .` y `trivy image motorsport-backend:dev`.
5. Para repetir las comprobaciones estáticas de esta sección sin Docker, descarga los mismos binarios
   standalone (`docker-compose`, `kustomize`, `kubeconform`, `hadolint`, `shellcheck` desde sus releases
   de GitHub) y ejecuta `kustomize build k8s/overlays/local | kubeconform -strict -kubernetes-version 1.30.0 -summary`,
   `docker-compose config -q`, `hadolint Dockerfile frontend/Dockerfile`, `python scripts/validate_k8s.py`
   y `python -m pytest tests/test_container_build_context.py tests/test_k8s_manifests.py`.

Si algún paso falla, envía el comando que falla y su salida: es justo la información que las
comprobaciones estáticas anteriores no pudieron producir.

## Solución de problemas

| Síntoma | Causa / solución |
|---|---|
| Error por `POSTGRES_PASSWORD` en `docker compose up` | No creaste `.env` (`cp .env.example .env`). |
| La subida falla con 413 | Archivo mayor que `MAX_UPLOAD_MB` (backend) o que el límite de body (nginx/Ingress). Súbelos todos a la vez. |
| El análisis devuelve 504 / conexión reiniciada | Un timeout de proxy es menor que el análisis: revisa `PROXY_TIMEOUT`, `proxy-read-timeout` del Ingress y el idle timeout del balanceador. |
| Pod del backend `OOMKilled` | Límite de memoria menor que lo que necesita el CSV; súbelo o baja `UVICORN_WORKERS`. |
| `CrashLoopBackOff` en el init `migrate` | Falta `alembic.ini` en la imagen, credenciales erróneas o Postgres aún no listo (`kubectl logs <pod> -c migrate`). |
| `ImagePullBackOff` en local | Imagen no cargada en el clúster: `kind load docker-image ...`; los tags deben ser `:dev`. |
| 404/502 en `http://localhost:8088` | Controlador de ingress no listo (`kubectl -n ingress-nginx get pods`) o frontend no listo. |
| nginx: `host not found in upstream "backend"` | El frontend arrancó fuera de la red de compose/clúster o sin el Service del backend. |
| `kubectl apply` del overlay prod: secret no encontrado | Crea primero `motorsport-db`. |
| El frontend en dev no alcanza la API | ¿Backend en :8000? ¿`CORS_ORIGINS` incluye el origen de Vite? O usa `VITE_API_URL=/api`. |

## Notas de seguridad

- Las credenciales de ejemplo de `.env.example` y del overlay local son valores desechables para un
  portátil. No las reutilices. `.env` está en `.gitignore`.
- No subas Secrets reales; usa sealed-secrets o external-secrets.
- Los contenedores corren como no root con sistema de archivos raíz de solo lectura; solo se puede
  escribir en `/tmp` y en el volumen de almacenamiento.
- nginx envía `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` y
  una Content-Security-Policy (permite Google Fonts, que la UI carga). Añade HSTS en la capa que
  termina TLS (Ingress/balanceador).
- La aplicación aún no tiene autenticación (ver arriba); no la expongas a internet tal cual.
