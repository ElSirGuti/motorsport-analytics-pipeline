# Guía de Usuario — Motorsport Analytics Pipeline

[Read in English](./USER_GUIDE.md)

Esta guía explica, en lenguaje sencillo, cómo usar la aplicación y qué significan los resultados de cada análisis. No necesitas saber matemáticas ni ingeniería para interpretarlos.

---

## Primeros Pasos

### ¿Qué hace esta herramienta?

Analiza telemetría y te dice **dónde ganás tiempo, dónde lo perdés y por qué**. Funciona de dos maneras:

- **Sesión completa (1 CSV):** la sesión se divide automáticamente en vueltas y obtenés una tabla de vueltas, análisis de stint (ritmo, combustible, neumáticos, ventana de pit) y recomendaciones de setup.
- **Comparación de vueltas (2 CSV, o 2 vueltas elegidas de una sesión):** una comparación lado a lado con diagnóstico curva a curva y los análisis avanzados (neumáticos, frenos, suspensión, estilo de pilotaje, balance).

### Archivos que necesitás

Archivos CSV exportados desde **MoTeC i2** (Assetto Corsa vía ACTI, iRacing). Mirá [Exportar la telemetría](#exportar-la-telemetría) para los pasos y los canales que la app entiende.

### Cómo empezar

1. Instalá e iniciá el backend y el frontend (ver el [README](../README.es.md#inicio-rápido)) y abrí `http://localhost:5173`.
2. En la barra superior elegí el idioma (ES/EN) y el modo: **Ingeniero** (todo) o **Piloto** (paneles técnicos ocultos).
3. Soltá tu(s) archivo(s) CSV en el área de carga. Un archivo se trata como sesión completa; dos archivos se tratan como dos vueltas sueltas a comparar.
4. Presioná analizar. Una barra de progreso muestra los pasos. Los archivos grandes pueden tardar varios minutos (una sesión de ~57 MB tardó unos 25 s); mantené la pestaña abierta.
5. Al terminar, el área de carga se compacta en una barra de archivo. Presioná **Nuevo análisis** para empezar de nuevo.

---

## La Interfaz de un Vistazo

La barra superior contiene la marca, el selector de idioma y el interruptor Piloto/Ingeniero. Un **riel lateral** permite saltar entre secciones. El resto de la página es una sola vista larga: **mover el ratón sobre cualquier gráfico sincroniza la posición del cursor en todos los demás**.

### Sesión completa (1 CSV)

| Sección | Qué muestra |
|---------|-------------|
| **Resumen de sesión** | Tabla de vueltas, mejor vuelta, panel de salud, mapa de pista |
| **Análisis de stint** | Evolución del tiempo por vuelta, degradación, estrategia de combustible, ventana de pit, proyección Monte Carlo, evolución de pista |
| **Setup y estrategia** | Análisis de curvas de toda la sesión, degradación de neumáticos, gestión térmica, trazada y recomendaciones de setup |

**Tabla de vueltas:** marcá **dos vueltas (A/B)** y presioná **Comparar** para abrir una comparación completa de esas vueltas, o presioná **Mejor vs Peor** para comparar automáticamente la vuelta flying más rápida con la más lenta. Las vueltas marcadas **PIT** (entrada/salida de boxes) y **atípicas** (tiempo muy lejos de la mediana) se excluyen de las estadísticas de degradación y proyección.

**Panel de salud:** lista los módulos de análisis (térmico, setup, degradación de neumáticos, trazada, slip, curvas) como disponibles o no disponibles. No disponible suele significar que el CSV no contiene los canales que ese módulo necesita.

### Comparación de vueltas (2 CSV, o 2 vueltas de una sesión)

| Sección | Qué muestra |
|---------|-------------|
| **Vuelta base** | Resumen, curva de velocidad + time delta acumulado, superposición de freno y acelerador, mapa de pista, análisis de curvas y sectores |
| **Dinámica del vehículo** | Diagrama G-G, neumáticos, frenos, suspensión, ángulo de deslizamiento (oculta en modo Piloto) |
| **Piloto y entradas** | Estilo de volante y pedales (oculta en modo Piloto) |
| **Estrategia y setup** | Potencial de vuelta, anomalías, recomendaciones de setup y reporte de ingeniero (copiar como texto o descargar como PDF) |

Hacé clic en una curva del análisis de curvas y todos los gráficos hacen zoom a esa zona.

---

## Cómo Leer Cada Análisis

---

### Velocidad y Time Delta

**¿Qué ves?**
- Curva de velocidad de ambas vueltas superpuestas
- Una línea de "delta" que sube y baja

**Cómo interpretarlo:**
- La línea de delta **sube** → la Vuelta A está **perdiendo tiempo** respecto a B en esa zona
- La línea de delta **baja** → la Vuelta A está **ganando tiempo**
- Si la delta termina en positivo (ej. `+0.8s`), la Vuelta A es más lenta en esa cantidad

**Ejemplo práctico:**
> La delta sube de golpe en la frenada de la curva 3 → llegás tarde al freno o frenás demasiado.  
> La delta baja en la salida de curva 5 → tu salida de curva es mejor que la otra vuelta.

**Zoom por curva:** Hacé clic en cualquier curva de la tabla de análisis y todos los gráficos hacen zoom automático en esa zona.

---

### Freno y Acelerador

**¿Qué ves?**
- Dos líneas de presión de freno (0–100%) superpuestas
- Dos líneas de posición de acelerador (0–100%) superpuestas

**Cómo interpretarlo:**
- Si una línea de freno empieza **antes** que la otra → ese piloto frena antes (más conservador o necesita más distancia)
- Si las curvas de gas tienen formas distintas en la salida de curva → diferencia de punto de aceleración o progresión de gas

**Lo que buscás:**
- Que el freno suelte y el gas abra sin solapamiento importante
- Una progresión de gas suave y progresiva en curvas lentas

---

### Mapa de Pista

Muestra el circuito dibujado a partir de las coordenadas GPS/juego. El punto se mueve en sincronía con el cursor en los otros gráficos, así podés ubicarte en la pista mientras analizás datos.

---

### Diagrama G-G (Círculo de Fricción)

**¿Qué ves?**
- Una nube de puntos que muestra todas las combinaciones de fuerza lateral y longitudinal durante la vuelta
- Un círculo que representa el límite de agarre estimado

**Cómo interpretarlo:**
- **Puntos cerca del borde del círculo** → el piloto está usando bien el agarre disponible
- **Puntos en el centro** → hay agarre sin usar (frenadas o curvas conservadoras)
- **Esquinas vacías** (sin puntos en combinaciones diagonal) → el piloto no está combinando frenado + giro o aceleración + giro eficientemente

**La eficiencia G-Sum** que aparece en el resumen (0–100%) indica qué tan bien se está aprovechando el agarre total en promedio.

---

### Análisis de Curvas

**¿Qué ves?**
- Una tarjeta por curva detectada con: tiempo ganado/perdido, diagnóstico de frenada, diagnóstico de salida

**Los estados de cada zona:**

| Color | Significado |
|---------------|-------------|
| Verde | Sin problema detectado |
| Amarillo | Diferencia leve (0.05–0.15s) |
| Rojo | Diferencia importante (>0.15s) |

**Diagnósticos frecuentes que verás:**
- *"Frena tarde / llega caliente"* → el punto de frenado está comprimido, se pierde tiempo por sobrecalentamiento de la maniobra
- *"Subviraje en apex"* → el coche se va recto en el vértice, pérdida de velocidad
- *"Lenta la progresión de gas"* → el acelerador se abre demasiado despacio en la salida

---

### Temperatura de Neumáticos

**¿Qué ves?**
- Temperatura de cada neumático (FL, FR, RL, RR) con sus 4 zonas: Interior, Medio, Exterior y Núcleo
- Un estado de color por neumático
- El porcentaje de tiempo que pasó en la ventana óptima

**Los estados:**

| Color | Estado | Temperatura | Qué hacer |
|-------|--------|-------------|-----------|
| Azul claro | Frío | < 65°C | El neumático no agarra bien. Normal en el primer par de vueltas. |
| Azul | Subóptimo | 65–80°C | Casi listo. No forzar la dirección todavía. |
| Verde | Óptimo | 80–100°C | El neumático está en su rango. Podés atacar. |
| Naranja | Caliente | 100–115°C | Agarre comienza a bajar. Cuidado con sobrecargas en curvas largas. |
| Rojo | Sobrecalentado | > 115°C | El neumático está degradado. Pierde agarre rápidamente. |

**El gradiente ΔT (Superficie − Núcleo):**
- Si ΔT > 20°C → el núcleo no alcanzó la temperatura de trabajo o hay estrés mecánico interno
- Un ΔT bajo y uniforme → el neumático trabaja bien en todo su espesor

**Patrones frecuentes:**

| Patrón | Causa probable |
|--------|---------------|
| Interior mucho más caliente que exterior | Presión de inflado demasiado alta |
| Exterior mucho más caliente que interior | Presión demasiado baja o demasiado camber negativo |
| Todos los neumáticos fríos toda la vuelta | Pista fría o vuelta de instalación |
| Solo los traseros sobrecalentados | Sobreviraje / entrada de potencia excesiva |
| Solo los delanteros sobrecalentados | Subviraje / frenadas muy agresivas |

---

### Brake Fade — Eficiencia de Frenado

**¿Qué ves?**
- Una puntuación de eficiencia de frenado por vuelta (0–100)
- Zonas de fade marcadas en el mapa de pista
- Comparación contra el baseline (referencia de las primeras frenadas)

**Cómo interpretarlo:**

La eficiencia mide **cuánta desaceleración produces por cada 1% de presión de pedal**. Si presionás fuerte y el coche no frena igual que al principio del stint → hay fade.

| Puntuación | Significado |
|------------|-------------|
| > 90 | Frenos en perfectas condiciones |
| 75–90 | Degradación leve, normal en vueltas largas |
| 60–75 | Fade moderado. Posible sobrecalentamiento. |
| < 60 | Fade severo. El coche no frena como debería. Riesgo de accidente. |

**Zonas de fade:**
- Las barras rojas en el mapa de distancia marcan dónde se detectó caída de eficiencia >15% respecto al baseline
- Si el fade siempre aparece en la misma curva → hay un problema específico de refrigeración en esa frenada

**Consejo práctico:**
> Si el fade aparece recién en las últimas vueltas del stint, es normal (degradación térmica acumulada). Si aparece desde la vuelta 2–3, el sistema de frenos puede estar subdimensionado o los conductos de aire están bloqueados.

---

### Inputs del Piloto — Estilo de Conducción

**¿Qué ves?**
- Un índice de **nerviosismo** (0–100%) por vuelta
- La distribución de frecuencias de las correcciones de volante (FFT)
- El porcentaje de solapamiento freno-gas

**El índice de nerviosismo:**

| Rango | Interpretación |
|-------|---------------|
| 0–20% | Piloto muy suave. Entradas limpias y estables. |
| 20–40% | Normal. Algo de actividad en curvas difíciles. |
| 40–60% | Piloto reactivo. Muchas micro-correcciones. Posible understeer crónico que se combate con el volante. |
| 60–80% | Muy nervioso. El coche probablemente no está equilibrado. |
| 80–100% | Extremo. El piloto está luchando contra el coche. |

**Las bandas de frecuencia (FFT):**

| Banda | Frecuencia | Qué representa |
|-------|-----------|----------------|
| Baja | < 0.5 Hz | Entradas de trazada: curvas largas, cambios de dirección lentos |
| Media | 0.5–2 Hz | Balance del coche: respuesta a perturbaciones normales |
| Alta | > 2 Hz | Micro-correcciones: el piloto está "salvando" situaciones |

Un piloto más rápido normalmente tiene **más potencia en banda baja** (hace las cosas antes) y **menos en banda alta** (no necesita corregir tanto).

**Solapamiento freno-gas:**
- Un % alto (>15%) no siempre es malo: en algunos coches es técnica de equilibrio
- En la mayoría de los casos, solapamiento alto = pedales mal coordinados = tiempo perdido

---

### Suspensión — Pitch, Roll y Bottoming

**¿Qué ves?**
- Curvas de roll (inclinación lateral) y pitch (inclinación longitudinal) a lo largo de la vuelta
- Eventos de bottoming detectados (cuándo toca fondo el amortiguador)

**Roll (inclinación lateral):**
- **Roll positivo** → el coche se inclina hacia la derecha (curva a derecha)
- **Roll negativo** → se inclina hacia la izquierda (curva a izquierda)
- Si el roll es muy alto → el coche tiene poca rigidez de barras estabilizadoras o los muelles son demasiado blandos

**Pitch (inclinación longitudinal):**
- **Pitch negativo** (morro hacia abajo) → zona de frenada
- **Pitch positivo** (cola hacia abajo) → zona de aceleración
- Picadas exageradas bajo frenada → muelles delanteros blandos o poco amortiguamiento

**Bottoming — Eventos de fondo:**

Un evento de fondo se marca cuando el recorrido de la suspensión llega al 90 % o más del recorrido máximo observado en el archivo (una heurística, no un límite medido). Es problemático porque:
- El coche se pone rígido de golpe (pérdida de agarre)
- La aerodinámica se desestabiliza
- Puede dañar la carrocería

| Severidad | Descripción |
|-----------|-------------|
| 90-95% | Cerca del límite pero controlado (90 % es el umbral de detección) |
| 95–98% | Fondo frecuente. Recomendable ajustar ride height o muelles |
| > 98% | Fondo severo. El coche está tocando mecánicamente |

> Si el bottoming siempre ocurre en la misma curva → revisar la altura de carrocería en esa zona de la pista (bump) o bajar la velocidad de compresión de los amortiguadores.

---

### Ángulo de Deslizamiento — Balance del Coche

**¿Qué ves?**
- El ángulo β (beta) del chasis: cuánto se desliza lateralmente el centro de gravedad del coche
- El balance αF − αR: si el coche tiende a subvirar o a sobrevirarse

**El ángulo β (sideslip):**

| β | Significado |
|---|-------------|
| 0–2° | Neutro. El coche sigue la dirección de las ruedas. |
| 2–5° | Algo de deslizamiento. Normal en vueltas rápidas con un coche equilibrado. |
| > 5° | Deslizamiento significativo. El coche trabaja fuera de su punto óptimo. |
| > 8° | El coche está al límite del control. Posible sobreviraje pendiente de salida. |

**El balance αF − αR:**

| Valor | Interpretación |
|-------|----------------|
| > +2° | **Subviraje**: las ruedas delanteras deslizan más que las traseras. El coche se va recto. |
| −2° a +2° | **Neutro**: el coche responde como se espera. |
| < −2° | **Sobreviraje**: las ruedas traseras deslizan más. La cola tiende a salir. |

**¿Cómo usar este dato?**

Si ves subviraje constante en las curvas de media/alta velocidad → el setup delantero necesita más agarre (más presión, más camber, menos rigidez de barra delantera).

Si ves sobreviraje en la salida de curvas lentas → el acelerador se abre demasiado pronto, o el diferencial está muy abierto.

**El porcentaje US/Neutral/OS:**
- Un coche bien equilibrado debería tener >60% neutro durante la vuelta
- Si tienes >30% de tiempo en subviraje → el setup delantero es dominante

---

### Reporte de Ingeniero

El botón **"Copiar Reporte"** genera un texto listo para pegar en un grupo de WhatsApp, Notion, o un correo. Contiene:
- Metadatos de la sesión
- Resumen de diferencias por curva
- Los puntos más importantes del análisis avanzado

---

## Glosario Rápido

| Término | Definición simple |
|---------|-------------------|
| **Delta** | Diferencia de tiempo acumulada entre dos vueltas |
| **Apex / Vértice** | El punto más cercano al interior de la curva |
| **Pitch** | El coche se inclina hacia adelante o atrás (como cuando frenás de golpe en bicicleta) |
| **Roll** | El coche se inclina a los costados en las curvas |
| **Bottoming** | El amortiguador llega a su límite de recorrido y toca fondo |
| **Subviraje** | El coche "se va recto" en vez de girar. Las ruedas delanteras pierden agarre. |
| **Sobreviraje** | La cola del coche tiende a salir. Las ruedas traseras pierden agarre. |
| **Fade** | Los frenos pierden eficiencia por sobrecalentamiento |
| **β (beta)** | Ángulo de deslizamiento lateral del chasis completo |
| **FFT / PSD** | Análisis de frecuencias de las correcciones del volante |
| **Nerviosismo** | Índice que mide cuántas micro-correcciones de volante hace el piloto |
| **ΔT** | Diferencia de temperatura entre la superficie y el núcleo del neumático |
| **Stint** | Período de carrera entre dos paradas en boxes |
| **G lateral / longitudinal** | Fuerza sentida en curvas (lateral) o bajo freno/aceleración (longitudinal) |

---

## Exportar la telemetría

La app lee **únicamente archivos CSV**. Exportalos desde el programa que uses:

**Assetto Corsa (ACTI + MoTeC i2)**
1. Grabá la sesión con la app de telemetría ACTI (mirá la documentación de ACTI para instalarla).
2. Abrí el log en **MoTeC i2** y usá **File -> Export -> Export to Spreadsheet (CSV)**.
3. Para una **vuelta suelta**, seleccioná el rango de tiempo de esa vuelta; para una **sesión completa**, seleccioná todo el rango (de la vuelta 1 a la última). Exportá todos los canales, idealmente a 60 Hz o más.
4. El bloque de cabecera del CSV de MoTeC (Driver, Vehicle, Venue) se lee automáticamente y se usa para las etiquetas.

**iRacing**
1. iRacing graba archivos `.ibt`; la app no lee `.ibt` directamente. Convertilos a CSV con MoTeC i2 o una herramienta de terceros.
2. El cargador detecta las exportaciones de iRacing por las columnas `SessionTime`, `Session Time` o `SessionLapCount` y normaliza las unidades (velocidad m/s a km/h, pedales 0-1 a 0-100, suspensión m a mm, presión de neumáticos kPa/PSI a bar).

**Canales obligatorios:** `Speed`, `Brake`, `Throttle`. Si falta alguno, la API devuelve un error `400` con las columnas que encontró.

**Canales y alias reconocidos** (el cargador los renombra automáticamente; la tabla completa es `COLUMN_ALIASES` en `src/io/loaders.py`):

| Categoría | Nombre canónico | Ejemplos de nombres aceptados |
|-----------|-----------------|-------------------------------|
| Velocidad | `Speed` | `Speed`, `Ground Speed`, `Chassis Velocity X` |
| Distancia | `Distance` | `Distance`, `Lap Distance`, `LapDistance` |
| Freno / Acelerador | `Brake`, `Throttle` | `Brake Pos`, `Throttle Pos`, `Gas` |
| Volante | `SteerAngle` | `Steering Angle`, `Steering Wheel Angle` |
| G lateral / longitudinal | `LateralG`, `LongitudinalG` | `Lateral Acc`, `CG Accel Lateral`, `Longitudinal Acc`, `CG Accel Longitudinal` |
| Velocidad de guiñada | `YawRate` | `Chassis Yaw Rate`, `Yaw Rate` |
| Contador de vueltas | `SessionLapCount` | `Session Lap Count`, `Lap` |
| Posición | `CarCoordX/Y/Z` | `Car Coord X/Y/Z` |
| Temperatura de neumáticos | `TyreTemp{Core,Inner,Middle,Outer}{FL,FR,RL,RR}` | `Tire Temp Core FL`, `Tyre Temp (I) FL`, `LFtempCL` |
| Presión de neumáticos | `TyrePress{FL,FR,RL,RR}` | `Tire Pressure FL`, `LFpressure` |
| Recorrido de suspensión | `SuspTravel{FL,FR,RL,RR}` | `Suspension Travel FL`, `LFshockDefl` |
| Temperatura / reparto de freno | `BrakeTemp{FL,FR,RL,RR}`, `BrakeBias` | `Brake Temp FL`, `dcBrakeBias` |
| Temperatura de agua / aceite | `WaterTemp`, `OilTemp` | `Coolant Temp`, `Eng Oil Temp` |

La ausencia de canales opcionales no detiene el análisis: el panel afectado se muestra como no disponible.

**¿Y si no hay canal `Distance`?** La app lo sintetiza integrando la velocidad sobre un reloj válido (`LR/HR/MR Sample Clock`, `SessionTime`, `Time`, `Lap Time`...). Los relojes que solo alternan 0/1 no se usan. La respuesta lo marca con `distance_synthetic`. Es suficientemente preciso para el análisis de sesión y de stint; para comparar vuelta contra vuelta es más fiable un canal de distancia real.

---

## Notas de Calidad de Datos

- **Detección de vueltas:** las vueltas se encuentran a partir del canal contador de vueltas o, si no existe, de los reinicios de distancia. Los segmentos de menos de 30 s (vueltas parciales, restos de pit) se descartan.
- **Vueltas de pit y atípicas:** las vueltas con el canal `In Pit` activo, o con un tiempo fuera del 70-115 % de la mediana, se marcan y quedan fuera de regresiones y proyecciones.
- **Las ventanas de curva** nunca se solapan: cada una se recorta a mitad de camino entre ápices vecinos. El resumen informa el time delta dentro de curvas (`corners_time_delta_s`) y fuera de ellas (`outside_corners_delta_s`). Las curvas de dos vueltas se emparejan por la distancia del ápice.
- **"No medible" no es "cero":** si un delta de frenada o acelerador muestra `0.0` pero está marcado como no disponible (`braking_delta_available` / `throttle_delta_available` = false), no se pudo medir.
- **Canales constantes:** un canal que nunca cambia (por ejemplo, temperaturas de freno fijas en un valor) se informa como no disponible con un motivo, en lugar de generar consejos inventados.
- **Slip angle:** la convención de signo de la G lateral se detecta por su correlación con la velocidad de guiñada y se invierte si hace falta (Assetto Corsa la registra invertida).
- **Archivos inválidos:** un CSV vacío, o sin `Speed`, `Brake` y `Throttle`, se rechaza con un mensaje claro.

## Ejemplo de Resultado

Validado con un Porsche Cayman GT4 Clubsport en Imola (Assetto Corsa, CSV de MoTeC de unos 57 MB sin canal `Distance`):

- 21 vueltas detectadas (las vueltas 1 y 21 son de pit); la mejor es la vuelta 11 con 1:57.605; las vueltas de carrera están entre 117.6 y 122.4 s.
- Longitud de pista de unos 4862 m, velocidad máxima 243.9 km/h, 11 curvas encontradas por geometría.
- Consumo de combustible 1.758 L/vuelta; tendencia de ritmo -0.077 s/vuelta (el coche mejora a medida que consume combustible, por lo que es una mejora y no desgaste de neumáticos).
- El análisis completo terminó en unos 25 s.

## Limitaciones Conocidas

- La detección de curvas solo por velocidad encuentra 7 curvas en Imola frente a 11 por geometría (las chicanes se fusionan en una).
- La detección de bottoming es heurística: recorrido de suspensión igual o superior al 90 % del recorrido máximo observado en el archivo.
- Según el simulador y la exportación, algunos canales pueden faltar; los paneles te avisan cuando ocurre.

---

## Problemas Comunes

**No se detectan curvas:**
- El CSV no tiene datos de distancia utilizables, o los datos son muy ruidosos
- Probá con una vuelta completa (sin vueltas cortadas)

**Un panel dice "no disponible" (mirá el panel de salud):**
- El CSV no tiene los canales que ese módulo necesita (temperaturas de neumáticos, temperaturas de freno, recorrido de suspensión, `YawRate` y `LateralG` para el slip angle...)
- Los canales con valor constante también se informan como no disponibles

**La app dice que no encontró varias vueltas:**
- Un archivo de sesión necesita un canal contador de vueltas (`Session Lap Count`) o una distancia que se reinicie en cada vuelta
- El análisis de stint necesita al menos 3 vueltas

**Error 400 al subir:**
- El CSV está vacío o no contiene `Speed`, `Brake` y `Throttle` (el mensaje lista las columnas encontradas)

**Error 422 al comparar:**
- La vuelta elegida está fuera de rango, las dos vueltas son la misma, o no hay suficientes vueltas flying válidas para la selección automática

**Los gráficos no se sincronizan:**
- Mové el cursor lentamente; si el navegador tiene alto consumo de CPU, puede haber lag

**El análisis tarda mucho:**
- Los archivos de sesión de decenas de MB pueden tardar decenas de segundos o más en el backend; mantené la pestaña abierta

---

## Flujo de Trabajo Recomendado

```
1. Cargá el/los archivo(s) y esperá el análisis (en una sesión, elegí dos vueltas o usá Mejor vs Peor)
2. Mirá el TIME DELTA: ¿dónde se separan las líneas?
3. Hacé click en las curvas donde perdés más tiempo
4. Verificá el G-G: ¿estás usando todo el agarre disponible?
5. Revisá los neumáticos: ¿están en temperatura óptima?
6. Controlá el balance (slip angle): ¿el setup está equilibrado?
7. Mirá el estilo de pilotaje: ¿el coche obliga a corregir mucho?
8. Copiá el reporte de ingeniero para compartir con el equipo
```
