import pandas as pd
import numpy as np

def analyze_session(df: pd.DataFrame) -> dict:
    """
    Analiza un DataFrame de telemetría que contiene una sesión completa.
    Agrupa los datos por vuelta y extrae estadísticas clave (tiempo de vuelta, max speed, etc).
    """
    if "SessionLapCount" not in df.columns:
        # Fallback if no lap count is available: treat as single lap
        df["SessionLapCount"] = 1
        
    # Group by lap count
    laps_data = []
    
    # We ignore lap 0 usually as it's the out lap, but we'll include it and let the user filter
    for lap_num, group in df.groupby("SessionLapCount"):
        # Time and distance differences for this lap
        time_col = "LapTime" if "LapTime" in group.columns else ("Time" if "Time" in group.columns else None)
        if time_col is None:
            continue
            
        group = group.sort_values(by=time_col)
        lap_time = group[time_col].max() - group[time_col].min()
        lap_distance = group["Distance"].max() - group["Distance"].min()
        
        # Validar si es una vuelta completa (heuristic: > 1000 metros)
        if pd.isna(lap_distance) or lap_distance < 1000:
            continue
            
        def clean_float(val):
            if pd.isna(val) or np.isinf(val):
                return 0.0
            return float(val)
            
        lap_info = {
            "lap_number": int(lap_num),
            "lap_time": clean_float(lap_time),
            "lap_distance": clean_float(lap_distance),
            "max_speed": clean_float(group["Speed"].max()) if "Speed" in group.columns else 0.0,
            "min_speed": clean_float(group["Speed"].min()) if "Speed" in group.columns else 0.0,
            "max_brake": clean_float(group["Brake"].max()) if "Brake" in group.columns else 0.0,
            "avg_throttle": clean_float(group["Throttle"].mean()) if "Throttle" in group.columns else 0.0,
        }
        laps_data.append(lap_info)
        
    # Determine fastest lap
    fastest_lap = None
    if laps_data:
        fastest_lap = min(laps_data, key=lambda x: x["lap_time"])
        for lap in laps_data:
            lap["is_fastest"] = (lap["lap_number"] == fastest_lap["lap_number"])
            
    # Track Map using the fastest lap
    track_map = []
    if fastest_lap:
        fastest_group = df[df["SessionLapCount"] == fastest_lap["lap_number"]]
        coord_x_col = "CarCoordX" if "CarCoordX" in fastest_group.columns else None
        coord_y_col = "CarCoordZ" if "CarCoordZ" in fastest_group.columns else ("CarCoordY" if "CarCoordY" in fastest_group.columns else None)
        
        if coord_x_col and coord_y_col:
            step = max(1, len(fastest_group) // 500)
            x_coords = fastest_group[coord_x_col].iloc[::step].fillna(0).tolist()
            y_coords = fastest_group[coord_y_col].iloc[::step].fillna(0).tolist()
            track_map = [{"x": float(x), "y": float(y)} for x, y in zip(x_coords, y_coords)]

    return {
        "laps": laps_data,
        "fastest_lap": fastest_lap,
        "track_map": track_map,
        "total_laps": len(laps_data),
    }
