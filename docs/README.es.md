# Documentación — Motorsport Analytics Pipeline

[Read in English](./README.md)

---

## Guías para el Usuario

| Documento | Para quién |
|-----------|-----------|
| [Guía de Usuario](./GUIA_USUARIO.es.md) | Pilotos, ingenieros y cualquier persona que use la app: cómo usarla, funciones de sesión (calidad de datos, vuelta óptima, setups de Assetto Corsa, biblioteca, informe PDF, circuitos, tema, comparar dos archivos de una vuelta), exportar telemetría, interpretar cada panel y solución de problemas. |
| [Referencia Rápida](./REFERENCIA_RAPIDA.es.md) | Cheat sheet para consulta rápida durante sesión: tablas de estados, diagnósticos frecuentes, vuelta óptima, modo comparar con dos archivos, puntuación de calidad de datos, enlace con el setup, formatos, límites y códigos de estado. |

---

## Documentación del Proyecto

| Documento | Contenido |
|-----------|-----------|
| [README principal](../README.es.md) | Inicio rápido, instalación, funciones, formatos, tabla de la API, configuración, tests, arquitectura |
| [Despliegue](./DEPLOYMENT.es.md) | Local, Docker Compose y Kubernetes (Kustomize); contrato de variables (todas), instalación de Docker/kind en Windows, caché de subida única, qué se verificó en Docker Compose y kind y qué no, solución de problemas del primer despliegue |
| [Tests](../tests/README.md) | Suites de tests (571 recogidos; 541 se ejecutan por defecto, 30 e2e requieren `E2E=1`), fixtures reales anonimizados, tests del modo comparar dos archivos, tests end-to-end y visuales (en inglés) |
| [README del frontend](../frontend/README.md) | Estructura de la UI, sistema de diseño y temas, cliente de API, módulos i18n, build y lint (en inglés, con resumen en español) |
| [CONTRIBUTING](../CONTRIBUTING.md) | Cómo contribuir: flujo, traducciones por módulo, tests, sin datos personales (en inglés, con resumen en español) |
| [LICENSE](../LICENSE) | Licencia MIT |

---

## Documentación de Funciones

Estas funciones no tienen un documento científico aparte; se describen en el README principal (diseño, límites, API) y en la Guía de Usuario (cómo usarlas).

| Función | Código | Documentación |
|---------|--------|---------------|
| Vuelta óptima por microsectores | `src/analytics/optimal_lap.py`, `src/api/optimal_lap.py` | [README](../README.es.md#vuelta-óptima-por-microsectores), [Guía](./GUIA_USUARIO.es.md#vuelta-óptima-por-microsectores) |
| Setups de Assetto Corsa | `src/analytics/ac_setups.py`, `src/api/setups.py` | [README](../README.es.md#integración-de-setups-de-assetto-corsa), [Guía](./GUIA_USUARIO.es.md#setups-de-assetto-corsa) |
| Biblioteca y comparar sesiones | `src/api/library.py`, `src/db/`, `src/analytics/session_compare.py`, `alembic/` | [README](../README.es.md#biblioteca-de-sesiones-y-comparar-sesiones), [Guía](./GUIA_USUARIO.es.md#biblioteca-de-sesiones-y-comparar-sesiones) |
| Calidad de datos | `src/analytics/data_quality.py` | [README](../README.es.md#panel-de-calidad-de-datos), [Guía](./GUIA_USUARIO.es.md#panel-de-calidad-de-datos) |
| Informe PDF | `src/io/pdf_exporter.py`, `src/io/pdf_charts.py` | [README](../README.es.md#informe-pdf), [Guía](./GUIA_USUARIO.es.md#informe-pdf) |
| Formatos `.ibt` y `.ld` (experimentales) | `src/io/ibt_loader.py`, `ld_loader.py`, `native_common.py` | [README](../README.es.md#formatos-de-telemetría), [Guía](./GUIA_USUARIO.es.md#formatos-soportados) |
| Circuitos conocidos y nombres de curva | `src/data/circuits.json`, `src/analytics/circuits.py` | [README](../README.es.md#circuitos-conocidos-y-nombres-de-curva), [Guía](./GUIA_USUARIO.es.md#circuitos-conocidos-y-nombres-de-curva) |
| Temas | `frontend/src/styles/theme-light.css`, `scripts/check_contrast.py` | [README](../README.es.md#temas), [README del frontend](../frontend/README.md#design-system-and-themes) |
| Subida única y caché | `src/api/files.py`, `src/io/session_cache.py`, `scripts/profile_pipeline.py` | [README](../README.es.md#rendimiento-y-subida-única), [Despliegue](./DEPLOYMENT.es.md#subir-una-vez-file_id-y-la-caché-de-análisis) |
| Proyecciones realistas | `src/analytics/stint.py`, `tyre_degradation.py` | [README](../README.es.md#proyecciones-realistas), módulos [08](./08_stint_analysis.es.md) y [15](./15_tyre_degradation.es.md) |

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
| 14 | [Gestión Térmica](./14_thermal_management.es.md) | Análisis térmico de fluidos, frenos y presión de neumáticos con recomendaciones por reglas |
| 15 | [Modelo de Degradación de Neumáticos](./15_tyre_degradation.es.md) | Tasa de degradación corregida por combustible, detección de desgaste activo, proyección del cliff |
| 16 | [Optimización de Línea de Carrera (RL)](./16_racing_line_rl.es.md) | Q-learning tabular por curva sobre intervalos de frenada / ápice / acelerador |
| 17 | [Asesor de Configuración del Vehículo](./17_setup_advisor.es.md) | Recomendaciones de setup por reglas (vuelta y sesión) y vinculación con el setup de Assetto Corsa |
| 18 | [Incidentes](./18_incidents.es.md) | Detección de trompos, derrapes salvados y salidas de pista con causa probable puntuada y consejo |

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

Cada script escribe en `docs/images/{módulo}/`. Los módulos 14-17 (gestión térmica, degradación de neumáticos, línea de carrera, asesor de configuración) no tienen generador de imágenes. Los documentos científicos 01-17 describen los algoritmos tal como se escribieron originalmente; donde el comportamiento actual difiere (por ejemplo las proyecciones de stint, más conservadoras), el README principal es la referencia vigente.

Ejecuta los scripts desde la raíz del proyecto con las dependencias de `requirements.txt` instaladas.

---

## Convenciones

- **Variables en negrita**: parámetros configurables en el código fuente
- Ecuaciones escritas en notación LaTeX inline: `$κ = ...$`
- Umbrales empíricos justificados con referencia bibliográfica cuando aplica
- Código Python reproducible con `numpy.random.seed` fijo donde se usan simulaciones
