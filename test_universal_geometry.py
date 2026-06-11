import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import CubicSpline
from scipy.signal import savgol_filter, find_peaks

def detectar_linea_de_cabecera(csv_path):
    """Busca la línea de cabecera real asegurándose de que contenga la estructura masiva de canales"""
    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        for i, linea in enumerate(f):
            columnas = linea.split(',')
            if len(columnas) > 50 and ("Distance" in linea or "Car Coord X" in linea):
                return i
    return 0

def cargar_y_limpiar_telemetria(csv_path):
    linea_inicio = detectar_linea_de_cabecera(csv_path)
    print(f"🤖 Tabla masiva encontrada. Saltando {linea_inicio} líneas de metadatos...")
    
    # 1. Cargar el CSV partiendo desde la cabecera
    df = pd.read_csv(csv_path, skiprows=linea_inicio)
    df.columns = df.columns.str.strip()
    
    # 2. Eliminar la fila de unidades ('m', 'km/h', etc.)
    primer_elemento_dist = str(df['Distance'].iloc[0]).strip()
    if primer_elemento_dist == 'm' or not primer_elemento_dist.replace('.', '', 1).isdigit():
        print("📏 Fila de unidades detectada. Eliminándola limpiamente...")
        df = df.drop(df.index[0]).reset_index(drop=True)
    
    # 3. DETECTAR EL CANAL DE VELOCIDAD DINÁMICAMENTE
    col_velocidad = next((c for c in df.columns if "speed" in c.lower() or "vel" in c.lower()), None)
    if col_velocidad is None:
        print("📋 Canales disponibles por si acaso:", list(df.columns[:20]))
        raise KeyError("No se encontró ninguna columna que contenga 'Speed' o 'Vel' en sus nombres.")
    
    print(f"🚗 Canal de velocidad detectado automáticamente como: '{col_velocidad}'")
    
    # Mapeo de nombres esperados por el pipeline
    rename_dict = {
        'Car Coord X': 'Car_X',
        'Car Coord Z': 'Car_Z',
        'Car Coord Y': 'Car_Y',
        col_velocidad: 'Speed'
    }
    
    col_throttle = next((c for c in df.columns if "throttle pos" in c.lower() or "gas" in c.lower() or "throttle" in c.lower()), None)
    if col_throttle:
        rename_dict[col_throttle] = 'Throttle'
    col_brake = next((c for c in df.columns if "brake pos" in c.lower() or "brake" in c.lower()), None)
    if col_brake:
        rename_dict[col_brake] = 'Brake'
        
    df = df.rename(columns=rename_dict)
    
    # Canales clave a procesar numéricamente
    canales_clave = ['Car_X', 'Car_Z', 'Car_Y', 'Distance', 'Speed']
    if 'Throttle' in df.columns:
        canales_clave.append('Throttle')
    if 'Brake' in df.columns:
        canales_clave.append('Brake')
        
    for col in canales_clave:
        df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    df = df.dropna(subset=['Car_X', 'Car_Z', 'Car_Y', 'Distance', 'Speed']).reset_index(drop=True)
    
    print(f"📋 ¡Éxito! Dataset filtrado con {df.shape[1]} canales y {df.shape[0]} filas de telemetría pura.")
    return df

def procesar_geometria_pista_perfecta(df):
    print("\n🧼 Iniciando purga de ruido y alineación geométrica real...")
    
    # 1. Limpieza inicial de duplicados espaciales
    df = df.drop_duplicates(subset=['Distance']).sort_values('Distance').reset_index(drop=True)
    
    dist_max = df['Distance'].max()
    dist_uniforme = np.arange(0, dist_max, 1.0) # Forzar resolución de 1 metro
    
    # NOTA: En la telemetría de Assetto Corsa (ACTI), el plano horizontal real está definido 
    # por Car_X (Car Coord X) y Car_Y (Car Coord Y). Car_Z (Car Coord Z) es la elevación real.
    x_interp = np.interp(dist_uniforme, df['Distance'], df['Car_X'])
    y_interp = np.interp(dist_uniforme, df['Distance'], df['Car_Y'])
    
    # 2. Suavizado macroscópico (Ventana de 75m, polinomio grado 2 para curvas suaves)
    x_smooth = savgol_filter(x_interp, window_length=75, polyorder=2)
    y_smooth = savgol_filter(y_interp, window_length=75, polyorder=2)
    
    spline_x = CubicSpline(dist_uniforme, x_smooth)
    spline_y = CubicSpline(dist_uniforme, y_smooth)
    
    dx = spline_x(dist_uniforme, 1)
    ddx = spline_x(dist_uniforme, 2)
    dy = spline_y(dist_uniforme, 1)
    ddy = spline_y(dist_uniforme, 2)
    
    numerador = np.abs(dx * ddy - dy * ddx)
    denominador = (dx**2 + dy**2)**(1.5)
    curvatura_limpia = np.where(denominador > 1e-6, numerador / denominador, 0)
    
    df_geo = pd.DataFrame({
        'Distance': dist_uniforme,
        'Curvature': curvatura_limpia
    })
    
    for col in ['Speed', 'Throttle', 'Brake', 'Car_Z']:
        if col in df.columns:
            df_geo[col] = np.interp(dist_uniforme, df['Distance'], df[col])
            
    if 'Car_Z' in df_geo.columns:
        df_geo['Elevation'] = df_geo['Car_Z']
            
    return df_geo

