# Guía de Usuario — Motorsport Analytics Pipeline

Esta guía explica, en lenguaje sencillo, cómo usar la aplicación y qué significan los resultados de cada análisis. No necesitas saber matemáticas ni ingeniería para interpretarlos.

---

## Primeros Pasos

### ¿Qué hace esta herramienta?

Compara dos vueltas de telemetría lado a lado y te dice **dónde ganás tiempo, dónde lo perdés y por qué**. También analiza el estado de los neumáticos, los frenos, la suspensión, y el estilo de conducción, todo de forma automática.

### Archivos que necesitás

Archivos CSV exportados desde **MoTeC i2** o cualquier simulador compatible (Assetto Corsa, etc.). Cada archivo representa una vuelta o una sesión.

### Cómo empezar

1. Abrí la app en tu navegador (`http://localhost:5173`)
2. Arrastrá o seleccioná **dos archivos CSV** en el panel de carga
3. Hacé clic en **"Comparar Vueltas"**
4. Esperá unos segundos — el análisis completo se carga automáticamente

> Si el archivo tiene varias vueltas, el sistema toma las dos más rápidas válidas.

---

## La Interfaz de un Vistazo

La página es una sola vista larga con secciones. Podés hacer scroll o usar el cursor cruzado interactivo: **mover el ratón sobre cualquier gráfico sincroniza la posición en todos los demás**.

| Sección | Qué muestra |
|---------|-------------|
| **Encabezado** | Nombre de piloto, vehículo, circuito, tiempo de cada vuelta |
| **Velocidad y Delta** | Curva de velocidad + diferencia de tiempo acumulada |
| **Freno y Acelerador** | Superposición de las dos vueltas en frenado y gas |
| **Mapa de Pista** | Trazada del circuito con la posición actual |
| **Diagrama G-G** | Agarre total usado por vuelta |
| **Análisis de Curvas** | Tabla con tiempos, frenado y aceleración por curva |
| **Neumáticos** | Temperatura e interpretación de los 4 neumáticos |
| **Frenos** | Eficiencia y detección de fade térmico |
| **Inputs del Piloto** | Estilo de conducción al volante (suave vs nervioso) |
| **Suspensión** | Roll, pitch y eventos de fondo |
| **Ángulo de Deslizamiento** | Balance del coche (subviraje vs sobreviraje) |
| **Reporte de Ingeniero** | Texto exportable con el resumen completo |

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

| Ícono / Color | Significado |
|---------------|-------------|
| Verde ✓ | Sin problema detectado |
| Amarillo ⚠ | Diferencia leve (0.05–0.15s) |
| Rojo ✗ | Diferencia importante (>0.15s) |

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

Un evento de fondo ocurre cuando el amortiguador llega a su límite de recorrido. Esto es problemático porque:
- El coche se pone rígido de golpe (pérdida de agarre)
- La aerodinámica se desestabiliza
- Puede dañar la carrocería

| Severidad | Descripción |
|-----------|-------------|
| < 95% | Cerca del límite pero controlado |
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

## Problemas Comunes

**No se detectan curvas:**
- El CSV no tiene datos de distancia o los datos son ruidosos
- Probá con una vuelta completa (sin laps cortadas)

**Los neumáticos siempre aparecen en "frío":**
- El CSV no tiene los canales de temperatura de neumáticos (TyreTempInner, TyreTempMiddle, etc.)
- Verificá que el set de canales de MoTeC incluye temperatura de ruedas

**El análisis de slip angle no aparece:**
- El CSV necesita canales de `YawRate` y `LateralG`
- Si el simulador no exporta YawRate, este módulo se desactiva automáticamente

**Los gráficos no se sincronizan:**
- Mové el cursor lentamente — la sincronización ocurre cada frame a 60fps
- Si el navegador tiene alto consumo de CPU, puede haber lag

**El análisis tarda mucho:**
- CSVs con más de 50.000 filas pueden tardar 10–20 segundos en el backend
- Normal para vueltas largas (>5 minutos) con alta frecuencia de muestreo

---

## Flujo de Trabajo Recomendado

```
1. Cargá las dos vueltas → esperá el análisis
2. Mirá el TIME DELTA: ¿dónde se separan las líneas?
3. Hacé click en las curvas donde perdés más tiempo
4. Verificá el G-G: ¿estás usando todo el agarre disponible?
5. Revisá los neumáticos: ¿están en temperatura óptima?
6. Controlá el balance (slip angle): ¿el setup está equilibrado?
7. Mirá el estilo de pilotaje: ¿el coche obliga a corregir mucho?
8. Copiá el reporte de ingeniero para compartir con el equipo
```
