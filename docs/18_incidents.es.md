# 18 - Incidentes: trompos, derrapes salvados y salidas de pista

Módulo `src/analytics/incidents.py`, textos en `src/locales/extra/incidents.{en,es}.json`, interfaz `frontend/src/components/IncidentsPanel.jsx`. El resultado es el objeto `incidents` de `POST /api/analyze-session` y `POST /api/stint/analyze`; el panel está en la sección de stint.

[View in English](./18_incidents.md)

## Qué detecta

| `kind` | Significado |
|---|---|
| `spin` | El coche se puso de lado hasta apuntar hacia atrás (ángulo de deslizamiento máximo >= 100 °) o giró >= 150 °. |
| `slide` | Un derrape grande que se salvó (ángulo máximo entre 45 y 100 °, menos de 150 ° de giro). |
| `off_track` | Las ruedas salieron de la pista (dos o más ruedas, o una con un nivel de suciedad alto). |

Un trompo y una salida de pista separados menos de 3 s son un solo evento (`went_off: true`). Una salida que cruza la línea de meta se une entre las dos vueltas. Se ignoran los eventos con velocidad inferior a 30 km/h al inicio, en el pit lane, o con una sola rueda rozando un piano.

## Señales (usa lo mejor que tenga el registro)

| Necesidad | 1.ª opción | 2.ª | 3.ª |
|---|---|---|---|
| Ángulo de deslizamiento | velocidad del chasis `BodyVelX/Y` (ACTI: `Chassis Velocity X/Y`), `atan2(vy, vx)` | posición + velocidad de guiñada: giro que la trayectoria no explica en 2 s (se autocalibra: las unidades y el signo cambian entre loggers; se descarta si posición y guiñada no concuerdan) | solo guiñada (>= 120 ° en 2,5 s con caída de velocidad o una guiñada muy alta) |
| Salida de pista | suciedad de neumáticos `Dirt*` (ACTI `Tire Dirt Level`): solo sube mientras una rueda está en el césped | `TrackSurface` (iRacing `PlayerTrackSurface`, 0 = fuera de pista) | distancia a la línea mediana de las otras vueltas (necesita 3 vueltas y posición) |

`summary.slip_source` y `summary.off_track_source` (y `sources`) indican cuál se usó; la interfaz lo muestra. Si el registro no tiene señal para un detector, ese detector simplemente no dice nada.

## Diagnóstico de la causa

Para cada evento lee los 3 s previos y los compara con lo que hicieron **las otras vueltas** en el mismo punto (mediana en +-25 m). Cada causa es la suma de evidencias (0..1) con los números que la respaldan; se devuelven las principales con puntuación >= 0,25 y su `confidence` (`high` >= 0,7 con margen, `medium` >= 0,45, `low`).

| Código | Evidencia usada |
|---|---|
| `too_much_throttle` | acelerador >= 35 % al inicio (y subiendo / por encima de otras vueltas), patinaje trasero (`SlipRatio`), ángulo de deslizamiento trasero mayor que el delantero |
| `lift_off` | el acelerador cayó >= 35 puntos en 0,6 s con carga lateral >= 0,6 g y sin frenar |
| `braking_instability` | freno >= 20 % con volante, ruedas traseras más lentas que las delanteras (bloqueo), más freno que otras vueltas |
| `too_much_steering` | volante por encima de otras vueltas en esa curva, o una entrada de volante muy rápida (>= 250 °/s) |
| `late_correction` | sin contravolante en 0,45 s desde el derrape, o uno muy pequeño (requiere velocidad del chasis) |
| `overcorrection` | el ángulo de deslizamiento osciló > 30 ° hacia ambos lados en 3 s |
| `entry_too_fast` | velocidad de entrada por encima de otras vueltas (>= 4 km/h o >= 3 %) |
| `low_grip` | neumáticos más fríos que la mediana de la sesión, neumáticos sucios, agarre de superficie < 95 %, menos g lateral de lo habitual, vuelta temprana o lenta |
| `kerb_or_bump` | pico de aceleración vertical (o de velocidad del recorrido de suspensión) |
| `downshift` | bajó la marcha en los últimos 0,8 s sin freno ni acelerador |
| `wind` | solo con viento >= 15 km/h a >= 150 km/h y poca g lateral; confianza baja por diseño |
| `understeer_off` | salida de pista con las delanteras deslizando más que las traseras, o ya en la g lateral habitual |

## Límites (también se dicen en la interfaz)

- Las causas son **inferencias** a partir de inputs y estado del coche, no una certeza.
- No se ven contactos con otros coches, zonas húmedas ni baches fuera de los canales registrados.
- Viento: solo se conoce su intensidad; su dirección está en un sistema de referencia que cambia entre simuladores, así que nunca cuenta como causa principal. No se evalúa si el registro no tiene canal de viento.
- Con pocas vueltas no hay referencia: se omiten las comparaciones con "tus otras vueltas" (hacen falta al menos 2 vueltas más en ese punto).
- `lap_delta_s` (tiempo que perdió la vuelta) solo se da cuando las vueltas limpias dan una referencia utilizable.

## Salida

`incidents = { available, events[], summary, sources }`. Cada evento: `id`, `lap`, `kind`, `went_off`, `severity` (`minor|moderate|major`), `t_s`, `distance_m`, `fraction`, `duration_s`, `peak_slip_deg`, `rotation_deg`, `min_speed_kmh`, `off_track {peak_dirt, wheels, duration_s}`, `lap_time_s`, `lap_delta_s`, `lap_invalidated`, `corner {corner_number, corner_name, corner_kind}` (del mapa unificado de curvas), `context`, `primary_cause`, `causes[] {code, score, confidence, label, advice, evidence[]}` y un `trace` (+-4 s alrededor del inicio: velocidad, acelerador, freno, volante, deslizamiento, g lateral). `summary` trae los conteos por tipo, las causas más frecuentes y `hot_spots` (curvas con 2 o más incidentes).

## Canales extra que hizo falta

`src/io/loaders.py` (`COLUMN_ALIASES`) mapea ahora, para CSV, `.ld` e `.ibt`: `BodyVelX/Y`, `Dirt{FL,FR,RL,RR}`, `SlipAngle*`, `SlipRatio*`, `WheelSpeed*`, `TyreLoad*`, `TyreGrip*`, `WindSpeed`, `WindDir`, `SurfaceGrip`, `VerticalG`, `TCActive`, `ABSActive`, `LapInvalid` y `TrackSurface`. Los que falten simplemente no aparecen. El `OnPitRoad` de iRacing alimenta ahora `InPit`.

## Tests

`tests/test_incidents.py` (sesiones sintéticas con un trompo por acelerador, un derrape salvado, salida de pista por suciedad, pianos, el respaldo solo con guiñada, puntos calientes, nombre de curva, paridad de claves EN/ES, ambos endpoints y fixtures reales: Imola limpio no da ningún evento y la sesión de Spa da su único trompo real) y `tests/e2e/test_e2e_flows.py::test_incidents_panel_shows_spin_and_cause`.
