"""
Loader de logs nativos de MoTeC i2 (.ld).  EXPERIMENTAL.

Estructura (conocimiento publico del formato, p. ej. proyecto ldparser; little-endian):

  Cabecera (en el byte 0)
    +0x00 u32 marcador (0x40)         +0x08 u32 puntero a la meta del primer canal
    +0x0C u32 puntero a los datos     +0x24 u32 puntero a evento
    +0x46 serie/dispositivo ("ADL"...)  y, a partir de ahi: fecha[16], hora[16],
    piloto[64], vehiculo[64], venue[64], ... (cadenas ASCII/latin-1 rellenas con 0)

  Meta de canal (124 bytes), lista enlazada por punteros absolutos:
    u32 prev, u32 next, u32 data_ptr, u32 n_datos,
    u16 contador, u16 dtype_a, u16 dtype, u16 freq,
    i16 shift, i16 mul, i16 scale, i16 dec,
    name[32], short_name[8], unit[12], 40 bytes de relleno

  Datos: n_datos muestras contiguas en data_ptr.
    dtype_a == 7 -> flotante (dtype 2 = float16, 4 = float32), sin escalado.
    en otro caso -> entero con signo (dtype 2 = int16, 4 = int32) y
    valor = (raw / scale * 10**-dec + shift) * mul.

Cada canal puede tener su propia frecuencia; ``build_frame`` los remuestrea a la
frecuencia maxima de los canales usados. Las columnas se leen con ``np.memmap``
(solo las que se mapean a canales de la app).
"""

from __future__ import annotations

import logging
import os
import struct
from typing import Dict, List

import numpy as np

from src.i18n import _ as _tr
from src.io.native_common import RawChannel, build_frame, pick_channels

logger = logging.getLogger(__name__)

CHAN_META_SIZE = 124
MIN_FILE_SIZE = 0x200
MAX_CHANNELS = 5000
_HEADER_OFF = {"meta_ptr": 8, "data_ptr": 12, "event_ptr": 36}
_DATE_OFF, _TIME_OFF, _DRIVER_OFF, _VEHICLE_OFF, _VENUE_OFF = 0x5E, 0x7E, 0x9E, 0xDE, 0x15E


def _err(key: str, **kw):
    from src.io.loaders import DataLoaderException
    return DataLoaderException(_tr(key, **kw))


def _cstr(b: bytes) -> str:
    return b.split(b"\0", 1)[0].decode("latin-1", errors="replace").strip()


class LdFile:
    def __init__(self, path: str):
        self.path = path
        self.size = os.path.getsize(path)
        if self.size < MIN_FILE_SIZE:
            raise _err("fmt_ld_truncated")
        with open(path, "rb") as f:
            head = f.read(0x200)
        if struct.unpack_from("<I", head, 0)[0] != 0x40:
            raise _err("fmt_ld_bad_header")
        self.meta_ptr, self.data_ptr = struct.unpack_from("<II", head, 8)
        if not (0 < self.meta_ptr < self.size) or self.data_ptr > self.size:
            raise _err("fmt_ld_truncated")
        self.date = _cstr(head[_DATE_OFF:_DATE_OFF + 16])
        self.time = _cstr(head[_TIME_OFF:_TIME_OFF + 16])
        self.driver = _cstr(head[_DRIVER_OFF:_DRIVER_OFF + 64])
        self.vehicle = _cstr(head[_VEHICLE_OFF:_VEHICLE_OFF + 64])
        self.venue = _cstr(head[_VENUE_OFF:_VENUE_OFF + 64])
        self.channels: List[dict] = []
        self.truncated = False
        self._read_channels()
        if not self.channels:
            raise _err("fmt_ld_no_channels")

    def _read_channels(self):
        ptr, seen = self.meta_ptr, set()
        with open(self.path, "rb") as f:
            while ptr and len(self.channels) < MAX_CHANNELS:
                if ptr in seen or ptr + CHAN_META_SIZE > self.size:
                    self.truncated = True
                    break
                seen.add(ptr)
                f.seek(ptr)
                raw = f.read(CHAN_META_SIZE)
                prev, nxt, dptr, n, _cnt, dtype_a, dtype, freq, shift, mul, scale, dec = \
                    struct.unpack_from("<IIIIHHHHhhhh", raw, 0)
                self.channels.append({
                    "name": _cstr(raw[32:64]), "short": _cstr(raw[64:72]), "unit": _cstr(raw[72:84]),
                    "data_ptr": dptr, "n": n, "dtype_a": dtype_a, "dtype": dtype, "freq": freq,
                    "shift": shift, "mul": mul, "scale": scale, "dec": dec,
                })
                ptr = nxt

    def metadata(self) -> dict:
        return {"driver": self.driver or None, "vehicle": self.vehicle or None,
                "venue": self.venue or None, "date": self.date or None, "time": self.time or None,
                "format": "ld", "experimental": True}


def _np_dtype(ch: dict):
    if ch["dtype_a"] == 7:
        return {2: "<f2", 4: "<f4"}.get(ch["dtype"])
    return {2: "<i2", 4: "<i4"}.get(ch["dtype"])


def read_ld_metadata(path: str) -> dict:
    try:
        return LdFile(path).metadata()
    except Exception:
        return {"driver": None, "vehicle": None, "venue": None}


def load_ld(path: str):
    ld = LdFile(path)
    mm = np.memmap(path, dtype=np.uint8, mode="r")
    truncated_channels = 0

    def make_reader(ch, dt):
        size = np.dtype(dt).itemsize
        is_float = ch["dtype_a"] == 7

        def read() -> np.ndarray:
            raw = np.frombuffer(mm, dtype=dt, count=ch["n"], offset=ch["data_ptr"]).astype(np.float64)
            if is_float:
                return raw
            scale = ch["scale"] or 1
            return (raw / scale * 10.0 ** (-ch["dec"]) + ch["shift"]) * (ch["mul"] or 1)
        return read, size

    available: Dict[str, List[RawChannel]] = {}
    for ch in ld.channels:
        dt = _np_dtype(ch)
        if dt is None or ch["freq"] <= 0 or ch["n"] <= 1:
            continue
        reader, size = make_reader(ch, dt)
        if ch["data_ptr"] <= 0 or ch["data_ptr"] + ch["n"] * size > ld.size:
            truncated_channels += 1
            continue
        available.setdefault(ch["name"], []).append(
            RawChannel(ch["name"], ch["unit"], float(ch["freq"]), ch["n"], reader))
    if truncated_channels and not available:
        raise _err("fmt_ld_truncated")
    if truncated_channels:
        logger.warning("Archivo .ld truncado: %d canales omitidos", truncated_channels)

    chosen = pick_channels(available)
    if truncated_channels and "Speed" not in chosen:
        raise _err("fmt_ld_truncated")
    df = build_frame(chosen, fmt="ld", available_names=sorted(available), metadata=ld.metadata())
    del mm
    if truncated_channels or ld.truncated:
        df.attrs["warnings"] = ["ld_truncated"]
    return df
