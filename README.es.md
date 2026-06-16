# Motorsport Analytics Pipeline — El Analista Automatizado

Plataforma full-stack para el análisis automatizado de telemetría de Assetto Corsa (ACTI) y otros simuladores compatibles con MoTeC. 

Esta herramienta alinea las vueltas por distancia y detecta automáticamente eventos clave como puntos de frenado, vértices de curva (apex) y puntos de aceleración para generar un reporte detallado y visual curva por curva.

## ✨ Características Principales

- 🏁 **Comparación Multi-Vuelta:** Soporta la carga y comparación simultánea de hasta 6 vueltas, con colores y etiquetas automáticas.
- 🔍 **Zoom Interactivo por Curva:** Al hacer clic en las tarjetas de análisis de curvas, los gráficos hacen zoom automáticamente en la zona de frenado y aceleración de esa curva específica.
- 🆔 **Detección Inteligente de Identidad:** Extrae la metadata del CSV de MoTeC (Piloto, Vehículo, Circuito) para generar etiquetas dinámicas e identificar diferencias (ej. advierte si estás comparando distintos vehículos).
- 📋 **Reporte de Ingeniero Exportable:** Genera un resumen en texto plano, curva por curva, con un botón integrado para copiar al portapapeles.
- 🌡️ **Temperatura de Neumáticos:** Análisis térmico completo por neumático (Inner/Middle/Outer/Core), detección de ventana óptima de operación (configurable), gradiente ΔT superficie–núcleo y % de tiempo en estrés térmico.
- 🔴 **Brake Fade — Eficiencia de Frenado:** Ratio |LonG| / presión de pedal en todas las zonas de frenada. Detecta automáticamente la degradación de eficiencia a lo largo del stint y localiza zonas de fade térmico.
- 🎮 **Análisis de Inputs del Piloto (FFT):** Welch PSD sobre el canal SteerAngle para cuantificar micro-correcciones de alta frecuencia. Índice de nerviosismo normalizado + % solapamiento freno-gas por vuelta.
- 🔧 **Suspensión — Pitch & Roll:** Pitch y roll del chasis desde los 4 canales SuspTravel, detección de eventos de fondo (bottoming) con severidad, máximos de transferencia de carga dinámica.
- 📐 **Ángulo de Deslizamiento (Sideslip β):** Integración cinemática de Vy_dot = LateralG·g − YawRate·Vx para estimar β del chasis. Cálculo de αF y αR con modelo de bicicleta; balance de pista (subviraje vs sobreviraje) por distancia.
- 🗺️ **Mapeo de Pista:** Visualización simplificada de la trazada del circuito basada en coordenadas GPS/Juego.
- ◎ **Diagrama G-G (Círculo de Fricción):** Visualiza el agarre disponible del vehículo con puntos coloreados por eficiencia de G-Sum. Muestra el límite de adherencia (percentil 95) y la distribución de fuerzas longitudinales y laterales.
- ⚠️ **Detección de Subviraje y Sobreviraje:** Algoritmo que analiza derivadas del ángulo de volante y G-Lateral para identificar pérdida de agarre delantero (subviraje) o trasero (sobreviraje) en cada curva, con severidad y diagnóstico textual.
- 🗜️ **Compresión RDP (Ramer-Douglas-Peucker):** Reduce el payload de telemetría hasta un 80% preservando la forma de las curvas de velocidad y delta, con retención forzada de apexes para mantener precisión en zonas críticas.
- 🗃️ **Vista Unificada:** Todos los análisis (básico + avanzado) se presentan en una sola página scrollable sin pestañas ni toggles, cargados en paralelo.

## 📁 Estructura del Proyecto

- `main.py` - Backend FastAPI (Endpoints y gestión de telemetría)
- `src/` - Lógica central del motor de telemetría
  - `io/` - Carga y exportación de datos (loaders, exporters)
  - `processing/` - Alineación espacial y filtros (alignment, filters)
  - `telemetry/` - Comparación de vueltas y análisis de sesión (lap_comparator, session_analyzer)
  - `analytics/` - Módulos de análisis avanzado
    - `geometry.py` - Geometría de pista, detección de apexes por curvatura
    - `alignment.py` - Alineación de vueltas y cálculo de time delta
    - `insights.py` - Generación de insights técnicos curva por curva
    - `dynamics.py` - Círculo de fricción (G-Sum, eficiencia), detección de subviraje/sobreviraje
    - `compression.py` - Compresión Ramer-Douglas-Peucker (RDP) para reducción de payload
    - `thermodynamics.py` - Análisis térmico de neumáticos: ventana de temperatura, ΔT, estrés
    - `brake_fade.py` - Eficiencia de frenado y detección de brake fade por zona
    - `driver_inputs.py` - FFT Welch sobre SteerAngle, índice de nerviosismo, solapamiento freno-gas
    - `suspension.py` - Pitch, roll y bottoming desde canales SuspTravel FL/FR/RL/RR
    - `slip_angle.py` - Ángulo de deslizamiento β (cinemático), αF/αR y balance de pista
