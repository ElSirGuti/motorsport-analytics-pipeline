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

## 📁 Estructura del Proyecto

- `main.py` - Backend FastAPI (Endpoints y gestión de telemetría)
- `src/` - Lógica central del motor de telemetría (Carga, Alineación, Comparación, Exportación)
- `frontend/` - Interfaz de usuario (React + Vite, Recharts para gráficos)
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
3. **Alineación Espacial:** A diferencia de la telemetría temporal tradicional, interpolamos cúbicamente todas las vueltas a un eje X uniforme basado en la **distancia** (1 metro de resolución).
4. **Detección de Métricas (Curvas):** Algoritmos identifican automáticamente zonas de frenado profundo (>5%), apex (mínimos locales de velocidad en el paso por curva) y puntos de aceleración total (>98%).
5. **Comparación y Visualización:** Generación de deltas precisos en metros y segundos, enviando el JSON final al frontend para su renderizado con Recharts interactivo.
