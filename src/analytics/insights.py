"""
Módulo de Extracción de Insights Automatizados.

Este módulo actúa como el "Ingeniero de Pista de IA". Analiza la telemetría
alineada en ventanas alrededor de cada curva (Apex) para identificar errores
críticos de conducción mediante reglas heurísticas de competición.

Métricas doradas extraídas:
  1. Braking Point Delta: Diferencia en metros del punto inicial de frenada.
  2. V-Min Delta: Diferencia en la velocidad mínima de paso por curva.
  3. Throttle Application Delta: Diferencia en metros para volver al 100% de gas.
"""

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def analizar_errores_por_curva(df_alineado: pd.DataFrame, df_apexes: pd.DataFrame) -> list[dict]:
    """
    Analiza la telemetría en ventanas alrededor de cada Apex para generar
    diagnósticos técnicos automatizados sobre el rendimiento en cada curva.

    Args:
        df_alineado: DataFrame con telemetría de ambas vueltas alineada por distancia.
                     Requiere: Distance, Speed_Fast, Speed_Slow, Delta_Time,
                               Brake_Fast, Brake_Slow, Throttle_Fast, Throttle_Slow.
        df_apexes: DataFrame con las ubicaciones de los Apex (Distance, Curvature).

    Returns:
        Lista de diccionarios con los insights y métricas de cada curva.
    """
    reporte_insights = []
    
    if df_apexes.empty or df_alineado.empty:
        return reporte_insights

    logger.info("🧠 Generando insights automatizados por curva...")

    # Asegurarnos de que las columnas de pedales existan (pueden faltar en algunos CSVs)
    has_brake = 'Brake_Fast' in df_alineado.columns and 'Brake_Slow' in df_alineado.columns
    has_throttle = 'Throttle_Fast' in df_alineado.columns and 'Throttle_Slow' in df_alineado.columns

    for idx, (_, apex) in enumerate(df_apexes.iterrows()):
        curva_num = idx + 1
        metro_apex = apex['Distance']
        
        # Crear una ventana de análisis: 100m antes del apex y 50m después
        ventana = df_alineado[(df_alineado['Distance'] >= metro_apex - 100) & 
                              (df_alineado['Distance'] <= metro_apex + 50)]
        
        if len(ventana) < 10:
            continue
            
        # 1. Delta de tiempo específico perdido SOLO en esta curva
        delta_entrada = ventana['Delta_Time'].iloc[-1] - ventana['Delta_Time'].iloc[0]
        
        # 2. Velocidad mínima en vértice (V-Min Delta)
        v_min_fast = ventana['Speed_Fast'].min()
        v_min_slow = ventana['Speed_Slow'].min()
        v_delta = v_min_fast - v_min_slow  # Positivo si Fast fue más rápido en curva
        
        # 3. Punto de Frenada (Braking Point Delta)
        # Distancia al apex donde se pisa el freno (> 5%)
        brake_delta_m = 0.0
        dist_frenada_fast = None
        dist_frenada_slow = None
        
        if has_brake:
            # Ventana de entrada (antes del apex)
            entrada = ventana[ventana['Distance'] <= metro_apex]
            
            idx_brake_fast = entrada[entrada['Brake_Fast'] > 5.0].index
            if not idx_brake_fast.empty:
                dist_frenada_fast = metro_apex - df_alineado.loc[idx_brake_fast[0], 'Distance']
                
            idx_brake_slow = entrada[entrada['Brake_Slow'] > 5.0].index
            if not idx_brake_slow.empty:
                dist_frenada_slow = metro_apex - df_alineado.loc[idx_brake_slow[0], 'Distance']
                
            if dist_frenada_fast is not None and dist_frenada_slow is not None:
                # Positivo si Slow frena ANTES (más lejos del apex), Negativo si frena DESPUÉS
                brake_delta_m = dist_frenada_slow - dist_frenada_fast
                
        # 4. Fase de Retorno al Gas (Throttle Application Delta)
        # Metros después del apex para llegar al gas a fondo (> 95%)
        throttle_delta_m = 0.0
        dist_gas_fast = None
        dist_gas_slow = None
        
        if has_throttle:
            # Ventana de salida (desde un poco antes del apex hacia adelante)
            salida = ventana[ventana['Distance'] >= metro_apex - 20]
            
            idx_gas_fast = salida[salida['Throttle_Fast'] > 95.0].index
            if not idx_gas_fast.empty:
                dist_gas_fast = df_alineado.loc[idx_gas_fast[0], 'Distance'] - metro_apex
                
            idx_gas_slow = salida[salida['Throttle_Slow'] > 95.0].index
            if not idx_gas_slow.empty:
                dist_gas_slow = df_alineado.loc[idx_gas_slow[0], 'Distance'] - metro_apex
                
            if dist_gas_fast is not None and dist_gas_slow is not None:
                # Positivo si Slow da gas DESPUÉS (más lejos del apex), Negativo si da gas ANTES
                throttle_delta_m = dist_gas_slow - dist_gas_fast

        # 5. Lógica predictiva / Heurística de coaching
        diagnostico = ""
        is_loss = delta_entrada > 0.05
        
        if is_loss:
            if v_delta > 3.0 and brake_delta_m > 10.0:
                diagnostico = f"Frenada anticipada. Frenaste {brake_delta_m:.1f}m antes que la referencia, resultando en una velocidad mínima de paso {v_delta:.1f} km/h más lenta."
            elif brake_delta_m < -5.0 and throttle_delta_m > 10.0:
                diagnostico = f"Entrada pasada (Overdriving). Frenaste tarde ({abs(brake_delta_m):.1f}m después), perdiste el vértice y retrasaste la aceleración {throttle_delta_m:.1f}m."
            elif v_delta > 5.0:
                diagnostico = f"Paso por curva excesivamente lento. Perdiste {v_delta:.1f} km/h en el vértice respecto a la vuelta óptima."
            elif throttle_delta_m > 15.0:
                diagnostico = f"Salida comprometida. Te tomó {throttle_delta_m:.1f}m adicionales volver a dar gas a fondo."
            else:
                diagnostico = f"Pérdida general en el sector de {delta_entrada:.3f}s. Revisa la trazada."
        elif delta_entrada < -0.05:
             diagnostico = f"¡Excelente ejecución! Ganaste {abs(delta_entrada):.3f}s en esta sección."
        else:
            diagnostico = "Ejecución óptima, muy similar a la referencia."
            
        reporte_insights.append({
            'corner_number': curva_num,
            'start_distance': metro_apex - 100,
            'end_distance': metro_apex + 50,
            'apex_distance': metro_apex,
            'time_loss_seconds': round(delta_entrada, 3),
            'apex_speed_delta_kmh': round(-v_delta, 1), # Invertido para que + signifique que Slow es más rápido, o ajustado
            'braking_delta_meters': round(brake_delta_m, 1) if has_brake else 0.0,
            'throttle_delta_meters': round(throttle_delta_m, 1) if has_throttle else 0.0,
            'description': diagnostico
        })
        
    logger.info(f"  ✓ {len(reporte_insights)} insights generados")
    return reporte_insights