- `frontend/` - Interfaz de usuario (React + Vite, Recharts para gráficos)
  - `src/components/` - Componentes React (SpeedChart, BrakeThrottleChart, TimeDeltaChart, TrackMap, CornerReport, GGDiagramChart, etc.)
  - `src/api/` - Cliente Axios para comunicación con la API
  - `src/api/cursorStore.js` - Store sincrónico para cursor entre gráficas (rendimiento 60fps)
- `scripts/` - Utilidades adicionales (ej. generador de datos sintéticos)
- `data/` - Directorio para guardar archivos CSV crudos

## ⚙️ Instalación

### Requisitos previos

| Herramienta | Versión mínima | Descarga |
|---|---|---|
| Python | 3.10 | https://www.python.org/downloads/ |
| Node.js | 18 LTS | https://nodejs.org/ |
| Git | cualquiera | https://git-scm.com/ |

### 1 — Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/motorsport-analytics-pipeline.git
cd motorsport-analytics-pipeline
```

### 2 — Backend (Python)

```bash
# Crear y activar entorno virtual (recomendado)
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 3 — Frontend (Node.js)

```bash
cd frontend
npm install
cd ..
```

### 4 — Ejecutar la app

Abre **dos terminales** desde la raíz del proyecto:

**Terminal 1 — API Backend:**
```bash
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Abre el navegador en **http://localhost:5173**.

---

## 📡 Guía de Exportación de Telemetría

### Assetto Corsa — Plugin ACTI

[ACTI (AC Telemetry Interface)](https://www.assettocorsa.net/forum/index.php?threads/acti-ac-telemetry-interface.50534/) graba telemetría compatible con MoTeC directamente desde Assetto Corsa.

**Configuración:**
1. Descarga e instala el plugin ACTI en la carpeta `apps/python/` de Assetto Corsa.
2. En Assetto Corsa ve a **Opciones → General** y activa las **Apps de Python**.
3. En sesión, habilita la app **ACTI** desde la barra de apps del HUD.
4. ACTI grabará automáticamente un archivo `.ldx` / CSV crudo por vuelta. Por defecto en `Documentos\Assetto Corsa\logs\`.
5. Para exportar a CSV: abre **MoTeC i2**, conecta el archivo de log y sigue los pasos de exportación MoTeC indicados abajo.

### iRacing — Logging de telemetría

iRacing puede escribir un archivo `.ibt` de telemetría de forma nativa.

**Activar en iRacing:**
1. Abre `Documentos\iRacing\app.ini` con un editor de texto.
2. Busca (o agrega) la sección `[Telemetry]` y configura:
   ```
   logToDisk=1
   diskSamplingRate=60
   ```
3. Alternativamente, ve a **Opciones → Telemetría → Grabar en disco** en la interfaz de iRacing (si está disponible en tu versión).
4. Los archivos `.ibt` se guardan en `Documentos\iRacing\telemetry\`.
5. Usa **MoTeC i2 Pro** (con el workspace de iRacing) o herramientas de terceros (p.ej. *ibt2csv*) para convertir `.ibt` → `.csv`.

### MoTeC i2 — Exportar a CSV

MoTeC i2 es la herramienta de análisis de datos profesional para visualizar y exportar telemetría de ACTI, iRacing y otras fuentes.

**Exportar una vuelta específica:**
1. Abre MoTeC i2 y carga tu archivo de log (**Archivo → Abrir**).
2. Navega a la vuelta deseada en el panel **Laps**.
3. Ve a **Archivo → Exportar → Exportar a hoja de cálculo (CSV)**.
4. En el diálogo: selecciona el **rango de tiempo** de esa vuelta, elige **Todos los canales**, configura la frecuencia de salida (60 Hz recomendado) y haz clic en **Exportar**.

**Exportar un stint completo:**
1. Selecciona el rango de tiempo de toda la sesión (desde la Vuelta 1 hasta la última) en el panel Laps.
2. Sigue los mismos pasos de **Archivo → Exportar → CSV**.
3. El CSV resultante contendrá todas las vueltas como un dataset continuo — la app segmentará automáticamente las vueltas individuales detectando transiciones de velocidad cero.

**Canales requeridos para análisis completo:**

| Categoría | Nombres típicos de canal |
|---|---|
| Velocidad | `Speed`, `Ground Speed` |
| Distancia | `Lap Distance`, `Distance` |
| Freno / Gas | `Brake Pos`, `Throttle Pos` |
| G Lateral / Longitudinal | `Lateral Acc`, `Longitudinal Acc` |
| Velocidad de guiñada | `Yaw Rate` |
| Ángulo de volante | `Steer Angle` |
| Temp. neumáticos | `Tyre Temp FL`, `Tyre Temp FR`, `Tyre Temp RL`, `Tyre Temp RR` |
| Viaje de suspensión | `Susp Travel FL`, `Susp Travel FR`, `Susp Travel RL`, `Susp Travel RR` |

Los canales faltantes simplemente desactivan el panel de análisis correspondiente — la app degrada de forma elegante.

---

## 🏎️ Uso Rápido

```bash
# Backend
python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (otra terminal)
cd frontend && npm install && npm run dev
```

Abre **http://localhost:5173**, sube un CSV exportado desde MoTeC i2 y haz clic en **Analizar Sesión Completa**.

## 🏗️ Arquitectura del Pipeline

El pipeline utiliza la siguiente arquitectura matemática y lógica:
1. **Ingesta y Metadatos:** Pandas carga los CSVs, lee las cabeceras (Driver, Vehicle) y valida/limpia los canales esenciales (Speed, Brake, Throttle, Distance).
2. **Filtros de Señal:** Suavizado (media móvil) y limpieza de outliers de sensores ruidosos para evitar falsos positivos en las derivadas.
3. **Geometría de Pista y Apexes:** Cálculo de curvatura dinámica para detectar puntos de entrada, apex y salida de curva mediante máximos de curvatura y mínimos de velocidad.
4. **Alineación Espacial:** A diferencia de la telemetría temporal tradicional, interpolamos cúbicamente todas las vueltas a un eje X uniforme basado en la **distancia** (1 metro de resolución), con canales extra como LateralG, LongitudinalG y SteerAngle.
5. **Círculo de Fricción (G-G Diagram):** Cálculo de G-Sum (√(G_Lat² + G_Long²)) por muestra, límite de adherencia como percentil 95 del G-Sum, y eficiencia de agarre por punto.
6. **Detección de Subviraje/Sobreviraje:** Análisis de derivadas del steering angle en ventanas de apex. Subviraje = volante sigue girando pero G-Lat no aumenta. Sobreviraje = pico abrupto de G-Lat con corrección simultánea de volante.
7. **Comparación y Visualización:** Generación de deltas precisos en metros y segundos, compresión RDP del payload (preservando apexes), envío del JSON final al frontend para renderizado con Recharts interactivo.
8. **Persistencia de Estado:** Los componentes de cada pestaña permanecen montados (ocultos via CSS) al cambiar de tab, preservando archivos cargados y resultados sin recarga. Cursor tracking fuera de React (módulo store + rAF + DOM directo) para 60fps sin re-renders.

### Endpoints de la API REST

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/compare-laps` | POST | Comparación simple de 2 vueltas (SpeedChart, TrackMap, CornerReport) |
| `/api/telemetry/compare` | POST | Pipeline avanzado con geometría, time delta y sectorización |
| `/api/telemetry/analyze` | POST | Pipeline completo: geometría + time delta + círculo de fricción + eventos dinámicos + compresión RDP |
| `/api/analyze-session` | POST | Análisis de sesión completa con múltiples vueltas |
| `/api/analyze` | POST | Pipeline completo con IA: geometría + time delta + Isolation Forest + K-Means + XGBoost + P10 |
| `/api/stint/analyze` | POST | Análisis multi-vuelta: degradación lineal + estrategia de combustible + Monte Carlo 500 sims |

