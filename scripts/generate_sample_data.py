"""
Generador de datos sintéticos de telemetría para pruebas.

Simula un circuito ficticio de ~3.5 km con 7 curvas.
Genera dos archivos CSV:
  - lap_clean.csv   → Vuelta de referencia (piloto A, línea óptima)
  - lap_errors.csv  → Vuelta con errores deliberados (piloto B)

Los errores simulados incluyen:
  - Frenado anticipado (brake earlier)
  - Aceleración tardía (throttle later)
  - Menor velocidad en el apex
  
Uso:
    python scripts/generate_sample_data.py
"""

import numpy as np
import pandas as pd
import os

# ─────────────────────────────────────────────────
# Parámetros del circuito
# ─────────────────────────────────────────────────

TRACK_LENGTH = 3500  # metros
SAMPLE_RATE = 100    # Hz (muestras por segundo)

# Definición de curvas: (inicio_frenado_m, inicio_curva_m, apex_m, salida_curva_m)
# Estas son las posiciones en metros a lo largo de la pista
CORNERS = [
    {"name": "Curva 1", "brake_start": 280,  "turn_in": 320,  "apex": 370,  "exit": 430,  "min_speed": 80,  "approach_speed": 200},
    {"name": "Curva 2", "brake_start": 680,  "turn_in": 720,  "apex": 780,  "exit": 850,  "min_speed": 110, "approach_speed": 220},
    {"name": "Curva 3", "brake_start": 1100, "turn_in": 1150, "apex": 1200, "exit": 1280, "min_speed": 65,  "approach_speed": 230},
    {"name": "Curva 4", "brake_start": 1550, "turn_in": 1580, "apex": 1620, "exit": 1680, "min_speed": 95,  "approach_speed": 210},
    {"name": "Curva 5", "brake_start": 2000, "turn_in": 2040, "apex": 2100, "exit": 2170, "min_speed": 75,  "approach_speed": 240},
    {"name": "Curva 6", "brake_start": 2500, "turn_in": 2530, "apex": 2570, "exit": 2630, "min_speed": 120, "approach_speed": 215},
    {"name": "Curva 7", "brake_start": 3050, "turn_in": 3090, "apex": 3150, "exit": 3230, "min_speed": 90,  "approach_speed": 225},
]


def _sigmoid(x, center, steepness=0.1):
    """Función sigmoide suave para transiciones de frenado/aceleración."""
    return 1.0 / (1.0 + np.exp(-steepness * (x - center)))


def _generate_speed_profile(distance, corners, errors=None):
    """
    Genera un perfil de velocidad realista a lo largo de la distancia.
    
    Args:
        distance: Array de distancias en metros.
        corners: Lista de diccionarios con la definición de cada curva.
        errors: Diccionario opcional {corner_index: {"brake_offset": m, "throttle_delay": m, "speed_penalty": km/h}}
    
    Returns:
        Array de velocidades en km/h.
    """
    if errors is None:
        errors = {}
    
    # Empezar con velocidad máxima base en recta
    speed = np.full_like(distance, 220.0, dtype=float)
    
    for i, corner in enumerate(corners):
        err = errors.get(i, {"brake_offset": 0, "throttle_delay": 0, "speed_penalty": 0})
        
        brake_start = corner["brake_start"] + err.get("brake_offset", 0)
        apex_pos = corner["apex"]
        exit_pos = corner["exit"] + err.get("throttle_delay", 0)
        min_speed = corner["min_speed"] - err.get("speed_penalty", 0)
        approach_speed = corner["approach_speed"]
        
        # Zona de frenado: transición suave de approach_speed a min_speed
        brake_zone = (distance >= brake_start - 30) & (distance <= apex_pos)
        if np.any(brake_zone):
            d_brake = distance[brake_zone]
            # Sigmoid descendente
            brake_progress = (d_brake - brake_start) / max(apex_pos - brake_start, 1)
            brake_progress = np.clip(brake_progress, 0, 1)
            # Curva de desaceleración suave (coseno)
            speed_brake = approach_speed - (approach_speed - min_speed) * (0.5 - 0.5 * np.cos(np.pi * brake_progress))
            speed[brake_zone] = np.minimum(speed[brake_zone], speed_brake)
        
        # Zona de aceleración: transición suave de min_speed a velocidad de recta
        accel_zone = (distance > apex_pos) & (distance <= exit_pos + 200)
        if np.any(accel_zone):
            d_accel = distance[accel_zone]
            accel_progress = (d_accel - apex_pos) / max(exit_pos + 200 - apex_pos, 1)
            accel_progress = np.clip(accel_progress, 0, 1)
            # Aceleración progresiva (cuadrática)
            target_exit_speed = min(approach_speed + 20, 250)
            speed_accel = min_speed + (target_exit_speed - min_speed) * accel_progress**1.5
            speed[accel_zone] = np.minimum(speed[accel_zone], speed_accel)
    
    # Suavizar el perfil completo
    from scipy.ndimage import uniform_filter1d
    speed = uniform_filter1d(speed, size=15)
    
    # Agregar un poco de ruido realista (± 0.5 km/h)
    speed += np.random.normal(0, 0.3, len(speed))
    speed = np.clip(speed, 30, 280)
    
    return speed


