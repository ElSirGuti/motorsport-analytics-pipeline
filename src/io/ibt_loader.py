"""
Loader de telemetria nativa de iRacing (.ibt).  EXPERIMENTAL.

Formato (documentado publicamente en el irsdk): todo little-endian.

  irsdk_header (112 B)    ver, status, tickRate, sessionInfoUpdate, sessionInfoLen,
                          sessionInfoOffset, numVars, varHeaderOffset, numBuf, bufLen,
                          pad[2], varBuf[4] {tickCount, bufOffset, pad[2]}
  irsdk_diskSubHeader     sessionStartDate (i64), sessionStartTime (f64),
  (32 B, en el byte 112)  sessionEndTime (f64), sessionLapCount (i32), sessionRecordCount (i32)
  irsdk_varHeader[numVars] (144 B c/u en varHeaderOffset)
                          type i32, offset i32, count i32, countAsTime u8, pad[3],
                          name[32], desc[64], unit[32]
  YAML de sesion          sessionInfoLen bytes en sessionInfoOffset (ISO-8859-1)
  registros               sessionRecordCount registros de bufLen bytes desde varBuf[0].bufOffset

Tipos: 0 char(1), 1 bool(1), 2 int(4), 3 bitfield(4), 4 float(4), 5 double(8).

Los registros se leen con ``np.memmap`` + ``np.ndarray(strides=bufLen)``: solo se
materializan en memoria las columnas que se mapean a canales de la app.
"""

from __future__ import annotations

import logging
import os
import re
import struct
from typing import Dict, List, Optional

import numpy as np

from src.i18n import _ as _tr
from src.io.native_common import RawChannel, build_frame, pick_channels

logger = logging.getLogger(__name__)

HEADER_SIZE = 112
SUBHEADER_SIZE = 32
VARHEADER_SIZE = 144
_TYPES = {0: ("u1", 1), 1: ("u1", 1), 2: ("<i4", 4), 3: ("<u4", 4), 4: ("<f4", 4), 5: ("<f8", 8)}
_DISCRETE_TYPES = {0, 1, 2, 3}
SUPPORTED_VERSIONS = (1, 2)


def _err(key: str, **kw):
    from src.io.loaders import DataLoaderException
    return DataLoaderException(_tr(key, **kw))


def _cstr(b: bytes) -> str:
    return b.split(b"\0", 1)[0].decode("latin-1", errors="replace").strip()