## 🤖 Pipeline de Inteligencia Artificial

El sistema incluye tres modelos de IA que se activan progresivamente según el historial acumulado en `data/laptime_history.db`:

### Isolation Forest — Anomaly Detection
Entrena sobre la vuelta rápida (estado de referencia normal) y puntúa la vuelta lenta punto a punto. Zonas con score > 0.60 se identifican como anomalías de conducción.
- **Siempre activo** — no requiere datos históricos
- Documentación: [docs/05_anomaly_detection.md](./docs/05_anomaly_detection.md)

### K-Means — Perfiles de Estilo por Curva
Clasifica cada curva en perfiles semánticos: *Ataque Limpio*, *Entrada Agresiva*, *Conservador*, *Salida Tardía*. Permite comparar el estilo de conducción entre circuitos y vueltas.
- **Siempre activo** — basado en los datos de la vuelta actual
- Documentación: [docs/06_clustering.md](./docs/06_clustering.md)

### Reachable Lap (P10) + Consistencia + XGBoost
Tres capas de análisis de tiempo potencial:
1. **P10 Histórico** — activa con ≥3 observaciones por curva: tiempo estadísticamente alcanzable en el 10% mejor
2. **Score de Consistencia** — `max(0, 100 × (1 − σ/|μ|))`: qué tan repetible es el piloto curva por curva
3. **XGBoost** — activa con ≥30 observaciones totales: predice el óptimo y explica el gap con los top-2 factores limitantes
- Documentación: [docs/07_lap_time_potential.md](./docs/07_lap_time_potential.md)