def _generate_brake_channel(distance, speed, corners, errors=None):
    """Genera el canal de presión de freno (0-100%) basado en la desaceleración."""
    if errors is None:
        errors = {}
    
    brake = np.zeros_like(distance, dtype=float)
    
    for i, corner in enumerate(corners):
        err = errors.get(i, {"brake_offset": 0})
        brake_start = corner["brake_start"] + err.get("brake_offset", 0)
        apex_pos = corner["apex"]
        
        # Zona de frenado activo
        brake_zone = (distance >= brake_start) & (distance <= apex_pos + 10)
        if np.any(brake_zone):
            d_brake = distance[brake_zone]
            # Perfil de frenado: fuerte al principio, trail braking hacia el apex
            progress = (d_brake - brake_start) / max(apex_pos - brake_start, 1)
            progress = np.clip(progress, 0, 1)
            # Pico de frenado al ~20% de la zona, luego decae (trail braking)
            brake_profile = np.where(
                progress < 0.2,
                progress / 0.2 * 95,  # Ramp-up rápido
                95 * (1 - (progress - 0.2) / 0.8) ** 0.6  # Trail braking
            )
            brake[brake_zone] = brake_profile
    
    # Agregar ruido
    brake += np.random.normal(0, 0.5, len(brake))
    brake = np.clip(brake, 0, 100)
    # Poner a cero valores muy pequeños (< 1%)
    brake[brake < 1.0] = 0.0
    
    return brake


def _generate_throttle_channel(distance, speed, corners, errors=None):
    """Genera el canal de acelerador (0-100%) complementario al freno."""
    if errors is None:
        errors = {}
    
    throttle = np.full_like(distance, 100.0, dtype=float)
    
    for i, corner in enumerate(corners):
        err = errors.get(i, {"brake_offset": 0, "throttle_delay": 0})
        brake_start = corner["brake_start"] + err.get("brake_offset", 0)
        exit_pos = corner["exit"] + err.get("throttle_delay", 0)
        apex_pos = corner["apex"]
        
        # Zona de freno: throttle = 0
        coast_start = brake_start - 5
        brake_zone = (distance >= coast_start) & (distance <= apex_pos)
        throttle[brake_zone] = 0.0
        
        # Zona de transición apex → full throttle
        trans_zone = (distance > apex_pos) & (distance <= exit_pos)
        if np.any(trans_zone):
            d_trans = distance[trans_zone]
            progress = (d_trans - apex_pos) / max(exit_pos - apex_pos, 1)
            progress = np.clip(progress, 0, 1)
            throttle[trans_zone] = 100 * progress**1.2
    
    # Ruido
    throttle += np.random.normal(0, 0.8, len(throttle))
    throttle = np.clip(throttle, 0, 100)
    
    return throttle


