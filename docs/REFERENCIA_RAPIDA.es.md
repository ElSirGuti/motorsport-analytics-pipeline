# Referencia Rápida — Interpretar Resultados

[Read in English](./QUICK_REFERENCE.md)

Cheat sheet para consulta rápida durante o después de una sesión. Explicaciones completas: [Guía de Usuario](./GUIA_USUARIO.es.md).

---

## Neumáticos — Estados de Temperatura

| Estado | Rango | Acción |
|--------|-------|--------|
| Frío (azul) | < 65°C | Vuelta de calentamiento, no atacar |
| Subóptimo | 65–80°C | Suave, evitar curvas muy cargadas |
| **Óptimo** | **80–100°C** | **Condiciones ideales de agarre** |
| Caliente | 100–115°C | Reducir carga o suavizar entradas |
| Sobrecalentado | > 115°C | Peligro: agarre muy reducido |

**Gradiente ΔT > 20°C** → Estrés interno. Posible problema de presión o compuesto.

### Diagnóstico por patrón de temperatura

| Patrón | Causa más probable | Setup |
|--------|--------------------|-------|
| Interior >> Exterior | Presión alta | Bajar presión |
| Exterior >> Interior | Presión baja / mucho camber | Subir presión o reducir camber |
| Delanteros sobrecalentados | Subviraje / frenadas duras | Más agarre delantero o ajuste de frenos |
| Traseros sobrecalentados | Sobreviraje / potencia temprana | Menos potencia en salida o diff más cerrado |

---

## Brake Fade — Eficiencia de Frenado

| Puntuación | Estado | Acción |
|------------|--------|--------|
| > 90 | Normal | Sin acción necesaria |
| 75–90 | Leve | Monitorear en stints largos |
| 60–75 | Moderado | Revisar ductos de aire o compuesto |
| < 60 | Severo | Alto riesgo. Pit stop o ajuste inmediato |

**Fade en zona específica siempre** → Problema localizado (ducto bloqueado, frenada muy larga sin enfriamiento).  
**Fade progresivo a lo largo del stint** → Normal en carrera larga con compuesto suave.

---

## Inputs del Piloto — Nerviosismo

| NI (%) | Perfil | Diagnóstico |
|--------|--------|-------------|
| 0–20% | Suave / limpio | Entradas ideales, mínimo desgaste |
| 20–40% | Normal | Actividad natural en curvas difíciles |
| 40–60% | Reactivo | El coche puede estar desequilibrado |
| 60–80% | Muy nervioso | Setup problemático o pista difícil |
| 80–100% | Luchando | Coche incontrolable — revisar balance |

**FFT: potencia en banda alta (>2 Hz) elevada** → El piloto corrige errores en vez de prevenirlos.  
**Solapamiento freno-gas > 15%** → Coordinación de pedales a mejorar, o técnica deliberada (Trail braking).

---

## Suspensión

### Bottoming (fondo de carrera)

| Severidad | Recorrido | Acción |
|-----------|-----------|--------|
| Normal | < 90% del máximo | Sin cambios |
| Alerta | 90–95% | Revisar ride height |
| Crítico | > 95% | Subir coche o endurecer resorte / compresión |

**Pitch exagerado en frenada** → Muelles delanteros blandos o poco amortiguamiento de compresión.  
**Roll excesivo en curvas** → Barras estabilizadoras blandas o muelles blandos.

### Signos de Roll/Pitch

| Valor positivo | Valor negativo |
|----------------|----------------|
| Roll (+): carga a derecha | Roll (−): carga a izquierda |
| Pitch (+): cola baja (aceleración) | Pitch (−): morro bajo (frenada) |

---

## Ángulo de Deslizamiento — Balance de Coche

### Sideslip β

| β | Comportamiento |
|---|----------------|
| 0–2° | Neutro, coche sigue la dirección |
| 2–5° | Deslizamiento controlado (normal en límite) |
| 5–8° | Trabajo fuera del punto óptimo |
| > 8° | Límite del control — peligro de salida |

### Balance αF − αR

| Valor | Significado | Setup a revisar |
|-------|-------------|-----------------|
| > +2° | Subviraje (ruedas delanteras deslizan) | Bajar presión delantera, reducir barra delantera, más camber |
| −2° a +2° | Neutro — ideal | Mantener setup |
| < −2° | Sobreviraje (cola sale) | Subir presión trasera, abrir diff, suavizar gas en salida |

**% US / Neutral / OS durante la vuelta:**
- Objetivo: >60% tiempo neutro
- >30% subviraje → setup muy subviraje, el coche frena la vuelta
- >20% sobreviraje → riesgo de excursiones o salidas de pista