### Stint Analysis — Monte Carlo
Pipeline completo para análisis de carrera completa:
- Degradación de tiempo de vuelta: regresión lineal β₁ (s/vuelta)
- Estrategia de combustible con ventana de pit calculada con consumo conservador (media + 1.65σ)
- 500 simulaciones Monte Carlo reproducibles (`seed=42`) con bandas P10/P25/P50/P75/P90
- Documentación: [docs/08_stint_analysis.md](./docs/08_stint_analysis.md)

## 📖 Guías de Usuario

Para interpretar los resultados de la app en lenguaje simple:

| Documento | Descripción |
|-----------|-------------|
| [Guía de Usuario](./docs/GUIA_USUARIO.md) | Cómo usar la app y qué significa cada análisis. Sin matemáticas. |
| [Referencia Rápida](./docs/REFERENCIA_RAPIDA.md) | Tablas de estados, umbrales y diagnósticos frecuentes para consulta durante sesión. |

---

## 📚 Documentación Científica

Todos los módulos están documentados con fundamentos matemáticos, pseudocódigo y visualizaciones matplotlib:

| Módulo | Documento |
|--------|-----------|
| Geometría de pista y detección de apexes | [docs/01_geometry.md](./docs/01_geometry.md) |
| Time Delta y alineación por distancia | [docs/02_time_delta.md](./docs/02_time_delta.md) |
| Diagrama GG y círculo de fricción | [docs/03_gg_diagram.md](./docs/03_gg_diagram.md) |
| Subviraje / sobreviraje (3 niveles de severidad) | [docs/04_dynamics.md](./docs/04_dynamics.md) |
| Isolation Forest — detección de anomalías | [docs/05_anomaly_detection.md](./docs/05_anomaly_detection.md) |
| K-Means — clustering de estilo de conducción | [docs/06_clustering.md](./docs/06_clustering.md) |
| Reachable Lap, Consistencia y XGBoost | [docs/07_lap_time_potential.md](./docs/07_lap_time_potential.md) |
| Análisis de stint y simulación Monte Carlo | [docs/08_stint_analysis.md](./docs/08_stint_analysis.md) |
| Temperatura de Neumáticos — ventana térmica y ΔT | [docs/09_thermodynamics.md](./docs/09_thermodynamics.md) |
| Brake Fade — eficiencia y degradación de frenado | [docs/10_brake_fade.md](./docs/10_brake_fade.md) |
| Inputs del Piloto — FFT y nerviosismo de volante | [docs/11_driver_inputs.md](./docs/11_driver_inputs.md) |
| Suspensión — pitch, roll y bottoming | [docs/12_suspension.md](./docs/12_suspension.md) |
| Ángulo de Deslizamiento — sideslip β y balance αF/αR | [docs/13_slip_angle.md](./docs/13_slip_angle.md) |

Ver índice completo en [docs/README.md](./docs/README.md).