def _calculate_time_from_speed(distance, speed_kmh):
    """Calcula el canal de tiempo acumulado a partir de velocidad y distancia."""
    speed_ms = speed_kmh / 3.6  # Convertir a m/s
    speed_ms = np.maximum(speed_ms, 1.0)  # Evitar división por cero
    
    ds = np.diff(distance)
    dt = ds / speed_ms[:-1]
    time = np.concatenate([[0], np.cumsum(dt)])
    
    return time


def _generate_gear(speed_kmh):
    """Simula el canal de marcha basado en la velocidad."""
    gear = np.ones_like(speed_kmh, dtype=int)
    gear[speed_kmh > 60] = 2
    gear[speed_kmh > 90] = 3
    gear[speed_kmh > 130] = 4
    gear[speed_kmh > 170] = 5
    gear[speed_kmh > 210] = 6
    return gear


def _generate_rpm(speed_kmh, gear):
    """Simula RPM basado en velocidad y marcha."""
    # Simulación simplificada
    base_rpm = 3000
    rpm_per_kmh = {1: 80, 2: 55, 3: 40, 4: 30, 5: 25, 6: 20}
    rpm = np.array([base_rpm + speed_kmh[i] * rpm_per_kmh.get(gear[i], 30) for i in range(len(speed_kmh))])
    rpm += np.random.normal(0, 50, len(rpm))
    rpm = np.clip(rpm, 2000, 12000)
    return rpm


def _generate_steer_angle(distance, corners):
    """Genera ángulo de dirección simulado."""
    steer = np.zeros_like(distance, dtype=float)
    
    for corner in corners:
        turn_in = corner["turn_in"]
        apex = corner["apex"]
        exit_pos = corner["exit"]
        
        # Dirección negativa o positiva (alternamos)
        direction = 1 if corners.index(corner) % 2 == 0 else -1
        max_angle = 45 * (1 - corner["min_speed"] / 250)  # Más lento = más giro
        
        zone = (distance >= turn_in - 20) & (distance <= exit_pos + 20)
        if np.any(zone):
            d = distance[zone]
            center = (turn_in + exit_pos) / 2
            width = (exit_pos - turn_in) / 2
            steer[zone] = direction * max_angle * np.exp(-((d - center) / width) ** 2)
    
    steer += np.random.normal(0, 0.3, len(steer))
    return steer


def _generate_lateral_g(speed_kmh, steer_angle):
    """Genera fuerza lateral G simulada."""
    speed_ms = speed_kmh / 3.6
    # G lateral ∝ v² * ángulo de dirección (simplificado)
    lat_g = (speed_ms ** 2) * np.abs(steer_angle) / 100000
    lat_g *= np.sign(steer_angle)
    lat_g += np.random.normal(0, 0.02, len(lat_g))
    lat_g = np.clip(lat_g, -4, 4)
    return lat_g


def _generate_longitudinal_g(speed_kmh, time):
    """Genera fuerza longitudinal G basada en la aceleración."""
    speed_ms = speed_kmh / 3.6
    dt = np.diff(time)
    dt[dt == 0] = 0.001
    dv = np.diff(speed_ms)
    accel = dv / dt
    long_g = np.concatenate([[0], accel]) / 9.81
    
    # Suavizar
    from scipy.ndimage import uniform_filter1d
    long_g = uniform_filter1d(long_g, size=10)
    long_g += np.random.normal(0, 0.01, len(long_g))
    long_g = np.clip(long_g, -5, 3)
    
    return long_g