class IbtFile:
    """Cabecera + variables + YAML de un .ibt (sin leer los registros)."""

    def __init__(self, path: str):
        self.path = path
        self.size = os.path.getsize(path)
        if self.size < HEADER_SIZE + SUBHEADER_SIZE:
            raise _err("fmt_ibt_truncated")
        with open(path, "rb") as f:
            head = f.read(HEADER_SIZE + SUBHEADER_SIZE)
            (self.ver, self.status, self.tick_rate, _siu, self.si_len, self.si_off,
             self.num_vars, self.var_off, self.num_buf, self.buf_len) = struct.unpack_from("<10i", head, 0)
            if self.ver not in SUPPORTED_VERSIONS:
                raise _err("fmt_ibt_version_unsupported", ver=self.ver)
            if not (1 <= self.tick_rate <= 1000) or self.num_vars <= 0 or self.buf_len <= 0 \
                    or self.num_vars > 20000 or self.buf_len > 50_000_000:
                raise _err("fmt_ibt_bad_header")
            self.buf_offset = struct.unpack_from("<i", head, 52)[0]   # varBuf[0].bufOffset
            (self.start_date, self.start_time, self.end_time,
             self.lap_count, self.record_count) = struct.unpack_from("<qddii", head, HEADER_SIZE)

            vh_end = self.var_off + self.num_vars * VARHEADER_SIZE
            if self.var_off < HEADER_SIZE or vh_end > self.size or self.buf_offset <= 0:
                raise _err("fmt_ibt_truncated")
            f.seek(self.var_off)
            raw = f.read(self.num_vars * VARHEADER_SIZE)
            if len(raw) < self.num_vars * VARHEADER_SIZE:
                raise _err("fmt_ibt_truncated")
            self.vars: List[dict] = []
            for i in range(self.num_vars):
                o = i * VARHEADER_SIZE
                vtype, off, count, _cat = struct.unpack_from("<iiiB", raw, o)
                self.vars.append({
                    "type": vtype, "offset": off, "count": count,
                    "name": _cstr(raw[o + 16:o + 48]),
                    "desc": _cstr(raw[o + 48:o + 112]),
                    "unit": _cstr(raw[o + 112:o + 144]),
                })
            self.yaml = ""
            if self.si_len > 0 and self.si_off > 0 and self.si_off + self.si_len <= self.size:
                f.seek(self.si_off)
                self.yaml = f.read(self.si_len).decode("latin-1", errors="replace")

        # numero de registros realmente presentes en disco
        on_disk = max(0, (self.size - self.buf_offset) // self.buf_len)
        declared = self.record_count if self.record_count > 0 else on_disk
        self.truncated = on_disk < declared
        self.n_records = min(declared, on_disk)

    # ── YAML (parser tolerante: el YAML de iRacing no siempre es valido) ──
    def yaml_value(self, key: str, section: Optional[str] = None) -> Optional[str]:
        text = self.yaml
        if section:
            i = text.find(f"\n{section}:")
            if i < 0:
                return None
            nxt = re.search(r"\n[A-Za-z]\w*:", text[i + 1:])
            text = text[i: i + 1 + nxt.start()] if nxt else text[i:]
        m = re.search(rf"^\s*{re.escape(key)}:[ \t]*(.*?)\s*$", text, re.M)
        return m.group(1).strip().strip('"') if m else None

    def metadata(self) -> dict:
        meta = {"driver": None, "vehicle": None, "venue": None, "track_length_km": None,
                "format": "ibt", "experimental": True}
        try:
            idx = self.yaml_value("DriverCarIdx", "DriverInfo")
            text = self.yaml
            i = text.find("\n Drivers:")
            if idx is not None and i >= 0:
                m = re.search(rf"- CarIdx: {re.escape(idx)}\s*\n(.*?)(?=\n - CarIdx:|\Z)", text[i:], re.S)
                if m:
                    blk = m.group(1)
                    for key, field in (("UserName", "driver"), ("CarScreenName", "vehicle")):
                        mm = re.search(rf"^\s*{key}:[ \t]*(.*?)\s*$", blk, re.M)
                        if mm:
                            meta[field] = mm.group(1).strip().strip('"')
            disp = self.yaml_value("TrackDisplayName", "WeekendInfo") or self.yaml_value("TrackName", "WeekendInfo")
            cfg = self.yaml_value("TrackConfigName", "WeekendInfo")
            if disp:
                meta["venue"] = f"{disp} ({cfg})" if cfg and cfg.lower() not in disp.lower() else disp
            tl = self.yaml_value("TrackLength", "WeekendInfo")
            if tl:
                mm = re.match(r"([\d.]+)", tl)
                meta["track_length_km"] = float(mm.group(1)) if mm else None
        except Exception:  # los metadatos nunca deben tumbar la carga
            logger.debug("No se pudieron leer metadatos del YAML .ibt", exc_info=True)
        return meta


def read_ibt_metadata(path: str) -> dict:
    try:
        return IbtFile(path).metadata()
    except Exception:
        return {"driver": None, "vehicle": None, "venue": None}


def load_ibt(path: str):
    """Carga un .ibt y devuelve un DataFrame con canales canonicos y unidades normalizadas."""
    ibt = IbtFile(path)
    if ibt.n_records < 2:
        raise _err("fmt_ibt_truncated")
    if ibt.truncated:
        logger.warning("Archivo .ibt truncado: %d de %d registros disponibles", ibt.n_records, ibt.record_count)

    mm = np.memmap(path, dtype=np.uint8, mode="r", offset=ibt.buf_offset,
                   shape=(ibt.n_records * ibt.buf_len,))
    n = ibt.n_records

    def make_reader(v):
        dt, size = _TYPES[v["type"]]
        if v["offset"] < 0 or v["offset"] + size > ibt.buf_len:
            return None
        off = v["offset"]

        def read() -> np.ndarray:
            arr = np.ndarray((n,), dtype=dt, buffer=mm, offset=off, strides=(ibt.buf_len,))
            return np.array(arr, dtype=np.float64)   # copia: la columna sale del memmap
        return read

    available: Dict[str, List[RawChannel]] = {}
    for v in ibt.vars:
        if v["type"] not in _TYPES or v["count"] != 1:      # los arrays (p. ej. *_ST) se ignoran
            continue
        reader = make_reader(v)
        if reader is None:
            continue
        available.setdefault(v["name"], []).append(
            RawChannel(v["name"], v["unit"], float(ibt.tick_rate), n, reader,
                       discrete=v["type"] in _DISCRETE_TYPES))

    chosen = pick_channels(available)

    # Tiempo: SessionTime (f64) si existe y es creciente; si no, indice / tickRate
    time_s = None
    st = available.get("SessionTime")
    if st:
        t = st[0].values()
        if np.all(np.isfinite(t)) and t[-1] > t[0]:
            time_s = t
    try:
        df = build_frame(chosen, fmt="ibt", time_s=time_s, grid_hz=float(ibt.tick_rate),
                         fraction_pedals=True, available_names=sorted(available),
                         metadata=ibt.metadata())
    finally:
        del mm
    if ibt.truncated:
        df.attrs["warnings"] = ["ibt_truncated"]
    return df
