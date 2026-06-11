# Motorsport Analytics Pipeline — El Analista Automatizado

Plataforma full-stack para el análisis automatizado de telemetría de Assetto Corsa (ACTI) y otros simuladores compatibles con MoTeC. 

Esta herramienta alinea las vueltas por distancia y detecta automáticamente eventos clave como puntos de frenado, vértices de curva (apex) y puntos de aceleración para generar un reporte detallado y visual curva por curva.

## ✨ Características Principales

- 🏁 **Comparación Multi-Vuelta:** Soporta la carga y comparación simultánea de hasta 6 vueltas, con colores y etiquetas automáticas.
- 🔍 **Zoom Interactivo por Curva:** Al hacer clic en las tarjetas de análisis de curvas, los gráficos hacen zoom automáticamente en la zona de frenado y aceleración de esa curva específica.
- 🆔 **Detección Inteligente de Identidad:** Extrae la metadata del CSV de MoTeC (Piloto, Vehículo, Circuito) para generar etiquetas dinámicas e identificar diferencias (ej. advierte si estás comparando distintos vehículos).
- 📋 **Reporte de Ingeniero Exportable:** Genera un resumen en texto plano, curva por curva, con un botón integrado para copiar al portapapeles.
- 🌡️ **Datos Atmosféricos:** Extrae y muestra la temperatura de pista y ambiente directamente de la telemetría.
- 🗺️ **Mapeo de Pista:** Visualización simplificada de la trazada del circuito basada en coordenadas GPS/Juego.
- ◎ **Diagrama G-G (Círculo de Fricción):** Visualiza el agarre disponible del vehículo con puntos coloreados por eficiencia de G-Sum. Muestra el límite de adherencia (percentil 95) y la distribución de fuerzas longitudinales y laterales.
- ⚠️ **Detección de Subviraje y Sobreviraje:** Algoritmo que analiza derivadas del ángulo de volante y G-Lateral para identificar pérdida de agarre delantero (subviraje) o trasero (sobreviraje) en cada curva, con severidad y diagnóstico textual.
- 🗜️ **Compresión RDP (Ramer-Douglas-Peucker):** Reduce el payload de telemetría hasta un 80% preservando la forma de las curvas de velocidad y delta, con retención forzada de apexes para mantener precisión en zonas críticas.
- 🗃️ **Persistencia entre Pestañas:** Los archivos cargados y resultados de análisis se mantienen al cambiar entre las pestañas de Comparación, Análisis Avanzado y Sesión, evitando recargas innecesarias.

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
- `frontend/` - Interfaz de usuario (React + Vite, Recharts para gráficos)
  - `src/components/` - Componentes React (SpeedChart, BrakeThrottleChart, TimeDeltaChart, TrackMap, CornerReport, GGDiagramChart, etc.)
  - `src/api/` - Cliente Axios para comunicación con la API
  - `src/api/cursorStore.js` - Store sincrónico para cursor entre gráficas (rendimiento 60fps)
- `scripts/` - Utilidades adicionales (ej. generador de datos sintéticos)
- `data/` - Directorio para guardar archivos CSV crudos

## ⚙️ Requisitos

- Python 3.10+
- Node.js 18+

## 🚀 Instalación

1. **Backend (Python)**
```bash
pip install -r requirements.txt
```

2. **Frontend (React)**
```bash
cd frontend
npm install
```

## 🏎️ Uso Rápido

1. **Iniciar el Backend (API):**
```bash
uvicorn main:app --reload --port 8000
```

2. **Iniciar el Frontend (en otra terminal):**
```bash
cd frontend
npm run dev
```

3. **Probar la app:**
Abre `http://localhost:5173` en tu navegador, sube tus archivos CSV exportados por ACTI (ej. `vuelta_lenta.csv` y `vuelta_rapida.csv`) y haz clic en "Analizar".

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
