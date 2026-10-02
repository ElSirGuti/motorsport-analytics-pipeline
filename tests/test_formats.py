"""
Tests de los loaders de formatos nativos EXPERIMENTALES (.ibt de iRacing, .ld de MoTeC).

Los archivos se generan con escritores sinteticos (round-trip). Ademas, si existen
archivos reales del autor en esta maquina, se validan contra ellos (se omiten si no).
"""

import glob
import os
import struct

import numpy as np
import pytest

from src.i18n import set_language
from src.io.loaders import DataLoaderException, load_telemetry_data, read_motec_metadata
from src.io.native_common import convert, detect_format, unwrap_lap_distance

# ─────────────────────────────────────────────────────────────────────────────
# Escritor sintetico de .ibt
# ─────────────────────────────────────────────────────────────────────────────
_T = {"char": 0, "bool": 1, "int": 2, "bitfield": 3, "float": 4, "double": 5}
_SZ = {0: 1, 1: 1, 2: 4, 3: 4, 4: 4, 5: 8}
_FMT = {0: "b", 1: "?", 2: "<i", 3: "<I", 4: "<f", 5: "<d"}


def write_ibt(path, variables, records, *, tick=60, yaml=None, version=2, declared=None, extra_cut=0):
    """variables: [(name, type, unit)]; records: list[dict name->value]."""
    yaml = yaml if yaml is not None else (
        "---\nWeekendInfo:\n TrackName: test track\n TrackDisplayName: Test Raceway\n"
        " TrackConfigName: GP\n TrackLength: 2.50 km\n\nDriverInfo:\n DriverCarIdx: 3\n Drivers:\n"
        " - CarIdx: 0\n   UserName: Someone Else\n   CarScreenName: Wrong Car\n"
        " - CarIdx: 3\n   UserName: Test Driver\n   CarScreenName: Test Car GT3\n   CarPath: testcar\n"
        " - CarIdx: 4\n   UserName: Another\n   CarScreenName: Other\n\nSplitTimeInfo:\n Sectors:\n")
    yb = yaml.encode("latin-1")
    var_off = 144
    offs, o = [], 0
    for _n, t, _u in variables:
        offs.append(o)
        o += _SZ[_T[t]]
    buf_len = o
    si_off = var_off + 144 * len(variables)
    data_off = si_off + len(yb)
    n = len(records)
    head = struct.pack("<10i", version, 1, tick, 0, len(yb), si_off, len(variables), var_off, 1, buf_len)
    head += struct.pack("<2i", 0, 0)
    head += struct.pack("<4i", n, data_off, 0, 0) + b"\0" * 48
    assert len(head) == 112
    sub = struct.pack("<qddii", 1_700_000_000, 0.0, n / tick, 3, declared if declared is not None else n)
    vh = b""
    for (name, t, unit), off in zip(variables, offs):
        vh += struct.pack("<iiiB3x", _T[t], off, 1, 0)
        vh += name.encode().ljust(32, b"\0") + b"".ljust(64, b"\0") + unit.encode().ljust(32, b"\0")
    body = bytearray()
    for r in records:
        for name, t, _u in variables:
            body += struct.pack(_FMT[_T[t]], r[name])
    if extra_cut:
        body = body[:-extra_cut]
    with open(path, "wb") as f:
        f.write(head + sub + vh + yb + bytes(body))


