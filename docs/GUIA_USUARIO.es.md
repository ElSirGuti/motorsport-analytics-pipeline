# Guía de Usuario — Motorsport Analytics Pipeline

[Read in English](./USER_GUIDE.md)

Esta guía explica, en lenguaje sencillo, cómo usar la aplicación y qué significan los resultados de cada análisis. No necesitas saber matemáticas ni ingeniería para interpretarlos.

## Contenido

- [Primeros pasos](#primeros-pasos)
- [La interfaz de un vistazo](#la-interfaz-de-un-vistazo)
- [Funciones de sesión](#funciones-de-sesión): [calidad de datos](#panel-de-calidad-de-datos), [vuelta óptima](#vuelta-óptima-por-microsectores), [setups de Assetto Corsa](#setups-de-assetto-corsa), [biblioteca y comparar sesiones](#biblioteca-de-sesiones-y-comparar-sesiones), [informe PDF](#informe-pdf), [circuitos y nombres de curva](#circuitos-conocidos-y-nombres-de-curva), [tema](#tema), [velocidad](#análisis-más-rápido-subida-única)
- [Cómo leer cada análisis](#cómo-leer-cada-análisis)
- [Formatos soportados](#formatos-soportados) y [exportar la telemetría](#exportar-la-telemetría)
- [Notas de calidad de datos](#notas-de-calidad-de-datos), [limitaciones conocidas](#limitaciones-conocidas), [problemas comunes](#problemas-comunes), [flujo de trabajo recomendado](#flujo-de-trabajo-recomendado)

---

## Primeros Pasos

### ¿Qué hace esta herramienta?

Analiza telemetría y te dice **dónde ganás tiempo, dónde lo perdés y por qué**. Funciona de dos maneras:

- **Sesión completa (1 CSV):** la sesión se divide automáticamente en vueltas y obtenés una tabla de vueltas, análisis de stint (ritmo, combustible, neumáticos, ventana de pit) y recomendaciones de setup.
- **Comparación de vueltas (2 CSV, o 2 vueltas elegidas de una sesión):** una comparación lado a lado con diagnóstico curva a curva y los análisis avanzados (neumáticos, frenos, suspensión, estilo de pilotaje, balance).

### Archivos que necesitás

Archivos CSV exportados desde **MoTeC i2** (Assetto Corsa vía ACTI, iRacing) o, de forma **experimental**, archivos `.ibt` de iRacing y `.ld` de MoTeC directamente. Mirá [Formatos soportados](#formatos-soportados) y [Exportar la telemetría](#exportar-la-telemetría) para los pasos y los canales que la app entiende.

### Cómo empezar

1. Instalá e iniciá el backend y el frontend (ver el [README](../README.es.md#inicio-rápido)) y abrí `http://localhost:5173`.
2. En la barra superior elegí el idioma (ES/EN) y el modo: **Ingeniero** (todo) o **Piloto** (paneles técnicos ocultos).
3. Soltá tu(s) archivo(s) en el área de carga. Un archivo se trata como sesión completa; dos archivos se tratan como dos vueltas sueltas a comparar.
4. Presioná analizar. El archivo se sube una sola vez y una barra de progreso muestra las etapas (subida, sesión, stint, vuelta óptima); cada resultado aparece apenas termina su etapa, así que podés empezar a leer mientras se calcula el resto. Una sesión de ~57 MB mostró su primer resultado en unos 2 s y terminó en unos 3 s en el equipo del autor; con archivos más grandes mantené la pestaña abierta.
5. Al terminar, el área de carga se compacta en una barra de archivo con **Nuevo análisis**, **Guardar en biblioteca** y **Descargar informe**.

---

## La Interfaz de un Vistazo

La barra superior contiene la marca, el selector **Análisis / Biblioteca / Comparar sesiones**, el selector de idioma, el selector de tema y el interruptor Piloto/Ingeniero. Un **riel lateral** permite saltar entre secciones. El resto de la página es una sola vista larga: **mover el ratón sobre cualquier gráfico sincroniza la posición del cursor en todos los demás**.

### Sesión completa (1 CSV)

| Sección | Qué muestra |
|---------|-------------|
| **Resumen de sesión** | Panel de calidad de datos, tabla de vueltas, mejor vuelta, panel de salud, mapa de pista, vuelta óptima por microsectores |
| **Análisis de stint** | Evolución del tiempo por vuelta, degradación, estrategia de combustible, ventana de pit, proyección Monte Carlo, evolución de pista |
| **Setup y estrategia** | Setup usado (Assetto Corsa), análisis de curvas de toda la sesión, degradación de neumáticos, gestión térmica, trazada y recomendaciones de setup |

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

### Comparar dos archivos de una vuelta

Soltá **dos archivos con una vuelta cada uno** (por ejemplo una vuelta rápida y una lenta exportadas por separado) para compararlos directamente. La app ejecuta la comparación básica (`/api/compare-laps`) y la avanzada (`/api/telemetry/analyze`) y fusiona ambos resultados, incluidos los metadatos (piloto, coche, circuito) de cada archivo.

- El primer archivo es la vuelta de referencia y el segundo la vuelta que se compara contra ella (cargá primero la vuelta rápida).
- Si los dos archivos son de **coches distintos**, aparece un aviso (con los nombres de ambos coches) porque la comparación mezcla diferencias de coche y de piloto. Con el mismo coche no hay aviso.
- Ejemplo real, Red Bull Ring, Porsche Cayman GT4: vuelta rápida contra vuelta lenta = **+3,25 s**. La misma vuelta rápida contra una vuelta de un Maserati GT MC GT4 = **+1,44 s**, con el aviso de vehículos distintos.

---

## Funciones de sesión

### Panel de calidad de datos

Aparece primero, arriba de los resultados, y responde "¿qué le pasa a mis datos y cuánto me cuesta?". Da una **puntuación de 0 a 100** (Buena desde 75, Regular desde 50, Mala por debajo) formada por tres partes: canales (40 %), vueltas (20 %) y módulos de análisis (40 %). Al expandirlo ves:

- **Origen:** simulador, coche, circuito, frecuencia de muestreo, duración, muestras.
- **Vueltas:** detectadas, válidas, de pit, atípicas y segmentos parciales descartados, y cómo se segmentaron (contador de vueltas o reinicio de distancia).
- **Canales:** cada canal como OK, Falta, Constante, Sintetizado (por ejemplo `Distance` reconstruida desde la velocidad), Parcial, Huecos o Inactivo (modelo de desgaste de neumáticos apagado). "Mostrar solo problemas" oculta los sanos.
- **Módulos de análisis:** cada módulo (geometría, time delta, G-G, slip angle, suspensión, neumáticos, frenos, combustible/stint, térmico, setup, trazada, vuelta óptima) como OK, Degradado o No disponible, con el motivo concreto.
- **Cómo mejorar:** una lista priorizada (Alta, Media, Baja) de qué registrar o exportar distinto y qué análisis desbloquea cada arreglo.

### Vuelta óptima por microsectores

Está en el resumen de sesión. La app corta cada vuelta válida en microsectores y combina los mejores, y da dos números:

- **Óptima teórica:** la suma del mejor tiempo de cada microsector. Es una cota inferior optimista porque ignora que la velocidad de salida de un microsector es la de entrada del siguiente.
- **Óptima realista:** solo cambia de una vuelta a otra donde las velocidades coinciden (tolerancia de 3 km/h) y se queda al menos 75 m en la misma vuelta, de modo que la vuelta combinada es físicamente posible. Es la cifra que conviene usar como objetivo.

Ejemplo (Imola, Porsche Cayman GT4, 21 vueltas): mejor vuelta 1:57.605, óptima realista 1:54.107 (-3.498 s), óptima teórica 1:52.885 (-4.720 s).

Controles y consejos de lectura:

- **Tamaño del microsector** (10, 25, 50 o 100 m). La óptima teórica crece (se hace más rápida) al achicar el microsector, porque tiene más libertad para elegir lo mejor; compará tamaños y no persigas el número más pequeño.
- Vistas del gráfico: ganancia acumulada, ganancia por microsector y perfil de velocidad. El mapa de pista muestra dónde está el tiempo; la tabla de zonas lista dónde tu mejor vuelta pierde más, de qué vuelta tomarlo y qué mirar.
- Necesita al menos 3 vueltas utilizables (se excluyen las de pit, atípicas y parciales). Si el archivo no tenía canal `Distance`, se reconstruyó desde la velocidad, el alineado es menos preciso y el resultado es **solo orientativo**; el panel muestra un aviso.

### Setups de Assetto Corsa

La app puede enlazar el setup que usaste con las recomendaciones de setup, de modo que cada sugerencia muestre **Actual -> Sugerido** con tus valores reales.

1. Busca `<Documentos>\Assetto Corsa\setups\<coche>\<pista>\*.ini` (coche y pista salen de la cabecera de la telemetría). Si hay varios, elegís el que usaste.
2. Si no hay ninguno, puede ofrecerte tu último setup guardado (`<coche>\generic\last.ini`), pero **solo después de que confirmes** que fue el usado en esa sesión.
3. Si no, soltá el archivo `.ini` del setup en el área indicada (siempre disponible). Tu elección se recuerda para ese coche y pista.

Notas: el servidor solo puede leer la carpeta del juego si corre en el mismo equipo que el juego. **En Docker no puede**: subí el `.ini` manualmente, o montá la carpeta de solo lectura y definí `AC_SETUPS_DIR` (ver `docker-compose.override.example.yml` y la [guía de despliegue](./DEPLOYMENT.es.md)). Los valores se muestran en las unidades propias del juego (clics); una unidad real (presión de neumáticos en psi, reparto de frenada delantero y potencia de frenos en %, combustible en litros) se muestra solo donde es segura, y los rangos mín/máx solo cuando existe el `data/setup.ini` desempaquetado del coche. Los datos cifrados del coche nunca se abren. Si dos sugerencias empujan el mismo parámetro en sentidos opuestos, el panel te avisa: cambiá una cosa por vez. Por seguridad, solo se leen archivos `.ini`/`.sp` de hasta 256 KB y los nombres no pueden apuntar fuera de la carpeta de setups.

### Biblioteca de sesiones y comparar sesiones

- **Guardar en biblioteca** (barra de archivo) almacena los resultados calculados en la base de datos; marcá la opción para guardar automáticamente tras cada análisis. Guardar de nuevo el mismo archivo del mismo circuito actualiza la entrada existente.
- **Biblioteca** lista las sesiones guardadas con búsqueda, filtros de circuito/coche/fecha y paginación. Podés abrir una sesión **sin el archivo original** (la comparación vuelta a vuelta y todo lo que necesita la telemetría cruda requiere analizar el CSV otra vez), renombrarla o borrarla.
- **Comparar sesiones:** elegí la sesión A (referencia) y la B. Solo se ofrecen sesiones del mismo circuito y coche; se puede forzar la comparación de distintas y queda señalada. El resultado muestra diferencias de ritmo medio y mediano, consistencia, combustible por vuelta, tiempo perdido por curva y un gráfico de ritmo vuelta a vuelta. Los valores negativos significan que B es más rápida o menor.
- Límites: una sesión guardada está limitada a 5 MB. **Todavía no hay inicio de sesión**: cualquiera que llegue al servidor ve toda la biblioteca.

### Informe PDF

**Descargar informe** (barra de archivo) genera un PDF bilingüe (idioma de la interfaz) a partir de los resultados que ya tenés, sin recalcular: resumen ejecutivo, hallazgos clave, acciones recomendadas, calidad de datos y limitaciones, ritmo y vueltas, curvas en orden de pista, recomendaciones de setup, estrategia y neumáticos y, si comparaste dos vueltas, telemetría del coche y comparación de trazas. El archivo se llama `motorsport_<circuito>_<coche>_<fecha>.pdf`. Las comparaciones tienen además su propio botón de PDF y un reporte de texto para copiar.

### Circuitos conocidos y nombres de curva

Si el circuito de la cabecera del archivo es conocido, la interfaz muestra una insignia con su nombre y longitud, y las curvas se muestran como "Curva 4 - Tamburello". **Se reconocen 19 circuitos y 7 tienen nombres de curva**: Imola, Spa-Francorchamps, Silverstone GP, Le Mans y Mónaco (confianza alta) y Mugello y Brands Hatch GP (confianza media). Los otros 12 (Monza, Red Bull Ring, Nordschleife y más) solo se reconocen y sus curvas conservan el número. Si la longitud de la vuelta no coincide con el circuito (otro trazado o vuelta parcial) la insignia dice "confianza baja" y no se muestran nombres. Los nombres nunca se adivinan: una tabla de curvas se publica solo cuando se verificó con telemetría real.

### Trompos y salidas de pista

Tras analizar una sesión, el panel **Trompos y salidas de pista** (en la sección de stint) lista cada trompo, derrape salvado y salida de pista con su vuelta, curva y velocidad. Ábrelo para ver la **causa más probable** con los números que la respaldan (por ejemplo "acelerador 95 % frente a 60 % en tus otras vueltas en este punto"), cómo evitarlo, otros factores que contribuyen y una gráfica de pedales, volante, velocidad y deslizamiento alrededor del momento. Una curva que aparece varias veces se marca como repetida. Las causas son inferencias a partir de tus inputs, no certezas; el panel también indica qué señales ofrece tu registro (velocidad del chasis y suciedad de neumáticos en los registros ACTI de Assetto Corsa; iRacing ofrece un canal de superficie de pista). El viento solo se evalúa si el registro lo graba. Detalle: [docs/18_incidents.es.md](./18_incidents.es.md).

### Tema

Usá el selector de tema de la barra superior: **Sistema** (sigue tu sistema operativo), **Claro** u **Oscuro**. La elección se recuerda en tu navegador. Los colores de texto y gráficos se verificaron por contraste en ambos temas (64 pares de colores por tema, sin fallos).

### Análisis más rápido (subida única)

El archivo viaja una sola vez al servidor y se mantiene en memoria para los pasos siguientes, así que sesión, stint y vuelta óptima no lo vuelven a procesar. Si el servidor se reinició o la copia caducó (24 horas por defecto), la app vuelve a subir el archivo y reintenta sola; no tenés que hacer nada.

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
| **Microsector** | Un tramo corto de la vuelta (10-100 m) con el que se arma la vuelta óptima |
| **Vuelta óptima** | Una vuelta armada con los mejores microsectores de tus vueltas (teórica o realista) |
| **G lateral / longitudinal** | Fuerza sentida en curvas (lateral) o bajo freno/aceleración (longitudinal) |

---

## Formatos soportados

| Formato | Origen | Estado |
|---------|--------|--------|
| `.csv` | Exportación de MoTeC i2 (Assetto Corsa/ACTI, iRacing) | Estable |
| `.ibt` | Telemetría nativa de iRacing | **Experimental** |
| `.ld`  | Log nativo de MoTeC i2 (ACTI, exportación "MoTeC" de iRacing) | **Experimental** |

> **Estado experimental.** Los lectores de `.ibt` y `.ld` están implementados a partir de los formatos binarios documentados públicamente. Se verificaron con archivos sintéticos (tests de ida y vuelta) y con archivos reales de la máquina del autor (53 archivos: 9 sesiones `.ibt` de iRacing con un BMW M2 en Oran Park y un Ford Mustang GT4 en Lime Rock, los 9 `.ld` de MoTeC equivalentes y 35 logs `.ld` de Assetto Corsa/ACTI). Es una muestra pequeña: otros coches, simuladores o loggers MoTeC pueden tener canales que el lector no conoce. La interfaz marca estos archivos con una insignia **Experimental**. Si un resultado parece incorrecto, compáralo con el CSV exportado de la misma sesión.

**iRacing `.ibt`:** iRacing los escribe automáticamente en `Documents\iRacing\telemetry` (un archivo por sesión, con nombre `<coche>_<pista> <fecha> <hora>.ibt`) cuando el registro de telemetría está activo (Ctrl+L lo alterna en el simulador). Súbelo tal cual. Piloto, coche y pista se leen del propio archivo. Las unidades se convierten (m/s a km/h, pedales 0-1 a %, rad a grados, m/s2 a g, kPa a bar, m a mm); `Distance` se reconstruye con la distancia de vuelta del simulador.

**MoTeC `.ld`:** abre la carpeta donde tu logger o ACTI guarda los logs (en ACTI, `Documents\acti\telem\<pista>_&_<coche>\`; el `.ldx` contiguo es opcional y se ignora) y sube el `.ld`. Los canales con distinta frecuencia se remuestrean a la más alta. Si el log no trae `Distance`, se sintetiza desde la velocidad, igual que con CSV.

Límites conocidos: se rechazan los archivos mayores que el límite de subida del servidor (`MAX_UPLOAD_MB`, 2048 por defecto); las sesiones de más de 2 millones de muestras tras remuestrear (`NATIVE_MAX_ROWS`) se rechazan con un mensaje; un `.ibt` truncado carga los registros completos y un `.ld` truncado se rechaza. El signo de la G lateral sigue la convención de cada origen y no se normaliza.

---

## Exportar la telemetría

Además de los archivos nativos `.ibt` / `.ld` de arriba, la app lee **archivos CSV**. Exportalos desde el programa que uses:

**Assetto Corsa (ACTI + MoTeC i2)**
1. Grabá la sesión con la app de telemetría ACTI (mirá la documentación de ACTI para instalarla).
2. Abrí el log en **MoTeC i2** y usá **File -> Export -> Export to Spreadsheet (CSV)**.
3. Para una **vuelta suelta**, seleccioná el rango de tiempo de esa vuelta; para una **sesión completa**, seleccioná todo el rango (de la vuelta 1 a la última). Exportá todos los canales, idealmente a 60 Hz o más.
4. El bloque de cabecera del CSV de MoTeC (Driver, Vehicle, Venue) se lee automáticamente y se usa para las etiquetas.

**iRacing**
1. iRacing graba archivos `.ibt`; podés subirlos directamente (experimental, ver arriba) o convertirlos a CSV con MoTeC i2 o una herramienta de terceros.
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
- **Proyecciones conservadoras:** con menos de 5 vueltas válidas (o una tendencia muy incierta) la proyección de stint vuelve al ritmo reciente y se marca con baja confianza y el motivo; con menos de 8 vueltas la confianza es siempre baja. Si el desgaste de neumáticos no parece activado en el simulador, la degradación se muestra como no disponible (desgaste inactivo) en lugar de inventar una tendencia.

## Ejemplo de Resultado

Validado con un Porsche Cayman GT4 Clubsport en Imola (Assetto Corsa, CSV de MoTeC de unos 57 MB sin canal `Distance`):

- 21 vueltas detectadas (las vueltas 1 y 21 son de pit); la mejor es la vuelta 11 con 1:57.605; las vueltas de carrera están entre 117.6 y 122.4 s.
- Longitud de pista de unos 4862 m, velocidad máxima 243.9 km/h, 11 curvas encontradas por geometría.
- Consumo de combustible 1.758 L/vuelta; tendencia de ritmo -0.077 s/vuelta (el coche mejora a medida que consume combustible, por lo que es una mejora y no desgaste de neumáticos).
- La vuelta óptima fue 1:54.107 realista (-3.498 s) y 1:52.885 teórica (-4.720 s), orientativa porque `Distance` se sintetizó.
- El primer resultado apareció en unos 2,1 s y el análisis completo terminó en unos 2,9 s en el equipo del autor (antes tardaba unos 15 s y 21 s).

## Limitaciones Conocidas

- La detección de curvas solo por velocidad encuentra 7 curvas en Imola frente a 11 por geometría (las chicanes se fusionan en una).
- La detección de bottoming es heurística: recorrido de suspensión igual o superior al 90 % del recorrido máximo observado en el archivo.
- Según el simulador y la exportación, algunos canales pueden faltar; los paneles te avisan cuando ocurre.
- `.ibt` y `.ld` son experimentales (probados con 53 archivos de un solo autor); CSV es el formato estable.
- La óptima teórica crece al achicar el microsector; con `Distance` sintetizada la vuelta óptima es solo orientativa.
- Los nombres de curva existen para 7 de los 19 circuitos reconocidos (Imola, Spa, Silverstone GP, Le Mans, Mónaco, Mugello, Brands Hatch GP).
- Las unidades de setup se muestran solo donde son seguras y faltan rangos en la mayoría de los coches (sus archivos de datos están cifrados).
- No hay autenticación: no expongas la app a internet tal cual.

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

**La app vuelve a subir el archivo o dice que expiró (HTTP 410):**
- El servidor ya no tenía tu copia subida (reinicio, caducidad de 24 horas u otra réplica sin volumen compartido). La app reintenta sola; si sigue fallando, presioná **Nuevo análisis** y cargá el archivo de nuevo.

**Un aviso dice que los dos archivos son de vehículos distintos:**
- Cargaste vueltas de coches diferentes en el modo de dos archivos. Los números se calculan igual, pero la diferencia incluye la del coche; cargá dos vueltas del mismo coche para comparar solo al piloto.

**Error 413 (archivo demasiado grande):**
- El archivo supera el límite del servidor (`MAX_UPLOAD_MB`, 2048 MB por archivo por defecto). Una sesión guardada en la biblioteca está limitada a 5 MB.

**El panel de setup dice que el servidor no puede leer tu carpeta de Assetto Corsa:**
- Es normal en Docker o cuando el servidor está en otro equipo. Subí el `.ini` del setup que usaste, o montá la carpeta de solo lectura y definí `AC_SETUPS_DIR`.

**Un archivo `.ibt` o `.ld` se ve mal:**
- Estos formatos son experimentales. Compará con la exportación CSV de la misma sesión y reportá el caso.

**La vuelta óptima dice que es orientativa o no disponible:**
- Necesita al menos 3 vueltas válidas y un `Distance` confiable; sin él la distancia se reconstruye desde la velocidad. Mirá el panel de calidad de datos.

**La app corre en Docker o Kubernetes y algo no arranca o no analiza:**
- Mirá la tabla de solución de problemas de [Despliegue](./DEPLOYMENT.es.md#solución-de-problemas) (`POSTGRES_PASSWORD`, primer build lento, versión de pandas, carpeta de la base del historial, `curl.exe` en PowerShell).

**El análisis tarda mucho:**
- Los archivos de sesión de decenas de MB pueden tardar decenas de segundos o más en el backend; mantené la pestaña abierta

---

## Flujo de Trabajo Recomendado

```
1. Cargá el/los archivo(s) y leé el panel de calidad de datos (en una sesión, elegí dos vueltas o usá Mejor vs Peor)
2. Mirá el TIME DELTA: ¿dónde se separan las líneas?
3. Hacé click en las curvas donde perdés más tiempo
4. Verificá el G-G: ¿estás usando todo el agarre disponible?
5. Revisá los neumáticos: ¿están en temperatura óptima?
6. Controlá el balance (slip angle): ¿el setup está equilibrado?
7. Mirá el estilo de pilotaje: ¿el coche obliga a corregir mucho?
8. Mirá la vuelta óptima y sus zonas para ver dónde tu mejor vuelta todavía pierde tiempo
9. Enlazá tu setup, guardá la sesión en la biblioteca y descargá el informe para compartir con el equipo
```