def detectar_apexes_perfectos(df_geo):
    print("\n🔍 Detectando Apexes con calibración de grado industrial...")
    max_kappa = df_geo['Curvature'].max()
    
    # Exigimos que el pico destaque al menos un 15% respecto a sus valles vecinos (prominencia)
    # distance=100 y Throttle < 85.0% son vitales para no omitir la Curva 1 y poder diferenciar 
    # curvas sucesivas rápidas (como la 6 y 7, o la 9 y 10).
    umbral_prominencia = max_kappa * 0.15 
    
    indices_apex, _ = find_peaks(
        df_geo['Curvature'], 
        height=0.008,               # Ignora totalmente las rectas limpias
        prominence=umbral_prominencia, 
        distance=100                # Separación mínima entre curvas sucesivas
    )
    
    df_candidatos = df_geo.iloc[indices_apex].copy()
    
    # Regla de oro del Motorsport: En el Apex no vas acelerando a fondo
    # Filtramos falsos positivos. Usamos 85% para permitir la transición de tracción en Curva 1.
    apexes_reales = df_candidatos[df_candidatos['Throttle'] < 85.0].copy()
    print(f"🏁 Filtrado completado. Se detectaron {len(apexes_reales)} curvas reales.")
    
    print("\n=======================================================")
    print("      REPORTE GEOMÉTRICO CALIBRADO (PERFECTO)         ")
    print("=======================================================")
    for i, (_, apex) in enumerate(apexes_reales.iterrows(), 1):
        dist = apex['Distance']
        vel = apex['Speed']
        kappa = apex['Curvature']
        alt = apex['Elevation'] if 'Elevation' in apex else 0.0
        throttle = apex['Throttle']
        
        radio_aprox = 1 / kappa if kappa > 0 else float('inf')
        tipo = "Rápida" if radio_aprox > 90 else "Media" if radio_aprox > 40 else "Frenada Fuerte / Lenta"
        
        print(f"📍 Curva {i:02d} | Metro: {dist:6.1f}m | V-Apex: {vel:5.1f} km/h | Elevación: {alt:5.1f}m | Throttle: {throttle:4.1f}% | Radio: {radio_aprox:.1f}m -> [{tipo}]")
    print("=======================================================\n")
    
    return apexes_reales

if __name__ == "__main__":
    mi_csv = "C:\\Users\\elgut\\Downloads\\vuelta_rapida.csv" 
    try:
        df_limpio = cargar_y_limpiar_telemetria(mi_csv)
        datos_ia = procesar_geometria_pista_perfecta(df_limpio)
        print("✅ ¡Pipeline geométrico completado con éxito!")
        
        # --- NUEVA LÓGICA DE SEGMENTACIÓN ---
        puntos_apex = detectar_apexes_perfectos(datos_ia)
        
        # Re-graficamos pero esta vez marcando los Apex detectados con estrellas negras
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        
        ax1.plot(datos_ia['Distance'], datos_ia['Speed'], color='blue', label='Velocidad')
        ax1.scatter(puntos_apex['Distance'], puntos_apex['Speed'], color='black', marker='X', s=100, zorder=5, label='Apex Detectado')
        ax1.set_ylabel('Velocidad (km/h)')
        ax1.grid(True)
        ax1.legend()
        
        ax2.plot(datos_ia['Distance'], datos_ia['Curvature'], color='red', label='Curvatura Geométrica (κ)')
        ax2.scatter(puntos_apex['Distance'], puntos_apex['Curvature'], color='black', marker='X', s=100, zorder=5)
        ax2.set_ylabel('Curvatura (1/R)')
        ax2.set_xlabel('Distancia Recorrida (m)')
        ax2.grid(True)
        
        plt.suptitle('Detección Autónoma de Vértices para el Modelo de IA', fontsize=14)
        plt.show()
        
    except Exception as e:
        print(f"❌ Ocurrió un problema durante la ejecución: {e}")