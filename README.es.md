# Motorsport Analytics Pipeline

> Análisis de telemetría de vueltas y sesiones de Assetto Corsa e iRacing: comparación de vueltas, diagnóstico curva a curva, análisis de stint y neumáticos, vuelta óptima por microsectores, recomendaciones de setup enlazadas con tus setups de Assetto Corsa, biblioteca de sesiones e informe PDF bilingüe.

[Read in English](README.md)

## Inicio rápido

```bash
# 1. Backend (desde la raíz del proyecto)
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt && uvicorn main:app --reload --port 8000

# 2. Frontend (segunda terminal)
cd frontend && npm install && npm run dev

# 3. Abre http://localhost:5173 y suelta un CSV, .ibt o .ld (ver "Uso de la aplicación")
```

Con Docker (backend + frontend + PostgreSQL, interfaz en http://localhost:8080): `cp .env.example .env && docker compose up --build -d`. Los archivos de Docker y Kubernetes **no se han ejecutado** en la máquina del autor (allí no había Docker); consulta [Despliegue](#despliegue) y [docs/DEPLOYMENT.es.md](docs/DEPLOYMENT.es.md).

## Tabla de contenidos

- [Qué es](#qué-es)
- [Instalación](#instalación)
- [Despliegue](#despliegue)
- [Uso de la aplicación](#uso-de-la-aplicación)
- [Funciones principales](#funciones-principales)
- [Formatos de telemetría](#formatos-de-telemetría)
- [Circuitos conocidos y nombres de curva](#circuitos-conocidos-y-nombres-de-curva)
- [Temas](#temas)
- [Rendimiento y subida única](#rendimiento-y-subida-única)
- [Notas de calidad de datos y comportamiento](#notas-de-calidad-de-datos-y-comportamiento)
- [Ejemplo de resultado](#ejemplo-de-resultado)
- [Arquitectura](#arquitectura)
- [API](#api)
- [Configuración](#configuración)
- [Desarrollo y tests](#desarrollo-y-tests)
- [Documentación](#documentación)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Contribuir](#contribuir)
- [Licencia](#licencia)

## Qué es

Un backend FastAPI y un frontend React. Subes telemetría y obtienes:

- **Modo sesión (1 archivo):** la sesión completa se segmenta automáticamente en vueltas. Obtienes una tabla de vueltas (con las vueltas de pit y atípicas marcadas), análisis de stint (degradación de ritmo, estrategia de combustible, proyección Monte Carlo, ventana de pit, evolución de pista), la vuelta óptima por microsectores, análisis de curvas de la sesión, degradación de neumáticos, gestión térmica, optimización de trazada, recomendaciones de setup y un panel de calidad de datos.
- **Modo comparación (2 archivos de una vuelta cada uno, o 2 vueltas elegidas de una sesión):** time delta alineado por distancia, superposición de velocidad/freno/acelerador, diagnóstico curva a curva, diagrama G-G, eventos de subviraje/sobreviraje, análisis de neumáticos/frenos/suspensión/inputs/slip angle, módulos de ML (detección de anomalías, clustering de estilo, potencial de vuelta) e informe PDF.
- **Biblioteca:** las sesiones analizadas se pueden guardar en una base de datos, reabrir sin el archivo original y compararlas entre sí.

La interfaz tiene dos vistas: **Ingeniero** (todo) y **Piloto** (paneles técnicos ocultos). Idiomas: español e inglés (los mensajes y reportes de la API siguen el parámetro `lang` o `Accept-Language`).

## Instalación

### Requisitos

| Herramienta | Versión |
|---|---|
| Python | 3.10+ (la imagen Docker usa 3.11) |
| Node.js | 18+ (la imagen Docker usa 20) |
| Git | cualquiera |
| Docker | opcional (Compose v2), solo para contenedores |

### Local

```bash
git clone https://github.com/ElSirGuti/motorsport-analytics-pipeline.git
cd motorsport-analytics-pipeline

python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt    # añade -r requirements-dev.txt para los tests

cd frontend && npm install && cd ..
```

Ejecuta los dos procesos en terminales separadas:

```bash
uvicorn main:app --reload --port 8000     # API en http://localhost:8000 (docs en /docs)
cd frontend && npm run dev                # UI en http://localhost:5173
```

También puedes ejecutar `python main.py`, que lee `API_HOST`, `API_PORT` y `API_RELOAD` del entorno. En local la biblioteca usa un archivo SQLite (`data/motorsport.db`); no hace falta configurar ninguna base de datos.

## Despliegue

Guía completa, con arquitectura, contrato de variables de entorno, resolución de problemas y notas de seguridad: [docs/DEPLOYMENT.es.md](docs/DEPLOYMENT.es.md) ([English](docs/DEPLOYMENT.md)).

| Método | Comando | Resultado |
|---|---|---|
| Docker Compose | `cp .env.example .env` y luego `docker compose up --build -d` (o `make up`) | UI en `http://localhost:8080` (`FRONTEND_PORT`); backend y PostgreSQL quedan en la red interna |
| Perfil dev de Compose | `docker compose --profile dev up postgres backend-dev` | API con recarga en caliente en `http://127.0.0.1:8010` (`BACKEND_DEV_PORT`) |
| Kubernetes (kind) | `make kind-up` (o `scripts/kind-up.sh`, `scripts/kind-up.ps1`) | Clúster local con el overlay Kustomize `k8s/overlays/local`, UI en `http://localhost:8088` |
| Kubernetes (otros) | `kubectl apply -k k8s/overlays/local` o `k8s/overlays/prod` | Ver la guía de despliegue |

Edita `POSTGRES_PASSWORD` en `.env` antes de arrancar; los valores de ejemplo son solo para una máquina local. Compose ejecuta `alembic upgrade head` al iniciar.

**Qué se verificó y qué no.** Los Dockerfile, `docker-compose.yml` y los manifiestos de Kubernetes se escribieron y revisaron de forma estática (YAML, esquemas de Kubernetes con `scripts/validate_k8s.py` y `kubernetes-validate`, `yamllint`, `bash -n`, parser de PowerShell) en una máquina sin Docker ni Kubernetes. **Todavía no se han construido ni aplicado.** Los comandos para verificarlos en tu máquina están en [docs/DEPLOYMENT.es.md](docs/DEPLOYMENT.es.md); la versión corta:

```bash
docker compose config -q
docker build -t motorsport-backend:dev . && docker build -t motorsport-frontend:dev ./frontend
docker compose up --build -d && curl -f http://localhost:8080/api/health
make kind-up && kubectl -n motorsport get pods
```

La aplicación **todavía no tiene autenticación**: no la expongas a internet tal cual.

**Setups de Assetto Corsa dentro de Docker.** Un contenedor no ve tu carpeta `Documentos\Assetto Corsa\setups`. Sube el `.ini` del setup manualmente en la interfaz, o monta la carpeta como bind-mount de solo lectura y define `AC_SETUPS_DIR` (ver `docker-compose.override.example.yml`).

## Uso de la aplicación

1. Abre la interfaz (`http://localhost:5173` en desarrollo, `http://localhost:8080` con Docker) y elige el idioma (ES/EN) y el modo (Piloto/Ingeniero) en la barra superior. El selector **Análisis / Biblioteca / Comparar sesiones** cambia la vista.
2. Suelta los archivos de telemetría en la zona de carga. El modo se detecta por el número de archivos:
   - **1 archivo = sesión completa**, segmentada automáticamente en vueltas.
   - **2 archivos = dos vueltas sueltas** para comparar.
3. Pulsa analizar. El archivo se sube una sola vez y una barra de progreso por etapas muestra el análisis de sesión, de stint y la vuelta óptima; los resultados aparecen a medida que termina cada etapa (una sesión de ~57 MB mostró su primer resultado en unos 2 s y terminó en unos 3 s en el equipo del autor, ver [Rendimiento](#rendimiento-y-subida-única)). Al terminar, la zona de carga se pliega en una barra de archivo con las acciones **Nuevo análisis**, **Guardar en biblioteca** y **Descargar informe**.
4. Aparece primero un **panel de calidad de datos**: puntuación, canales, vueltas y módulos de análisis, con una lista de lo que mejoraría el análisis.
5. Navega con el riel lateral:
   - Sesión: *Resumen de sesión* (tabla de vueltas, mapa de pista, vuelta óptima), *Análisis de stint*, *Setup y estrategia*.
   - Comparación: *Vuelta base*, *Dinámica del vehículo*, *Piloto y entradas*, *Estrategia y setup*.
   - El modo Piloto oculta los paneles técnicos (dinámica del vehículo y entradas del piloto).
6. En la tabla de vueltas de la sesión, marca **dos vueltas (A/B)** y pulsa **Comparar**, o usa **Mejor vs Peor**. Las vueltas de pit y atípicas aparecen marcadas.
7. Los resultados de la comparación se pueden copiar como informe de texto o descargar como PDF.

Recorrido completo: [Guía de Usuario](docs/GUIA_USUARIO.es.md).

## Funciones principales

### Vuelta óptima por microsectores

`POST /api/optimal-lap` (módulo `src/analytics/optimal_lap.py`, panel `OptimalLapPanel` en el resumen de sesión). Cada vuelta válida se normaliza a la longitud mediana del circuito y se corta en microsectores; el panel muestra dos estimaciones:

- **Teórica:** la suma del mejor tiempo de cada microsector. Es una cota inferior optimista porque ignora que la velocidad de salida de un microsector es la de entrada del siguiente.
- **Realista:** programación dinámica que solo cambia de una vuelta a otra donde las velocidades coinciden (tolerancia `speed_tol_kmh`, por defecto 3 km/h) y exige un tramo mínimo de 75 m con la misma vuelta, de modo que se mantiene la continuidad cinemática.

La longitud del microsector es configurable en la interfaz (10, 25, 50 o 100 m; la API acepta cualquier valor en `microsector_m`, por defecto 25). Límites: la cifra teórica crece al achicar el microsector (tiene más libertad para elegir lo mejor de cada vuelta); con un canal `Distance` sintetizado la alineación es menos precisa y el resultado es solo orientativo (la API añade un aviso). Necesita al menos 3 vueltas utilizables; se excluyen las vueltas de pit, atípicas y parciales. El panel muestra además la ganancia por microsector sobre el mapa de pista, las zonas donde la mejor vuelta pierde más, la ganancia por curva y las vueltas que más aportan.

Ejemplo de Imola (Porsche Cayman GT4, 21 vueltas): mejor vuelta 1:57.605, óptima realista 1:54.107 (-3.498 s), óptima teórica 1:52.885 (-4.720 s).

### Integración de setups de Assetto Corsa

Módulo `src/analytics/ac_setups.py`, router `src/api/setups.py`, interfaz `SetupSelector` y `SetupLink`. El setup que usaste se enlaza con el Setup Advisor para que cada recomendación pueda mostrar **Actual -> Sugerido**.

Orden de búsqueda:

1. `<Documentos>\Assetto Corsa\setups\<coche>\<pista>\*.ini` (coche y pista salen de la cabecera de la telemetría; `AC_SETUPS_DIR` sustituye la carpeta). Si hay varios eliges cuál usaste.
2. `<coche>\generic\last.ini`, solo tras confirmar que fue el setup usado en esa sesión.
3. Subida manual de un archivo `.ini` (siempre disponible).

Notas: la carpeta de setups solo es legible cuando el backend corre en la misma máquina que el juego. En Docker se sube manualmente o se usa un bind-mount de solo lectura. Los valores se muestran en las unidades propias del juego (clics); las unidades solo se aplican donde son seguras (presión de neumáticos en psi, balance de freno delantero y potencia de freno en %, combustible en litros), y los rangos mín/máx solo si existe el `data/setup.ini` desempaquetado del coche (los `data.acd` cifrados no se abren a propósito). Seguridad: los nombres de coche y pista se validan con un juego de caracteres estricto y se comparan con el listado real del directorio, la ruta resuelta debe quedar dentro de la carpeta de setups (se rechaza el path traversal) y solo se leen archivos `.ini`/`.sp` de hasta 256 KB.

### Biblioteca de sesiones y comparar sesiones

Código en `src/api/library.py`, `src/db/` (modelos SQLAlchemy y motor), `src/analytics/session_compare.py` y migraciones en `alembic/`. Usa **Guardar en biblioteca** en la barra de archivo (o activa el guardado automático), luego reabre la sesión desde **Biblioteca** sin el CSV, o elige dos sesiones en **Comparar sesiones** para ver diferencias de ritmo medio y mediano, consistencia, combustible por vuelta y tiempo perdido por curva.

- Almacenamiento: `DATABASE_URL` (por defecto `sqlite:///data/motorsport.db`; PostgreSQL en los contenedores, `postgresql+psycopg://...`), `STORAGE_DIR` opcional (por defecto `./data/storage`). El esquema se crea o migra automáticamente en la primera petición a la biblioteca (Alembic, con `create_all` como alternativa); Compose y el init container de Kubernetes también ejecutan `alembic upgrade head` al iniciar.
- Guardar el mismo archivo (SHA-256) en el mismo circuito actualiza la entrada existente en lugar de duplicarla.
- Para compararlas, las sesiones deben ser del mismo circuito y coche; se puede forzar la comparación y queda señalado.
- Límites: el payload guardado está limitado a **5 MB** (HTTP 413); el listado es paginado (`limit` hasta 200).
- **Todavía no hay autenticación.** La columna `owner_id` está reservada para un futuro sistema de usuarios y hoy siempre está vacía.

### Panel de calidad de datos

Módulo `src/analytics/data_quality.py`. Se incluye en las respuestas como `data_quality` y es lo primero que se muestra en la interfaz. Da una **puntuación 0-100** (buena >= 75, aceptable >= 50, pobre por debajo) con desglose, y lista: origen (simulador, coche, circuito, frecuencia de muestreo, duración), **canales** (presentes, ausentes, constantes, sintetizados, dispersos, parciales), **vueltas** (válidas, de pit, atípicas, segmentos parciales descartados), **módulos de análisis** (ok, degradado o no disponible, con el motivo concreto) y una lista priorizada de **cómo mejorar**. Reutiliza las banderas `available`/`reason`/`low_confidence` que los módulos ya producen en lugar de recalcularlas.

### Informe PDF

Rediseñado y bilingüe (ES/EN, sigue el idioma de la interfaz). **Descargar informe** en la interfaz envía los resultados ya calculados a `POST /api/report/session-pdf-from-json` (sesión, stint y opcionalmente una comparación); las comparaciones de dos archivos o de pares de vueltas usan `POST /api/report/pdf-from-json`. Las secciones incluyen resumen ejecutivo, hallazgos clave, acciones recomendadas, calidad de datos y limitaciones, ritmo y vueltas, curvas en orden de pista, recomendaciones de setup, estrategia y neumáticos y, en comparaciones, telemetría del coche y comparación de trazas. Nombre del archivo: `motorsport_<circuito>_<coche>_<fecha>.pdf`.

### Proyecciones realistas

Las proyecciones de stint y neumáticos (`src/analytics/stint.py`, `tyre_degradation.py`) son conservadoras. Con menos de 5 vueltas válidas o un intervalo de confianza de la pendiente muy ancho, la proyección vuelve al ritmo reciente y se marca `low_confidence: true`, con `confidence` (`low`/`medium`/`high`), `reason_code` (`insufficient_sample`, `wide_slope_ci`, `short_sample`) y un `reason` traducido. Con menos de 8 vueltas válidas la confianza es siempre `low` y la mediana proyectada no puede bajar de un suelo de ritmo plausible (`proj_floor_s`); la ganancia por quemar combustible se detiene cuando este se acaba (`fuel_laps_remaining`). Si el desgaste de neumáticos no parece activado en el simulador (tasa de desgaste cero y agarre de goma constante), la degradación se informa como `available: false`, `reason_code: "wear_inactive"` en lugar de inventar una tendencia, porque la degradación no se puede separar de la quema de combustible y la evolución de pista.

## Formatos de telemetría

El cargador (`src/io/loaders.py`) lee CSV y, de forma **experimental**, dos formatos nativos.

| Origen | Estado | Notas |
|---|---|---|
| Assetto Corsa con ACTI, exportado como CSV de MoTeC | Estable | El separador coma o punto y coma se detecta solo; el bloque de cabecera de MoTeC (Driver, Vehicle, Venue) se lee como metadatos y se omite la fila de unidades. |
| iRacing exportado a CSV | Estable | Se detecta por `SessionTime`, `Session Time` o `SessionLapCount`. La velocidad en m/s se convierte a km/h, los pedales de 0-1 se escalan a 0-100, la suspensión de metros a mm, la presión de neumáticos de kPa/PSI a bar y el balance de freno de fracción a porcentaje. |
| iRacing `.ibt` (`src/io/ibt_loader.py`) | **Experimental** | Se detecta por extensión o firma binaria. Las unidades se normalizan a los canales canónicos. |
| MoTeC `.ld` (`src/io/ld_loader.py`) | **Experimental** | Los canales con distinta frecuencia se remuestrean a la más alta; código compartido en `src/io/native_common.py`. |

> **Experimental.** Los lectores de `.ibt` y `.ld` siguen los formatos documentados públicamente y se validaron con pruebas sintéticas de ida y vuelta y con 53 archivos reales del autor (iRacing BMW M2 y Ford Mustang GT4, sus exportaciones `.ld` de MoTeC y logs `.ld` de Assetto Corsa/ACTI). Hace falta probar más simuladores, coches y loggers. La interfaz muestra una insignia Experimental. Si un resultado parece incorrecto, compáralo con la exportación CSV. Las sesiones nativas con más de 2 millones de muestras (`NATIVE_MAX_ROWS`) se rechazan.

Los pasos de exportación de cada programa están en la [Guía de Usuario](docs/GUIA_USUARIO.es.md#exportar-la-telemetría).

**Canales obligatorios:** `Speed`, `Brake`, `Throttle`. Si falta alguno o no tiene valores numéricos, la API responde `400` con un mensaje que lista las columnas encontradas.

**Distancia:** si el canal `Distance` no existe (o nunca supera 10 m), se sintetiza integrando `Speed` sobre un reloj de tiempo válido (`LR/HR/MR Sample Clock`, `SessionTime`, `Time`, `Lap Time`; se rechaza un reloj que sea una onda cuadrada 0/1; como último recurso `Session Time Left`, luego el cronómetro de vuelta y por último 100 Hz fijos). Las respuestas con metadatos (`/api/compare-session-laps`, `/api/report/pdf`) fijan `metadata.distance_synthetic = true`. La distancia sintética sirve para el análisis de stint y de sesión; la comparación entre vueltas y la vuelta óptima son más fiables con un canal de distancia real.

**Canales reconocidos (nombre canónico: ejemplos de alias aceptados):**

| Grupo | Nombres canónicos | Ejemplos de alias |
|---|---|---|
| Núcleo | `Speed`, `Brake`, `Throttle`, `Distance`, `Gear`, `RPM` | `Ground Speed`, `Brake Pos`, `Throttle Pos`, `Lap Distance` |
| Dinámica | `SteerAngle`, `LateralG`, `LongitudinalG`, `YawRate` | `Steering Angle`, `CG Accel Lateral`, `CG Accel Longitudinal`, `Chassis Yaw Rate` |
| Vueltas y tiempo | `LapTime`, `SessionLapCount` | `Lap Time`, `Session Lap Count`, `Lap` |
| Posición | `CarCoordX/Y/Z` | `Car Coord X` |
| Clima | `AirTemp`, `RoadTemp` | `Air Temp`, `Road Temp` |
| Temperatura de neumáticos (4 zonas x 4 esquinas) | `TyreTemp{Core,Inner,Middle,Outer}{FL,FR,RL,RR}` | `Tire Temp Core FL`, `LFtempCL` |
| Presión de neumáticos | `TyrePress{FL..RR}`, `TyrePressCold{FL..RR}` | `Tire Pressure FL`, `LFpressure`, `LFcoldPressure` |
| Recorrido de suspensión | `SuspTravel{FL..RR}` | `Suspension Travel FL`, `LFshockDefl` |
| Frenos | `BrakeTemp{FL..RR}`, `BrakeBias` | `Brake Temp FL`, `dcBrakeBias` |
| Fluidos | `WaterTemp`, `OilTemp` | `Coolant Temp`, `Eng Oil Temp` |

La tabla completa de alias es `COLUMN_ALIASES` en `src/io/loaders.py`. Los canales opcionales ausentes no abortan el análisis: el panel afectado se declara no disponible.

## Circuitos conocidos y nombres de curva

`src/data/circuits.json` (19 circuitos), lógica en `src/analytics/circuits.py`. El circuito se reconoce por el `Venue` de la cabecera de telemetría (alias como `imola`, `fn_imola`, `ks_spa`) y se contrasta con la longitud de vuelta medida (tolerancia 4 %). Las respuestas incluyen un objeto `circuit` (`id`, `name`, `short_name`, `country`, `length_m`, `recognized`, `matched`, `confidence`, `named_corners`, `measured_length_m`, `length_deviation_pct`) y cada curva y apex recibe un `corner_name` (nulo si no se conoce). La interfaz muestra "Curva 4 - Tamburello" mediante el helper `frontend/src/utils/cornerLabel.js`.

- **Solo Imola y Spa-Francorchamps tienen nombres de curva** (confianza `high`; las posiciones se ajustaron con vueltas reales). Los otros 17 circuitos (Monza, Red Bull Ring, Silverstone, Brands Hatch, Mugello, Nordschleife, Barcelona, Laguna Seca, Zandvoort, Vallelunga, Magione, Mónaco, Le Mans, Sepang, Oran Park GP y South, Lime Rock GP) son **solo reconocimiento** (`confidence: medium`, sin nombres de curva).
- Si la longitud medida no encaja (probablemente otro trazado o una vuelta parcial) el circuito se marca con confianza `low` y no se asignan nombres. Un apex sin curva tabulada cerca conserva su número.
- **Regla de honestidad:** una tabla de curvas solo se publica cuando su orden y sus posiciones se verificaron con telemetría. No añadas nombres de memoria ni desde un plano sin comprobar dónde cae cada apex en una vuelta real.

Para añadir un circuito, agrega una entrada a `src/data/circuits.json` (`id`, `name`, `short_name`, `country`, `length_m`, `aliases`, `confidence`, `source`, `notes`, `corners: []`) y ejecuta `python -m pytest tests/test_circuits.py -q`; el validador `validate_database` comprueba ids, alias, orden y rangos. Añade `corners` (`order`, `name`, `apex_fraction`, estrictamente crecientes) solo con una vuelta real como evidencia y documéntalo en `source`.

## Temas

Claro, oscuro o según el sistema operativo (selector en la barra superior; la elección se guarda en el navegador). Archivos: `frontend/src/styles/theme-light.css`, `frontend/src/hooks/useTheme.js`; los tokens del tema oscuro están en `design-system.css`. `python scripts/check_contrast.py` comprueba el contraste WCAG de ambos: el tema claro pasa los 64 pares; el tema oscuro es anterior a la comprobación y tiene **10 pares por debajo de AA**, documentados como deuda conocida (se reportan, pero solo hacen fallar la ejecución con `--strict`).

## Rendimiento y subida única

La interfaz envía el archivo una vez con `POST /api/files` y luego llama a cada análisis con el `file_id` devuelto (el SHA-256 del contenido, por lo que subir dos veces el mismo archivo es idempotente). El backend guarda los frames parseados en una caché LRU en memoria (`src/io/session_cache.py`, acotada por `SESSION_CACHE_MAX_MB` y `SESSION_CACHE_TTL_MIN`); los archivos guardados viven en `UPLOAD_DIR` y se borran tras `UPLOAD_TTL_HOURS`. Si el archivo ya no está (caducó, o es otra réplica sin volumen compartido) los endpoints responden **410** y la interfaz vuelve a subirlo y reintenta. El modo clásico (enviar el archivo a cada endpoint) sigue funcionando. Los resultados son progresivos: primero aparece la tabla de la sesión y luego el análisis de stint y la vuelta óptima en paralelo.

Imola (57 MB): primer resultado en unos 2,1 s y todo en unos 2,9 s, en lugar de unos 15 s y 21 s, con un pico de 724 MB de memoria (equipo del autor). Se reproduce con `python scripts/profile_pipeline.py ARCHIVO --repeat 3` (opciones `--cprofile`, `--dump`, `--compare`).

## Notas de calidad de datos y comportamiento

- **La segmentación de vueltas** es única en todos los endpoints: por canal contador de vueltas (`Session Lap Count`, `Lap`, ...) o, si no existe, por reinicios de distancia. Los segmentos parciales de menos de 30 s se descartan. Si se encuentran menos de 2 vueltas, la API responde con un mensaje de error.
- **Vueltas de pit y atípicas:** una vuelta se marca como pit si el canal `In Pit` lo indica; las vueltas fuera del 70-115 % de la mediana también se marcan como atípicas y se excluyen de regresiones y proyecciones.
- **Las ventanas de curva no se solapan:** cada ventana se recorta en el punto medio entre ápices vecinos. El `summary` de la comparación incluye `corners_time_delta_s` (tiempo ganado/perdido dentro de curvas) y `outside_corners_delta_s` (el resto).
- **El emparejamiento de curvas** entre dos vueltas usa la distancia del ápice, no el índice de curva.
- **Valores no medibles:** `braking_delta_available` y `throttle_delta_available` indican si los deltas de frenada/acelerador se pudieron medir. Un `0.0` con `available = false` significa "no medible", no "sin diferencia".
- **Canales constantes** (por ejemplo, temperaturas de freno fijas en un valor) devuelven `available: false` con un `reason` en lugar de generar recomendaciones falsas.
- **Baja confianza:** las proyecciones con muy pocas vueltas llevan `low_confidence`, `confidence` y `reason` (ver "Proyecciones realistas").
- **Convención de signo del slip angle:** el signo de `LateralG` se detecta por su correlación con la velocidad de guiñada y se invierte si hace falta (Assetto Corsa lo registra invertido) antes de calcular el ángulo de deriva.
- **Validación de entrada:** un archivo vacío o sin los canales mínimos devuelve `400` con un mensaje claro. Las selecciones de vuelta no válidas devuelven `422`. Un archivo por encima de `MAX_UPLOAD_MB` devuelve `413`.
- **Evolución de pista** (`track_evolution`), **`health_summary`** y **`data_quality`** forman parte de las respuestas de stint y de comparación de sesión.

## Ejemplo de resultado

Validado con un Porsche Cayman GT4 Clubsport en Imola (Assetto Corsa, CSV MoTeC de ~57 MB sin canal `Distance`):

| Elemento | Valor |
|---|---|
| Vueltas detectadas | 21 (las vueltas 1 y 21 son de pit) |
| Mejor vuelta | Vuelta 11, 1:57.605 |
| Vuelta óptima (realista / teórica) | 1:54.107 (-3.498 s) / 1:52.885 (-4.720 s) |
| Rango de vueltas de carrera | 117.6 - 122.4 s |
| Longitud de pista | ~4862 m |
| Velocidad máxima | 243.9 km/h |
| Curvas por geometría | 11 |
| Consumo de combustible | 1.758 L/vuelta |
| Tendencia de degradación | -0.077 s/vuelta (el coche va más rápido al consumir combustible) |
| Tiempo de análisis | primer resultado ~2,1 s, todo ~2,9 s (equipo del autor; antes eran ~15 s / ~21 s) |

El CSV en sí no forma parte del repositorio. Las cifras de vuelta óptima se calcularon con este archivo, cuyo `Distance` se sintetizó, así que son orientativas.

## Arquitectura

```
main.py                  App FastAPI: endpoints principales, CORS, logging, límite de subida (413), mapeo de errores
src/
  api/                   Routers: files.py (subida única), library.py, optimal_lap.py, setups.py
  data/                  circuits.json (circuitos conocidos y nombres de curva)
  db/                    Modelos SQLAlchemy y motor (SQLite / PostgreSQL)
  io/                    loaders.py (CSV, alias, unidades, síntesis de distancia), ibt_loader.py, ld_loader.py,
                         native_common.py (formatos nativos experimentales), session_cache.py (almacén de subidas + caché LRU), exporters.py (informe de texto),
                         pdf_exporter.py, pdf_charts.py (informe PDF)
  processing/            alignment.py (alineación por distancia), filters.py (filtros de señal)
  telemetry/             lap_comparator.py, metrics.py, session_analyzer.py
  analytics/             Módulos avanzados (ver tabla abajo)
  i18n.py, locales/      Traducciones del backend: en.json, es.json y locales/extra/*.json
  visualization/         (paquete vacío)
alembic/, alembic.ini    Migraciones de base de datos (tablas de la biblioteca)
frontend/                React 19 + Vite + Recharts (ver frontend/README.md)
Dockerfile, docker/      Imagen del backend y entrypoint; frontend/Dockerfile + nginx.conf para la UI
docker-compose.yml       backend + frontend + postgres (+ docker-compose.override.example.yml)
k8s/                     Kustomize: base/ y overlays/local, overlays/prod
scripts/                 kind-up.sh/.ps1, kind-cluster.yaml, validate_k8s.py, dev.ps1, check_contrast.py,
                         profile_pipeline.py, make_fixtures.py,
                         datos de ejemplo y generadores de imágenes de la documentación
Makefile                 up, down, logs, test, lint, k8s-validate, kind-up, kind-down
tests/                   suite pytest (342 recogidos: 323 se ejecutan por defecto, 19 e2e omitidos), fixtures/, e2e/
data/                    laptime_history.db (historial de ML), motorsport.db (biblioteca, ignorado por git)
docs/                    Guías de usuario, guía de despliegue y documentación científica (EN/ES)
```

Módulos de `src/analytics/`:

| Módulo | Propósito | Doc |
|---|---|---|
| `geometry.py` | Curvatura y detección de ápices | [01](docs/01_geometry.es.md) |
| `alignment.py` | Alineación por distancia y time delta | [02](docs/02_time_delta.es.md) |
| `dynamics.py` | Diagrama G-G, eventos de subviraje/sobreviraje | [03](docs/03_gg_diagram.es.md), [04](docs/04_dynamics.es.md) |
| `compression.py` | Compresión RDP del payload | [02](docs/02_time_delta.es.md) |
| `insights.py` | Diagnóstico curva a curva | [01](docs/01_geometry.es.md) |
| `ml_anomaly.py` | Zonas de anomalía con Isolation Forest | [05](docs/05_anomaly_detection.es.md) |
| `ml_clustering.py` | Perfiles de estilo por curva con K-Means | [06](docs/06_clustering.es.md) |
| `ml_laptime.py` | Vuelta alcanzable (P10), consistencia, XGBoost, historial en SQLite | [07](docs/07_lap_time_potential.es.md) |
| `stint.py` | Segmentación de vueltas, métricas por vuelta, degradación, combustible, Monte Carlo, evolución de pista | [08](docs/08_stint_analysis.es.md) |
| `thermodynamics.py` | Ventana térmica de neumáticos (comparación) | [09](docs/09_thermodynamics.es.md) |
| `brake_fade.py` | Eficiencia de frenada y fade | [10](docs/10_brake_fade.es.md) |
| `driver_inputs.py` | FFT del volante, nerviosismo, solapamiento de pedales | [11](docs/11_driver_inputs.es.md) |
| `suspension.py` | Cabeceo, balanceo, tope de suspensión | [12](docs/12_suspension.es.md) |
| `slip_angle.py` | Ángulo de deriva y balance | [13](docs/13_slip_angle.es.md) |
| `thermal_management.py` | Temperaturas y presiones de neumáticos, frenos y fluidos en la sesión | [14](docs/14_thermal_management.es.md) |
| `tyre_degradation.py` | Predicción de degradación de neumáticos, detección de desgaste activo | [15](docs/15_tyre_degradation.es.md) |
| `racing_line_rl.py` | Optimización de la trazada | [16](docs/16_racing_line_rl.es.md) |
| `setup_advisor.py` | Recomendaciones de setup (comparación de vueltas y sesión) | [17](docs/17_setup_advisor.es.md) |
| `session_corner_analysis.py` | Estadísticas de curvas en todas las vueltas de una sesión | [08](docs/08_stint_analysis.es.md) |
| `session_telemetry_analysis.py` | Agregados de sesión de neumáticos, frenos, suspensión, inputs y balance | [08](docs/08_stint_analysis.es.md) |
| `circuits.py` | Circuitos conocidos, nombres de curva, objeto `circuit` | este README |
| `optimal_lap.py` | Vuelta óptima por microsectores (teórica y realista) | este README |
| `ac_setups.py` | Búsqueda y lectura de setups de Assetto Corsa, enlace "actual -> sugerido" | este README |
| `data_quality.py` | Puntuación de calidad de datos, canales, módulos, cómo mejorar | este README |
| `session_compare.py` | Comparación de dos sesiones guardadas | este README |

## API

URL base: `http://localhost:8000`. Documentación interactiva: `/docs` (Swagger). Los endpoints POST que reciben archivos usan `multipart/form-data`; los demás usan JSON. Añade `?lang=es` o `?lang=en` (si no, se usa `Accept-Language`) para elegir el idioma de mensajes e informes. Errores: `400` para archivos ilegibles o inválidos, `404` para sesiones de biblioteca inexistentes, `413` para subidas por encima de `MAX_UPLOAD_MB` (o payloads de biblioteca de más de 5 MB), `422` para selecciones no válidas (vuelta fuera de rango, misma vuelta dos veces, menos de 3 vueltas para stint), `500` para errores internos; el cuerpo es `{"detail": "..."}`.

### Análisis e informes

| Endpoint | Método | Entrada | Devuelve |
|---|---|---|---|
| `/api/health` | GET | ninguna | `{status, service, version}` |
| `/api/files` | POST | `file`: CSV, `.ibt` o `.ld` | `{file_id, filename, size_bytes, format, venue, vehicle, driver, ttl_hours}`; `413` si supera `MAX_UPLOAD_MB`, `400` si está vacío |
| `/api/files/{file_id}` | GET | id SHA-256 | `{file_id, filename, size_bytes}`, o `410` si el cliente debe volver a subirlo |
| `/api/analyze-session` | POST | `session_file` o `file_id` | JSON con `laps` (tiempo, banderas de pit/atípica), `fastest_lap`, `track_map`, `total_laps`, `circuit`, `data_quality`. Si no se puede segmentar ninguna vuelta, `laps` vacío y un `message`. |
| `/api/stint/analyze` | POST | `laps`: un archivo de sesión, o 3 o más archivos de una vuelta; o `file_id` de una sesión | `laps`, `degradacion`, `combustible`, `montecarlo`, `curvas_sesion`, `telemetria_sesion`, `setup_sesion`, `thermal_analysis`, `degradacion_neumatico`, `racing_line_rl`, `track_evolution`, `health_summary`, `data_quality` |
| `/api/optimal-lap` | POST | `session_file` o `file_id`; opcionales `microsector_m` (por defecto 25), `speed_tol_kmh` (por defecto 3) | Vuelta óptima teórica y realista, ganancias, microsectores, zonas, curvas, contribuciones, avisos (ver "Vuelta óptima") |
| `/api/compare-laps` | POST | `lap_a`, `lap_b` | Comparación básica: `summary`, comparaciones de velocidad/freno/acelerador, `time_delta_series`, `corners`, `track_map`, `metadata`, `text_report`, `setup_advisor` y los resultados de los módulos avanzados cuando estén disponibles |
| `/api/telemetry/analyze` | POST | `lap_fast`, `lap_slow` (o `lap_fast_id`, `lap_slow_id`); query `resolution_m` (por defecto 5) | Pipeline avanzado: `telemetria`, `curvatura`, `apexes`, `sectores`, `corners`, `gg_diagram`, `g_limit`, `dynamic_events`, `anomaly`, `corner_clusters`, `tiempo_potencial`, `xgboost_pred`, resultados de neumáticos/frenos/inputs/suspensión/slip, `data_quality` |
| `/api/telemetry/compare` | POST | `lap_fast`, `lap_slow`; query `resolution_m` | Subconjunto de geometría y time delta: `metadata`, `telemetria`, `curvatura`, `apexes`, `sectores`, `corners` |
| `/api/compare-session-laps` | POST | `session_file` o `file_id`, `lap_a`, `lap_b` (base 1; `0` = automático: vuelta voladora más rápida y más lenta) | Comparación completa de dos vueltas de una sesión; `metadata` incluye `distance_synthetic`; también `health_summary`, `data_quality` |
| `/api/report/pdf` | POST | `session_file`, `lap_a`, `lap_b` | Adjunto `application/pdf` `report_V{a}_vs_V{b}.pdf` |
| `/api/report/pdf-from-json` | POST | JSON: un resultado de comparación ya calculado | Adjunto `application/pdf`, sin recalcular |
| `/api/report/session-pdf-from-json` | POST | JSON: `{session, stint, comparison, metadata}` (`session` con `laps` es obligatorio; el resto opcional) | PDF de sesión `motorsport_<circuito>_<coche>_<fecha>.pdf`, sin recalcular |

### Setups de Assetto Corsa (`/api/setups`)

| Endpoint | Método | Entrada | Devuelve |
|---|---|---|---|
| `/api/setups/detect` | POST | `header`: primeros bytes del archivo de telemetría (máx. 64 KB), o `file_id` | Coche, circuito y piloto leídos de la cabecera MoTeC |
| `/api/setups/candidates` | GET | query `vehicle`, `venue`, `lang` | Setups candidatos: `track_setups`, `generic_last`, `state` (`track_setups`, `generic_only`, `none`, `no_access`), `needs_confirmation` |
| `/api/setups/file` | GET | query `vehicle`, `setup_id`, `venue`, `lang` | Setup leído (por identificador devuelto en `candidates`, nunca por ruta directa) |
| `/api/setups/parse` | POST | `file`: un `.ini` de setup (máx. 256 KB); query `vehicle` | Setup subido, ya interpretado |
| `/api/setups/annotate` | POST | JSON `{setup, recommendations}` (máx. 500 recomendaciones) | Recomendaciones anotadas con valores actual y sugerido |

### Biblioteca de sesiones (`/api/library`)

| Endpoint | Método | Entrada | Devuelve |
|---|---|---|---|
| `/api/library` | POST | JSON: metadatos (`title`, `vehicle`, `venue`, `driver`, `notes`, `file_sha256`, ...) y `payload` `{session, stint, extras}` (máx. 5 MB) | `{status: created o updated, duplicate, session}` |
| `/api/library` | GET | query `q`, `venue`, `vehicle`, `date_from`, `date_to`, `limit` (1-200), `offset` | `{items, total, limit, offset}` sin el payload pesado |
| `/api/library/facets` | GET | ninguna | Circuitos, coches y combinaciones circuito+coche con recuentos |
| `/api/library/sniff` | POST | `head`: primeros KB de un CSV (máx. 256 KB) | Circuito, coche y piloto de la cabecera MoTeC |
| `/api/library/compare` | POST | JSON `{a, b, force}` (UUID de sesiones) | Diferencias de ritmo, consistencia, combustible y por curva, compatibilidad y avisos; `400` si difieren circuito o coche y `force` es falso |
| `/api/library/{id}` | GET | UUID | Resumen más el `payload` guardado |
| `/api/library/{id}` | PATCH | JSON con cualquiera de `title`, `notes`, `venue`, `vehicle`, `driver` | Resumen actualizado |
| `/api/library/{id}` | DELETE | UUID | `{status: "deleted", id}` |

Notas:

- Los endpoints que leen una sesión (`analyze-session`, `compare-session-laps`, `optimal-lap`, `stint/analyze`, `setups/detect`) aceptan el campo de formulario `file_id` en lugar del archivo; `telemetry/analyze` acepta `lap_fast_id` y `lap_slow_id`. Un id desconocido o caducado responde `410`, uno mal formado `422`.
- La interfaz llama a `POST /api/files`, luego a `/api/analyze-session` y luego a `/api/stint/analyze` para una sesión, a `/api/optimal-lap` en segundo plano, a `/api/compare-laps` más `/api/telemetry/analyze` para dos archivos, a `/api/compare-session-laps` para pares de vueltas y a los endpoints PDF para los botones de descarga.
- `/api/telemetry/analyze` añade una observación a `data/laptime_history.db`, que alimenta con el tiempo las capas históricas de P10 y XGBoost.
- Un módulo que no puede ejecutarse devuelve `{"available": false, ...}` (a menudo con `reason`) en lugar de hacer fallar toda la petición.

## Configuración

Copia `.env.example` a `.env` (se carga con `python-dotenv`; Docker Compose también lo lee).

| Variable | Valor por defecto | Efecto |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000` | Orígenes permitidos separados por coma |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `TEMP_DIR` | `<proyecto>/tmp` | Directorio de archivos temporales de subida (se borran tras cada petición) |
| `API_HOST` / `API_PORT` / `API_RELOAD` | `0.0.0.0` / `8000` / `false` | Solo se usan al ejecutar `python main.py` |
| `MAX_UPLOAD_MB` | `2048` | Tamaño máximo **por archivo subido**. Lo aplica el backend (HTTP 413, se borra el archivo parcial); nginx y el Ingress derivan su límite de cuerpo de este valor |
| `NATIVE_MAX_ROWS` | `2000000` | Máximo de muestras aceptadas para `.ibt` / `.ld` tras el remuestreo |
| `DATABASE_URL` | `sqlite:///data/motorsport.db` | Base de datos de la biblioteca. PostgreSQL en contenedores: `postgresql+psycopg://user:pass@host:5432/db` |
| `STORAGE_DIR` | `./data/storage` | Directorio opcional para archivos originales |
| `UPLOAD_DIR` | `STORAGE_DIR/uploads` si hay `STORAGE_DIR`, si no `TEMP_DIR/uploads` | Dónde guarda `POST /api/files` las subidas (usa un volumen compartido con varias réplicas) |
| `UPLOAD_TTL_HOURS` | `24` | Las subidas sin uso durante este tiempo se borran |
| `SESSION_CACHE_MAX_MB` | `1024` | Memoria máxima de la caché de sesiones parseadas por proceso |
| `SESSION_CACHE_TTL_MIN` | `60` | Minutos sin uso antes de sacar una sesión de la caché |
| `AC_SETUPS_DIR` | automático (`<Documentos>\Assetto Corsa\setups`) | Carpeta explícita de setups de Assetto Corsa |
| `VITE_API_URL` | `http://localhost:8000/api` | URL de la API que usa el frontend en desarrollo (la lee Vite en build/dev; los contenedores de producción usan `/api` relativo) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `motorsport` / `change-me-local-only` / `motorsport` | Solo Compose. Valores de ejemplo para una máquina local, nunca para producción |
| `FRONTEND_PORT` / `BACKEND_DEV_PORT` | `8080` / `8010` | Puertos del host en Compose (UI; backend con `--profile dev`) |
| `UVICORN_WORKERS` | `1` | Workers de uvicorn en el contenedor (cada uno mantiene su propia memoria) |
| `RUN_MIGRATIONS` | `0` en la imagen, `1` en Compose | Ejecuta `alembic upgrade head` al iniciar el contenedor |
| `PROXY_TIMEOUT` | `900s` | Timeout del proxy nginx en el contenedor del frontend |

## Desarrollo y tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests -q          # 342 recogidos; los 19 e2e se omiten salvo con E2E=1

cd frontend
npm run lint                       # ESLint
npm run build                      # build de producción en frontend/dist

make lint                          # yamllint + scripts/validate_k8s.py + lint del frontend
make k8s-validate                  # validación estática de los manifiestos de Kubernetes
```

Tests con datos reales y de navegador: `tests/fixtures/*.csv.gz` son recortes anonimizados de exportaciones reales de Assetto Corsa (se regeneran con `scripts/make_fixtures.py`) usados por `tests/test_regression_real.py`. Los tests end-to-end y visuales (Playwright + Edge) están en `tests/e2e/` y solo corren con `E2E=1`; las líneas base visuales pueden requerir regenerarse con `E2E_UPDATE_BASELINE=1` en otra máquina. Detalles en [tests/README.md](tests/README.md).

Archivos de test en `tests/`: `test_alignment.py`, `test_loaders.py`, `test_metrics.py`, `test_session_pipeline.py`, `test_optimal_lap.py`, `test_ac_setups.py`, `test_library.py`, `test_data_quality.py`, `test_pdf_report.py`, `test_formats.py`, `test_projection_realism.py`, `test_upload_limit.py`, `test_k8s_manifests.py`, `test_circuits.py`, `test_perf_cache.py`, `test_check_contrast.py`, `test_regression_real.py`, `test_visual_tool.py` (fixtures en `tests/conftest.py`). Se pueden generar vueltas sintéticas con `python scripts/generate_sample_data.py` (escribe `data/raw/lap_clean.csv` y `data/raw/lap_errors.csv`, ignorados por git).

### Añadir textos traducidos

Los textos del backend y del frontend viven en dos diccionarios por idioma (`en`, `es`) que se amplían **por módulo de función**, para que los colaboradores no tengan que editar los archivos centrales, que son muy grandes:

- Frontend: crea `frontend/src/i18n/extra/<funcion>.en.js` y `<funcion>.es.js` con `export default { clave: 'texto' }` (los valores pueden ser funciones, p. ej. `(n) => ...`). Se cargan automáticamente (`import.meta.glob`) y se fusionan en `en.js` / `es.js`.
- Backend: crea `src/locales/extra/<funcion>.en.json` y `<funcion>.es.json` (clave plana a texto, con `{marcadores}`). `src/i18n.py` fusiona todos los archivos de esa carpeta en el primer uso. Usa `_l(lang, clave, ...)` o `_()`.

Añade siempre ambos idiomas y mantén las claves únicas entre módulos. Ver [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentación

| Público | Documento |
|---|---|
| Usuarios | [Guía de Usuario](docs/GUIA_USUARIO.es.md), [Referencia Rápida](docs/REFERENCIA_RAPIDA.es.md) |
| Operación | [Despliegue: local, Docker, Kubernetes](docs/DEPLOYMENT.es.md) |
| Desarrolladores | [Índice de docs](docs/README.es.md) con los 17 documentos científicos de módulos (matemáticas, algoritmos, figuras), [frontend/README.md](frontend/README.md), [CONTRIBUTING.md](CONTRIBUTING.md) |
| Inglés | [README.md](README.md), [User Guide](docs/USER_GUIDE.md), [Quick Reference](docs/QUICK_REFERENCE.md), [Deployment](docs/DEPLOYMENT.md), [docs/README.md](docs/README.md) |

## Limitaciones conocidas

- La detección de curvas por velocidad encuentra menos curvas que la basada en geometría (7 frente a 11 en Imola, porque las chicanes se fusionan).
- El tope de suspensión es heurístico: recorrido igual o superior al 90 % del máximo observado.
- Algunos canales pueden faltar según el simulador y la exportación; los paneles correspondientes lo indican en lugar de adivinar.
- El CSV es la entrada estable. `.ibt` de iRacing y `.ld` de MoTeC son **experimentales**: probados con 53 archivos reales de un solo autor, sin probar otros simuladores y coches.
- La vuelta óptima teórica crece al achicar el microsector, y con un `Distance` sintetizado la vuelta óptima es solo orientativa.
- Las unidades de los setups solo se muestran donde son seguras; los datos cifrados del coche (`data.acd`) nunca se abren, así que faltan los rangos en la mayoría de coches.
- **Sin autenticación ni autorización.** La biblioteca la comparte cualquiera que alcance la API (la columna `owner_id` está reservada para el futuro). No expongas la aplicación a internet tal cual.
- Los archivos de Docker, Compose y Kubernetes solo se han validado de forma estática (ver [Despliegue](#despliegue)).
- Los payloads de biblioteca están limitados a 5 MB; las subidas muy grandes necesitan memoria y tiempo (el límite es por archivo, `MAX_UPLOAD_MB`).

## Contribuir

Consulta [CONTRIBUTING.md](CONTRIBUTING.md). En resumen: fork, rama, ejecuta `python -m pytest tests -q` y abre un Pull Request contra `main`. No subas archivos de telemetría ni secretos.

## Licencia

[MIT](LICENSE) - Copyright (c) 2026 Andres Gutierrez.
