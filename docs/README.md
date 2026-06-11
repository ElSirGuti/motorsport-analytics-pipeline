# Documentación Técnica — Motorsport Analytics Pipeline

Documentación científica de todos los módulos de análisis. Cada sección incluye los fundamentos matemáticos, el algoritmo implementado, interpretación de resultados y visualizaciones generadas.

---

## Módulos

| # | Módulo | Descripción |
|---|--------|-------------|
| 01 | [Geometría de Pista](./01_geometry.md) | Filtro Savitzky-Golay, curvatura geométrica κ, detección de apexes |
| 02 | [Time Delta](./02_time_delta.md) | Interpolación cúbica, alineación por distancia, RDP de compresión |
| 03 | [Diagrama GG](./03_gg_diagram.md) | Círculo de fricción, G-efficiency, estimación cinemática de G |
| 04 | [Dinámica del Vehículo](./04_dynamics.md) | Subviraje / sobreviraje, tres niveles de severidad |
| 05 | [Detección de Anomalías](./05_anomaly_detection.md) | Isolation Forest, puntuación multivariable, extracción de zonas |
| 06 | [Clustering de Estilo](./06_clustering.md) | K-Means, perfiles de conducción, mapa de calor por curva |
| 07 | [Tiempo Potencial](./07_lap_time_potential.md) | Reachable Lap P10, consistencia, XGBoost con explicaciones |
| 08 | [Análisis de Stint](./08_stint_analysis.md) | Degradación lineal, estrategia de combustible, Monte Carlo |

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
```

Cada script escribe en `docs/images/{módulo}/`.

---

## Convenciones

- **Variables en negrita**: parámetros configurables en el código fuente
- Ecuaciones escritas en notación LaTeX inline: `$κ = ...$`
- Umbrales empíricos justificados con referencia bibliográfica cuando aplica
- Código Python reproducible con `numpy.random.seed` fijo donde se usan simulaciones