---

## Time Delta — Dónde Ganás / Perdés

| La línea de delta... | Significa... |
|----------------------|--------------|
| Sube → | A es más lento que B en esa zona |
| Baja → | A es más rápido que B en esa zona |
| Plana | Sin diferencia |
| Sube de golpe | Punto problemático puntual (frenada, apex) |
| Sube gradual | Velocidad de paso inferior en toda la curva |

---

## G-G Diagram — Aprovechamiento de Agarre

| G-Efficiency | Interpretación |
|--------------|----------------|
| > 80% | Excelente uso del agarre disponible |
| 60–80% | Margen de mejora, probablemente en frenadas o salidas |
| < 60% | El piloto no lleva el coche al límite |

**Las 4 esquinas del diagrama:**
- Arriba-derecha: aceleración + giro a derecha — ¿hay puntos? Si no, no se combina gas y curva
- Abajo-izquierda: frenada + giro a izquierda — trail braking

---

## Vuelta Óptima por Microsectores

| Cifra | Significado | Usala como |
|-------|-------------|-----------|
| **Mejor vuelta** | Tu vuelta válida más rápida | Referencia |
| **Óptima realista** | Mejores microsectores unidos solo donde las velocidades coinciden (3 km/h) y con al menos 75 m en la misma vuelta | Objetivo |
| **Óptima teórica** | Suma del mejor tiempo de cada microsector (ignora la continuidad de velocidad) | Cota inferior optimista |

- Microsector de 10 / 25 / 50 / 100 m: la cifra teórica se hace más rápida al achicar el microsector. Compará, no la persigas.
- Necesita 3 o más vueltas válidas. Con `Distance` sintetizada el resultado es solo orientativo (se muestra un aviso).
- Tabla de zonas: dónde pierde más la mejor vuelta, de qué vuelta tomarlo y qué mirar.
- Ejemplo Imola: mejor 1:57.605, realista 1:54.107 (-3.498 s), teórica 1:52.885 (-4.720 s).

---

## Puntuación de Calidad de Datos

| Puntuación | Nivel | Qué hacer |
|------------|-------|-----------|
| 75-100 | Buena | Confiá en los resultados |
| 50-74 | Regular | Leé "Cómo mejorar"; algunos paneles están degradados |
| 0-49 | Mala | Arreglá primero la exportación (canales ausentes o constantes, pocas vueltas) |

Pesos: canales 40 %, vueltas 20 %, módulos de análisis 40 %. Estados de canal: OK, Falta, Constante, Sintetizado, Parcial, Huecos, Inactivo. Estados de módulo: OK, Degradado, No disponible.

---

## Enlace con el Setup (Assetto Corsa)

| Paso | Dónde busca |
|------|-------------|
| 1 | `<Documentos>\Assetto Corsa\setups\<coche>\<pista>\*.ini` (o la carpeta de `AC_SETUPS_DIR`) |
| 2 | `<coche>\generic\last.ini`, solo después de que confirmes que se usó |
| 3 | Subida manual del `.ini` (siempre funciona; la única opción en Docker salvo que montes la carpeta de solo lectura) |

Las recomendaciones muestran entonces **Actual -> Sugerido**. Las unidades aparecen solo donde son seguras (psi, % de reparto y potencia de frenos, litros); si no, clics crudos del juego. Sugerencias en conflicto: cambiá una cosa por vez.

---

## Formatos, Límites y Códigos de Estado

| Elemento | Valor |
|----------|-------|
| CSV (MoTeC / ACTI, iRacing) | Estable |
| `.ibt` iRacing, `.ld` MoTeC | **Experimental** (validado con 53 archivos de un solo autor) |
| Canales mínimos | Speed, Brake, Throttle |
| Límite de subida | `MAX_UPLOAD_MB` por archivo (2048 por defecto), HTTP 413 si lo supera |
| Sesión guardada en la biblioteca | 5 MB máximo (HTTP 413) |
| Archivo de setup | `.ini`/`.sp`, 256 KB máximo |
| HTTP 410 | El servidor perdió la copia subida: la app sube de nuevo y reintenta |
| Stint / vuelta óptima | 3 o más vueltas válidas |
| Confianza de la proyección | Siempre baja con menos de 8 vueltas válidas; vuelve al ritmo reciente con menos de 5 |
| Circuitos | 19 reconocidos; 7 con nombres de curva (Imola, Spa, Silverstone GP, Le Mans, Mónaco = confianza alta; Mugello, Brands Hatch GP = media) |
| Comparar dos archivos | 2 archivos con una vuelta cada uno: el primero es la referencia y el segundo el comparado; avisa si los coches son distintos |
| Tests | `python -m pytest tests -q`: 448 recogidos, 425 se ejecutan, 23 e2e omitidos sin `E2E=1` |

