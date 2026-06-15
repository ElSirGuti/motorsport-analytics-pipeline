# Referencia Rápida — Interpretar Resultados

Cheat sheet para consulta rápida durante o después de una sesión.

---

## Neumáticos — Estados de Temperatura

| Estado | Rango | Acción |
|--------|-------|--------|
| Frío (azul) | < 65°C | Vuelta de calentamiento, no atacar |
| Subóptimo | 65–80°C | Suave, evitar curvas muy cargadas |
| **Óptimo** ✓ | **80–100°C** | **Condiciones ideales de agarre** |
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

Si alguno de estos canales no está en tu CSV de MoTeC, ese módulo se desactiva automáticamente y no aparece en la vista.

---

## Flujo de Sesión de Análisis

```
Cargá los CSV
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
Copiá el reporte → compartí con el equipo
```