def make_session(n_laps=3, hz=60, lap_s=40.0, track_m=2500.0):
    """Sesion sintetica: n_laps vueltas de lap_s segundos; velocidad 30-60 m/s."""
    n = int(n_laps * lap_s * hz)
    t = np.arange(n) / hz
    lap_phase = (t % lap_s) / lap_s
    speed = 45 + 15 * np.sin(2 * np.pi * lap_phase * 3)                 # m/s
    lapdist = lap_phase * track_m
    lap = (t // lap_s).astype(int)
    thr = np.clip(0.5 + 0.5 * np.sin(2 * np.pi * lap_phase * 3 + 1), 0, 1)
    brk = np.clip(-np.sin(2 * np.pi * lap_phase * 3 + 1), 0, 1)
    return dict(n=n, t=t, speed=speed, lapdist=lapdist, lap=lap, thr=thr, brk=brk,
                steer=0.5 * np.sin(2 * np.pi * lap_phase * 2),            # rad
                lat=9.80665 * 1.5 * np.sin(2 * np.pi * lap_phase * 2),    # m/s^2
                lon=9.80665 * np.cos(2 * np.pi * lap_phase * 3),
                yaw=0.3 * np.sin(2 * np.pi * lap_phase * 2),              # rad/s
                hz=hz, lap_s=lap_s)


IBT_VARS = [
    ("SessionTime", "double", "s"), ("Lap", "int", ""), ("LapDist", "float", "m"),
    ("LapCurrentLapTime", "float", "s"), ("Speed", "float", "m/s"),
    ("Throttle", "float", "%"), ("Brake", "float", "%"), ("SteeringWheelAngle", "float", "rad"),
    ("LatAccel", "float", "m/s^2"), ("LongAccel", "float", "m/s^2"), ("YawRate", "float", "rad/s"),
    ("Gear", "int", ""), ("RPM", "float", "revs/min"), ("FuelLevel", "float", "l"),
    ("LFshockDefl", "float", "m"), ("LFpressure", "float", "kPa"),
    ("LFtempL", "float", "C"), ("LFtempM", "float", "C"), ("LFtempR", "float", "C"),
    ("LFtempCM", "float", "C"), ("OilTemp", "float", "C"), ("WaterTemp", "float", "C"),
    ("OnPitRoad", "bool", ""),
]


def ibt_records(s):
    recs = []
    for i in range(s["n"]):
        recs.append({
            "SessionTime": 100.0 + s["t"][i], "Lap": int(s["lap"][i]), "LapDist": float(s["lapdist"][i]),
            "LapCurrentLapTime": float(s["t"][i] % s["lap_s"]), "Speed": float(s["speed"][i]),
            "Throttle": float(s["thr"][i]), "Brake": float(s["brk"][i]),
            "SteeringWheelAngle": float(s["steer"][i]), "LatAccel": float(s["lat"][i]),
            "LongAccel": float(s["lon"][i]), "YawRate": float(s["yaw"][i]),
            "Gear": 3, "RPM": 6000.0, "FuelLevel": 50.0 - 0.001 * i,
            "LFshockDefl": 0.03, "LFpressure": 190.0,
            "LFtempL": 70.0, "LFtempM": 80.0, "LFtempR": 90.0, "LFtempCM": 99.0,
            "OilTemp": 100.0, "WaterTemp": 90.0, "OnPitRoad": False,
        })
    return recs


@pytest.fixture(scope="module")
def session():
    return make_session()


@pytest.fixture()
def ibt_file(tmp_path, session):
    p = tmp_path / "synthetic.ibt"
    write_ibt(str(p), IBT_VARS, ibt_records(session))
    return str(p)


# ─────────────────────────────────────────────────────────────────────────────
# Escritor sintetico de .ld
# ─────────────────────────────────────────────────────────────────────────────
def write_ld(path, channels, *, driver="Test Driver", vehicle="testcar", venue="test track",
             cut=None, bad_marker=False):
    """channels: [dict(name, unit, freq, values, kind='int16'|'int32'|'float32'|'float16',
    shift, mul, scale, dec)]"""
    meta_ptr = 0x3448
    data_ptr0 = meta_ptr + 124 * len(channels)
    head = bytearray(0x3448)
    struct.pack_into("<I", head, 0, 0x41 if bad_marker else 0x40)
    struct.pack_into("<II", head, 8, meta_ptr, data_ptr0)
    head[0x46:0x4E] = b"ADL\0\0\0\0\0"
    head[0x5E:0x5E + 10] = b"01/02/2026"
    head[0x7E:0x7E + 5] = b"12:34"
    head[0x9E:0x9E + len(driver)] = driver.encode("latin-1")
    head[0xDE:0xDE + len(vehicle)] = vehicle.encode("latin-1")
    head[0x15E:0x15E + len(venue)] = venue.encode("latin-1")
    metas, blobs, ptr = b"", b"", data_ptr0
    for i, ch in enumerate(channels):
        kind = ch.get("kind", "int16")
        shift, mul, scale, dec = ch.get("shift", 0), ch.get("mul", 1), ch.get("scale", 1), ch.get("dec", 0)
        vals = np.asarray(ch["values"], dtype=np.float64)
        if kind.startswith("float"):
            dt = "<f2" if kind == "float16" else "<f4"
            raw, da, dtp = vals.astype(dt), 7, 2 if kind == "float16" else 4
        else:
            dt = "<i2" if kind == "int16" else "<i4"
            raw = np.round((vals / mul - shift) * scale * 10.0 ** dec).astype(dt)
            da, dtp = 3, 2 if kind == "int16" else 4
        blob = raw.tobytes()
        prev = meta_ptr + 124 * (i - 1) if i else 0
        nxt = meta_ptr + 124 * (i + 1) if i < len(channels) - 1 else 0
        metas += struct.pack("<IIIIHHHHhhhh", prev, nxt, ptr, len(raw), 0x2ee1 + i, da, dtp, int(ch["freq"]),
                             shift, mul, scale, dec)
        metas += ch["name"].encode().ljust(32, b"\0") + ch["name"][:8].encode().ljust(8, b"\0")
        metas += ch.get("unit", "").encode().ljust(12, b"\0") + b"\0" * 40
        blobs += blob
        ptr += len(blob)
    data = bytes(head) + metas + blobs
    if cut is not None:
        data = data[:cut]
    with open(path, "wb") as f:
        f.write(data)


def ld_channels(s, hz_hi=60, hz_lo=20):
    """Canales a 60 Hz y a 20 Hz mezclados, con escalado entero (shift/scale/dec)."""
    n_hi = s["n"]
    t_hi = np.arange(n_hi) / hz_hi
    lo = np.arange(0, n_hi, hz_hi // hz_lo)
    return [
        dict(name="Ground Speed", unit="km/h", freq=hz_hi, values=s["speed"] * 3.6, kind="int16",
             shift=150, scale=2, dec=2),
        dict(name="Throttle Pos", unit="%", freq=hz_hi, values=s["thr"] * 100, kind="int16",
             shift=50, scale=6, dec=2),
        dict(name="Brake Pos", unit="%", freq=hz_hi, values=s["brk"] * 100, kind="float32"),
        dict(name="Steering Angle", unit="deg", freq=hz_lo, values=np.rad2deg(s["steer"])[lo], kind="int16",
             shift=0, scale=10, dec=0),
        dict(name="G Force Lat", unit="G", freq=hz_lo, values=(s["lat"] / 9.80665)[lo], kind="int16",
             scale=8, dec=3),
        dict(name="Gear", unit="", freq=hz_lo, values=np.full(len(lo), 4), kind="int16"),
        dict(name="Session Lap Count", unit="", freq=hz_lo, values=s["lap"][lo], kind="int16"),
        dict(name="Lap Time", unit="s", freq=hz_hi, values=(t_hi % s["lap_s"]), kind="float32"),
        dict(name="Engine RPM", unit="rpm", freq=hz_lo, values=np.full(len(lo), 7000.0), kind="float32"),
        dict(name="Tire Pressure FL", unit="psi", freq=hz_lo, values=np.full(len(lo), 29.0), kind="float32"),
        dict(name="Susp Travel FL", unit="mm", freq=hz_lo, values=np.full(len(lo), 30.0), kind="float32"),
    ]


@pytest.fixture()
def ld_file(tmp_path, session):
    p = tmp_path / "synthetic.ld"
    write_ld(str(p), ld_channels(session))
    return str(p)


# ─────────────────────────────────────────────────────────────────────────────
# iRacing .ibt
# ─────────────────────────────────────────────────────────────────────────────
class TestIbt:
    def test_roundtrip_units(self, ibt_file, session):
        df = load_telemetry_data(ibt_file)
        assert len(df) == session["n"]
        assert df.attrs["format"] == "ibt" and df.attrs["experimental"] is True
        np.testing.assert_allclose(df["Speed"], session["speed"] * 3.6, rtol=1e-5)          # m/s -> km/h
        np.testing.assert_allclose(df["Throttle"], session["thr"] * 100, atol=1e-3)          # 0-1 -> %
        np.testing.assert_allclose(df["Brake"], session["brk"] * 100, atol=1e-3)
        np.testing.assert_allclose(df["SteerAngle"], np.rad2deg(session["steer"]), atol=1e-3)  # rad -> deg
        np.testing.assert_allclose(df["LateralG"], session["lat"] / 9.80665, atol=1e-4)       # m/s2 -> g
        np.testing.assert_allclose(df["LongitudinalG"], session["lon"] / 9.80665, atol=1e-4)
        np.testing.assert_allclose(df["YawRate"], np.rad2deg(session["yaw"]), atol=1e-3)     # rad/s -> deg/s
        np.testing.assert_allclose(df["TyrePressFL"], 1.90, atol=1e-6)                       # kPa -> bar
        np.testing.assert_allclose(df["SuspTravelFL"], 30.0, atol=1e-4)                      # m -> mm

    def test_time_and_laps(self, ibt_file, session):
        df = load_telemetry_data(ibt_file)
        assert df["Time"].iloc[0] == 0.0
        assert df["Time"].iloc[-1] == pytest.approx(session["n"] / 60 - 1 / 60, abs=1e-6)
        assert set(df["SessionLapCount"].unique()) == {0, 1, 2}
        # El cronometro por vuelta empieza en 0 en cada vuelta
        for _lap, g in df.groupby("SessionLapCount"):
            assert g["LapTime"].iloc[0] == pytest.approx(0.0, abs=1e-6)

    def test_distance_is_session_cumulative(self, ibt_file):
        df = load_telemetry_data(ibt_file)
        assert df["Distance"].is_monotonic_increasing
        assert df["Distance"].iloc[-1] == pytest.approx(3 * 2500 - 2500 / 2400, rel=1e-3)
        assert df.attrs.get("distance_synthetic") is None

    def test_tyre_temps_use_surface_with_inner_outer_swap(self, ibt_file):
        df = load_telemetry_data(ibt_file)
        # LF = neumatico izquierdo: R es interior, L exterior (como el export MoTeC de iRacing)
        assert df["TyreTempMiddleFL"].iloc[0] == 80.0
        assert df["TyreTempInnerFL"].iloc[0] == 90.0
        assert df["TyreTempOuterFL"].iloc[0] == 70.0

    def test_metadata(self, ibt_file):
        meta = read_motec_metadata(ibt_file)
        assert meta["driver"] == "Test Driver"           # el de DriverCarIdx, no el primero
        assert meta["vehicle"] == "Test Car GT3"
        assert "Test Raceway" in meta["venue"]
        assert load_telemetry_data(ibt_file).attrs["metadata"]["track_length_km"] == 2.5

    def test_detect_by_signature_when_named_csv(self, ibt_file, tmp_path):
        """La API guarda las subidas como session.csv: la firma binaria debe bastar."""
        renamed = tmp_path / "session.csv"
        renamed.write_bytes(open(ibt_file, "rb").read())
        assert detect_format(str(renamed)) == "ibt"
        assert len(load_telemetry_data(str(renamed))) > 100

    def test_truncated_records_loads_available(self, tmp_path, session):
        p = tmp_path / "cut.ibt"
        recs = ibt_records(session)
        write_ibt(str(p), IBT_VARS, recs, extra_cut=3)         # deja el ultimo registro incompleto
        df = load_telemetry_data(str(p))
        assert len(df) == len(recs) - 1
        assert df.attrs["warnings"] == ["ibt_truncated"]

    def test_truncated_header_error_translated(self, ibt_file, tmp_path):
        p = tmp_path / "cut.ibt"
        p.write_bytes(open(ibt_file, "rb").read()[:60])
        set_language("es")
        try:
            with pytest.raises(DataLoaderException, match="truncado"):
                load_telemetry_data(str(p))
            set_language("en")
            with pytest.raises(DataLoaderException, match="truncated"):
                load_telemetry_data(str(p))
        finally:
            set_language("en")

    def test_unsupported_version(self, tmp_path, session):
        p = tmp_path / "v9.ibt"
        write_ibt(str(p), IBT_VARS, ibt_records(session)[:50], version=9)
        with pytest.raises(DataLoaderException, match="version"):
            load_telemetry_data(str(p))

    def test_no_speed_channel(self, tmp_path):
        vars_ = [("SessionTime", "double", "s"), ("Throttle", "float", "%"), ("Brake", "float", "%")]
        recs = [{"SessionTime": i / 60, "Throttle": 0.5, "Brake": 0.0} for i in range(100)]
        p = tmp_path / "nospeed.ibt"
        write_ibt(str(p), vars_, recs)
        with pytest.raises(DataLoaderException, match="(?i)speed"):
            load_telemetry_data(str(p))

    def test_garbage_file_named_ibt(self, tmp_path):
        p = tmp_path / "junk.ibt"
        p.write_bytes(os.urandom(4096))
        with pytest.raises(DataLoaderException):
            load_telemetry_data(str(p))


# ─────────────────────────────────────────────────────────────────────────────
# MoTeC .ld
# ─────────────────────────────────────────────────────────────────────────────
class TestLd:
    def test_roundtrip_scaling_and_resampling(self, ld_file, session):
        df = load_telemetry_data(ld_file)
        assert df.attrs["format"] == "ld" and df.attrs["experimental"] is True
        assert len(df) == session["n"]                       # rejilla comun = frecuencia maxima (60 Hz)
        np.testing.assert_allclose(df["Speed"], session["speed"] * 3.6, atol=0.01)   # shift/scale/dec
        np.testing.assert_allclose(df["Throttle"], session["thr"] * 100, atol=0.02)
        np.testing.assert_allclose(df["Brake"], session["brk"] * 100, atol=1e-3)     # float32 sin escalar
        np.testing.assert_allclose(df["TyrePressFL"], 29.0 / 14.5038, atol=1e-5)     # psi -> bar
        np.testing.assert_allclose(df["SuspTravelFL"], 30.0, atol=1e-4)               # ya en mm

    def test_lowrate_channels_interpolated_and_discrete_held(self, ld_file, session):
        df = load_telemetry_data(ld_file)
        # canal continuo a 20 Hz -> interpolado linealmente a 60 Hz
        expected = np.interp(np.arange(len(df)) / 60, np.arange(0, session["n"], 3) / 60,
                             np.rad2deg(session["steer"])[::3])
        np.testing.assert_allclose(df["SteerAngle"], expected, atol=0.2)
        # discretos: sin valores intermedios inventados
        assert set(df["Gear"].unique()) == {4.0}
        assert set(df["SessionLapCount"].unique()) == {0.0, 1.0, 2.0}

    def test_lap_time_and_synth_distance(self, ld_file):
        df = load_telemetry_data(ld_file)
        assert df["LapTime"].max() == pytest.approx(40.0, abs=0.05)
        assert df.attrs["distance_synthetic"] is True
        assert df["Distance"].is_monotonic_increasing

    def test_metadata(self, ld_file):
        meta = read_motec_metadata(ld_file)
        assert (meta["driver"], meta["vehicle"], meta["venue"]) == ("Test Driver", "testcar", "test track")

    def test_detect_by_signature(self, ld_file, tmp_path):
        renamed = tmp_path / "session.csv"
        renamed.write_bytes(open(ld_file, "rb").read())
        assert detect_format(str(renamed)) == "ld"
        assert len(load_telemetry_data(str(renamed))) > 100

    def test_truncated_data(self, tmp_path, session):
        p = tmp_path / "cut.ld"
        write_ld(str(p), ld_channels(session), cut=0x3448 + 124 * 11 + 2000)
        with pytest.raises(DataLoaderException, match="truncated"):
            load_telemetry_data(str(p))

    def test_bad_marker(self, tmp_path, session):
        p = tmp_path / "bad.ld"
        write_ld(str(p), ld_channels(session), bad_marker=True)
        with pytest.raises(DataLoaderException, match="valid MoTeC"):
            load_telemetry_data(str(p))

    def test_tiny_file_error_in_spanish(self, tmp_path):
        p = tmp_path / "tiny.ld"
        p.write_bytes(b"\x40\x00\x00\x00" + b"\0" * 20)
        set_language("es")
        try:
            with pytest.raises(DataLoaderException, match="truncado"):
                load_telemetry_data(str(p))
        finally:
            set_language("en")

    def test_no_speed_channel(self, tmp_path, session):
        p = tmp_path / "nospeed.ld"
        chans = [c for c in ld_channels(session) if c["name"] != "Ground Speed"]
        write_ld(str(p), chans)
        with pytest.raises(DataLoaderException, match="(?i)speed"):
            load_telemetry_data(str(p))


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────────────────────
class TestHelpers:
    def test_csv_still_detected_as_csv(self, tmp_path):
        p = tmp_path / "a.csv"
        p.write_text("Time,Speed,Brake,Throttle\n0,1,0,0\n")
        assert detect_format(str(p)) == "csv"

    @pytest.mark.parametrize("kind,unit,inp,out", [
        ("speed", "m/s", 10, 36), ("speed", "km/h", 10, 10), ("speed", "mph", 10, 16.09344),
        ("angle_deg", "rad", np.pi, 180), ("angle_deg", "deg", 5, 5),
        ("accel_g", "m/s^2", 9.80665, 1), ("accel_g", "G", 1.2, 1.2),
        ("rate_degs", "rad/s", np.pi, 180), ("pressure_bar", "kPa", 200, 2), ("pressure_bar", "psi", 14.5038, 1),
        ("length_mm", "m", 0.03, 30), ("length_mm", "mm", 30, 30),
    ])
    def test_convert(self, kind, unit, inp, out):
        assert convert(kind, np.array([inp]), unit)[0] == pytest.approx(out)

    def test_unwrap_lap_distance(self):
        d = np.concatenate([np.linspace(0, 1000, 11), np.linspace(10, 1000, 10)])
        out = unwrap_lap_distance(d, hz=1.0)
        assert out[-1] == pytest.approx(1000 + 1000, rel=0.02)
        assert np.all(np.diff(out) >= 0)

    def test_unwrap_ignores_garbage_first_sample(self):
        d = np.array([0.0, 272.0, 272.0, 273.0, 274.0])
        out = unwrap_lap_distance(d, hz=60.0)
        assert out[-1] == pytest.approx(2.0)


# ─────────────────────────────────────────────────────────────────────────────
# Validacion contra archivos reales del autor (se omite si no existen)
# ─────────────────────────────────────────────────────────────────────────────
_IR = os.path.join(os.path.expanduser("~"), "Documents", "iRacing", "Telemetry")
_REAL_IBT = sorted(glob.glob(os.path.join(_IR, "*20-31-36.ibt")))
_REAL_ACTI = sorted(glob.glob(os.path.join(os.path.expanduser("~"), "Documents", "acti", "telem", "*ferrari_458", "*.ld")))


@pytest.mark.skipif(not _REAL_IBT, reason="no hay .ibt reales en esta maquina")
def test_real_ibt_matches_motec_export_of_same_session():
    ibt = _REAL_IBT[0]
    ld = ibt[:-4] + "_Stint_1.ld"
    if not os.path.exists(ld):
        pytest.skip("falta el .ld exportado de la misma sesion")
    a, b = load_telemetry_data(ibt), load_telemetry_data(ld)
    assert abs(len(a) - len(b)) <= 1
    n = min(len(a), len(b))
    # el .ld de iRacing omite el primer registro: desfase de 1 muestra
    sa, sb = a["Speed"].to_numpy()[1:n], b["Speed"].to_numpy()[:n - 1]
    np.testing.assert_allclose(sa, sb, atol=0.05)
    assert a["Distance"].iloc[-1] == pytest.approx(b["Distance"].iloc[-1], rel=1e-3)


@pytest.mark.skipif(not _REAL_ACTI, reason="no hay .ld reales de ACTI en esta maquina")
def test_real_acti_ld_plausible():
    df = load_telemetry_data(_REAL_ACTI[0])
    assert 150 < df["Speed"].max() < 400
    assert 0 <= df["Throttle"].min() and df["Throttle"].max() <= 100.5
    assert df["SessionLapCount"].nunique() >= 2
