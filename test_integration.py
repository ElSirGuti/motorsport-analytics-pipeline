import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

from src.io.loaders import load_telemetry_data
from src.analytics.geometry import (
    procesar_geometria_pista_perfecta,
    detectar_apexes_perfectos,
    reporte_apexes,
)
from src.analytics.alignment import (
    alinear_vueltas_y_calcular_delta,
    resumir_delta_por_sector,
)
from src.analytics.insights import analizar_errores_por_curva

FAST = r'C:\Users\elgut\Downloads\vuelta_rapida.csv'
SLOW = r'C:\Users\elgut\Downloads\vuelta_lenta.csv'

print("=== Paso 1: Carga y limpieza ===")
df_fast = load_telemetry_data(FAST)
df_slow = load_telemetry_data(SLOW)
print(f"Fast: {df_fast.shape}  |  Slow: {df_slow.shape}")
print("Columnas key:", [c for c in ['Speed','Throttle','Brake','CarCoordX','CarCoordY','CarCoordZ'] if c in df_fast.columns])

print("\n=== Paso 2: Geometria de pista ===")
df_geo = procesar_geometria_pista_perfecta(df_fast)
apexes = detectar_apexes_perfectos(df_geo)
print(reporte_apexes(apexes))

print("\n=== Paso 3: Time Delta ===")
df_alineado = alinear_vueltas_y_calcular_delta(df_fast, df_slow)
print("Columnas:", list(df_alineado.columns))
print(f"Delta total: {df_alineado['Delta_Time'].iloc[-1]:+.3f}s")
print(df_alineado[['Distance','Speed_Fast','Speed_Slow','Delta_Time']].head(5))

print("\n=== Paso 4: Sectorizacion ===")
df_sectores = resumir_delta_por_sector(df_alineado, apexes)
print(df_sectores.to_string(index=False))

print("\n=== Paso 5: Insights Automatizados ===")
insights = analizar_errores_por_curva(df_alineado, apexes)
for ins in insights:
    print(f"Curva {ins['corner_number']} (Apex: {ins['apex_distance']:.0f}m): {ins['description']}")
    print(f"  Delta frenada: {ins['braking_delta_meters']}m | V-Min Delta: {ins['apex_speed_delta_kmh']} km/h | Delta gas: {ins['throttle_delta_meters']}m | Perdida total: {ins['time_loss_seconds']}s")