def generate_lap(distance, corners, errors=None, label="clean"):
    """
    Genera un DataFrame completo de telemetría para una vuelta.
    
    Args:
        distance: Array de distancias uniformes.
        corners: Definición de las curvas del circuito.
        errors: Dict de errores por curva (opcional).
        label: Etiqueta para logging.
    
    Returns:
        pd.DataFrame con todos los canales de telemetría.
    """
    print(f"  Generando vuelta '{label}'...")
    
    np.random.seed(42 if label == "clean" else 123)
    
    speed = _generate_speed_profile(distance, corners, errors)
    brake = _generate_brake_channel(distance, speed, corners, errors)
    throttle = _generate_throttle_channel(distance, speed, corners, errors)
    time = _calculate_time_from_speed(distance, speed)
    gear = _generate_gear(speed)
    rpm = _generate_rpm(speed, gear)
    steer = _generate_steer_angle(distance, corners)
    lat_g = _generate_lateral_g(speed, steer)
    long_g = _generate_longitudinal_g(speed, time)
    
    df = pd.DataFrame({
        "Distance": np.round(distance, 3),
        "Speed": np.round(speed, 2),
        "Brake": np.round(brake, 2),
        "Throttle": np.round(throttle, 2),
        "Gear": gear,
        "RPM": np.round(rpm, 1),
        "SteerAngle": np.round(steer, 3),
        "LateralG": np.round(lat_g, 4),
        "LongitudinalG": np.round(long_g, 4),
        "LapTime": np.round(time, 6),
    })
    
    print(f"    - {len(df)} muestras, tiempo de vuelta: {time[-1]:.3f}s")
    return df


def main():
    """Genera los archivos CSV de prueba."""
    # Ruta de salida
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "data", "raw")
    os.makedirs(output_dir, exist_ok=True)
    
    # Vector de distancia uniforme (cada metro)
    distance = np.linspace(0, TRACK_LENGTH, TRACK_LENGTH + 1)
    
    print("=" * 60)
    print("GENERADOR DE DATOS SINTÉTICOS DE TELEMETRÍA")
    print(f"Circuito: {TRACK_LENGTH}m, {len(CORNERS)} curvas")
    print("=" * 60)
    
    # ── Vuelta limpia (Piloto A) ──
    df_clean = generate_lap(distance, CORNERS, errors=None, label="clean")
    clean_path = os.path.join(output_dir, "lap_clean.csv")
    df_clean.to_csv(clean_path, index=False)
    print(f"  > Guardado: {clean_path}")
    
    # ── Vuelta con errores (Piloto B) ──
    # Definir errores deliberados en curvas específicas
    errors = {
        0: {"brake_offset": -15, "throttle_delay": 12, "speed_penalty": 5},    # Curva 1: frena 15m antes
        2: {"brake_offset": -25, "throttle_delay": 18, "speed_penalty": 8},    # Curva 3: frena 25m antes (error grande)
        3: {"brake_offset": -10, "throttle_delay": 8,  "speed_penalty": 3},    # Curva 4: error menor
        4: {"brake_offset": -20, "throttle_delay": 15, "speed_penalty": 6},    # Curva 5: error medio
        6: {"brake_offset": -12, "throttle_delay": 10, "speed_penalty": 4},    # Curva 7: error menor
    }
    
    df_errors = generate_lap(distance, CORNERS, errors=errors, label="errors")
    errors_path = os.path.join(output_dir, "lap_errors.csv")
    df_errors.to_csv(errors_path, index=False)
    print(f"  > Guardado: {errors_path}")
    
    print()
    print("=" * 60)
    print("RESUMEN")
    print(f"  Vuelta limpia:     {df_clean['LapTime'].iloc[-1]:.3f}s")
    print(f"  Vuelta con errors: {df_errors['LapTime'].iloc[-1]:.3f}s")
    print(f"  Delta:             {df_errors['LapTime'].iloc[-1] - df_clean['LapTime'].iloc[-1]:.3f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
