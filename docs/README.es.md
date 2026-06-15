# Documentación — Motorsport Analytics Pipeline

---

## Guías para el Usuario

| Documento | Para quién |
|-----------|-----------|
| [Guía de Usuario](./GUIA_USUARIO.es.md) | Pilotos, ingenieros y cualquier persona que use la app. Explica cómo interpretar cada sección en lenguaje simple. |
| [Referencia Rápida](./REFERENCIA_RAPIDA.es.md) | Cheat sheet para consulta rápida durante sesión: tablas de estados, diagnósticos frecuentes y flujo de análisis. |

---

## Documentación Técnica

Documentación científica de todos los módulos de análisis. Cada sección incluye los fundamentos matemáticos, el algoritmo implementado, interpretación de resultados y visualizaciones generadas.

---

## Módulos

| # | Módulo | Descripción |
|---|--------|-------------|
| 01 | [Geometría de Pista](./01_geometry.es.md) | Filtro Savitzky-Golay, curvatura geométrica κ, detección de apexes |
| 02 | [Time Delta](./02_time_delta.es.md) | Interpolación cúbica, alineación por distancia, RDP de compresión |
| 03 | [Diagrama GG](./03_gg_diagram.es.md) | Círculo de fricción, G-efficiency, estimación cinemática de G |
| 04 | [Dinámica del Vehículo](./04_dynamics.es.md) | Subviraje / sobreviraje, tres niveles de severidad |
| 05 | [Detección de Anomalías](./05_anomaly_detection.es.md) | Isolation Forest, puntuación multivariable, extracción de zonas |
| 06 | [Clustering de Estilo](./06_clustering.es.md) | K-Means, perfiles de conducción, mapa de calor por curva |
| 07 | [Tiempo Potencial](./07_lap_time_potential.es.md) | Reachable Lap P10, consistencia, XGBoost con explicaciones |
| 08 | [Análisis de Stint](./08_stint_analysis.es.md) | Degradación lineal, estrategia de combustible, Monte Carlo |
| 09 | [Temperatura de Neumáticos](./09_thermodynamics.es.md) | Ventana térmica óptima, gradiente ΔT superficie–núcleo, estrés térmico |
| 10 | [Brake Fade](./10_brake_fade.es.md) | Eficiencia \|LonG\|/presión, detección de fade por zona y baseline |
| 11 | [Inputs del Piloto](./11_driver_inputs.es.md) | Welch PSD sobre SteerAngle, índice de nerviosismo, solapamiento freno-gas |
| 12 | [Suspensión](./12_suspension.es.md) | Pitch y roll desde SuspTravel FL/FR/RL/RR, detección de bottoming |
| 13 | [Ángulo de Deslizamiento](./13_slip_angle.es.md) | Sideslip β cinemático, αF/αR modelo bicicleta, balance de pista |

---

## Imágenes

Las imágenes son generadas por los scripts en `scripts/docs/`. Para regenerarlas:

```bash
python scripts/docs/gen_geometry.py
python scripts/docs/gen_time_delta.py
python scripts/docs/gen_gg_diagram.py
python scripts/docs/gen_dynamics.py
python scripts/docs/gen_anomaly.py
python scripts/docs/gen_clustering.py
python scripts/docs/gen_laptime.py
python scripts/docs/gen_stint.py
python scripts/docs/gen_thermodynamics.py
python scripts/docs/gen_brake_fade.py
python scripts/docs/gen_driver_inputs.py
python scripts/docs/gen_suspension.py
python scripts/docs/gen_slip_angle.py
```

Cada script escribe en `docs/images/{módulo}/`.

---

## Convenciones

- **Variables en negrita**: parámetros configurables en el código fuente
- Ecuaciones escritas en notación LaTeX inline: `$κ = ...$`
- Umbrales empíricos justificados con referencia bibliográfica cuando aplica
- Código Python reproducible con `numpy.random.seed` fijo donde se usan simulaciones