---

## Modo Comparar con Dos Archivos

Soltá dos archivos con una vuelta cada uno (primero la vuelta de referencia). La app llama a `/api/compare-laps` y `/api/telemetry/analyze` y fusiona ambos resultados y sus metadatos.

| Caso (Red Bull Ring) | Resultado |
|----------------------|-----------|
| Porsche Cayman GT4 vuelta rápida vs vuelta lenta (mismo coche) | +3,25 s, sin aviso de vehículos |
| La misma vuelta rápida vs vuelta de un Maserati GT MC GT4 | +1,44 s, **aviso de vehículos distintos** (la diferencia incluye la del coche) |

---

## Contenedores: Arreglos Rápidos

| Síntoma | Solución |
|---------|----------|
| `required variable POSTGRES_PASSWORD is missing a value` | `cp .env.example .env` y pon la contraseña |
| Docker Desktop: "Virtualization support not detected" | Activa VT-x/SVM en BIOS/UEFI, `wsl --install`, reinicia |
| Primer build del backend de más de 10 minutos / pip `read operation timed out` | Normal en el primer build; repítelo |
| kind: `migrate` falla 1-2 veces (`failed to resolve host postgres`) | Normal; mira `kubectl -n motorsport get pods` |
| `curl` de PowerShell se comporta raro | Usa `curl.exe` |

Lista completa: [Despliegue](./DEPLOYMENT.es.md#solución-de-problemas).

---

## Guía de Diagnóstico Rápido

### "Soy lento en frenadas"
1. Mirá el Time Delta: ¿la pérdida empieza antes o después del punto de freno?
2. Si antes → llegás rápido pero el punto de freno es correcto, el problema es la velocidad de entrada a la recta anterior
3. Si justo en el freno → probá frenar más tarde
4. Verificá si hay Brake Fade activo en esas curvas

### "El coche no gira"
1. Revisá el balance (slip angle): ¿% subviraje alto?
2. Mirá los neumáticos delanteros: ¿sobrecalentados?
3. Revisá el G-G: ¿estás usando freno y curva combinados (trail braking)?

### "El coche se mueve mucho atrás"
1. Verificá el sideslip β: ¿picos > 5° en salidas?
2. Revisá el índice de nerviosismo: correcciones al volante en salida de curva
3. Mirá la temperatura de traseros: ¿sobrecalentados?

### "Los neumáticos no calientan"
1. Confirmá que el CSV tiene canales de temperatura de neumáticos
2. Verifica que no estés en vuelta de instalación (outlap)
3. Si sigue frío → revisar compuesto, presión o falta de carga aerodinámica

### "Los resultados avanzados no aparecen"
Algunos módulos requieren canales específicos:

| Módulo | Canales necesarios |
|--------|-------------------|
| Temperatura neumáticos | TyreTempInner/Middle/Outer/CoreFL/FR/RL/RR |
| Brake Fade | LongitudinalG + Brake |
| Inputs piloto | SteerAngle |
| Suspensión | SuspTravelFL/FR/RL/RR |
| Slip angle | LateralG + YawRate + SteerAngle |

Si alguno de estos canales no está en tu CSV de MoTeC, ese módulo se informa como no disponible (mirá el panel de salud) en lugar de mostrar resultados inventados. Un canal que nunca cambia (por ejemplo, temperaturas de freno fijas en un valor) también se informa como no disponible. El bottoming se marca al 90 % o más del recorrido máximo observado. Canales mínimos para cualquier análisis: Speed, Brake, Throttle; si falta Distance se sintetiza a partir de la velocidad (marcado como `distance_synthetic`).

---

## Flujo de Sesión de Análisis

```
Cargá el/los archivo(s): 1 archivo = sesión, 2 archivos = comparación de vueltas (una vuelta cada uno)
    ↓
Leé primero la puntuación de calidad de datos
    ↓
¿Cuánto tiempo pierdo y dónde? → Time Delta + Curvas
    ↓
¿Por qué lo pierdo? → G-G + Slip Angle (subviraje/sobreviraje)
    ↓
¿El coche está en temperatura? → Neumáticos
    ↓
¿Los frenos funcionan bien? → Brake Fade
    ↓
¿El estilo de pilotaje es el problema? → Inputs del Piloto
    ↓
¿El setup mecánico es el problema? → Suspensión + Slip Angle
    ↓
Vuelta óptima → ¿qué zonas todavía cuestan tiempo?
    ↓
Enlazá el setup, guardá en la biblioteca, descargá el informe PDF → compartí con el equipo
```
