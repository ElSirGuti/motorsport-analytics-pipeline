"""Session header metadata (circuit / car / driver / date / session type) for CSV, .ibt and .ld.

Light module (no reportlab / matplotlib) shared by the PDF report, ``/api/library/sniff`` and
``/api/setups/detect``. Everything here is best-effort and never raises: unknown or unreadable
files simply yield fewer fields.

Normalised keys (all optional): ``venue``, ``vehicle``, ``driver``, ``log_date``, ``log_time``,
``date_iso`` (YYYY-MM-DD), ``session_type``, ``format`` (``csv`` | ``ibt`` | ``ld``), ``file``.
"""
from __future__ import annotations

import csv
import logging
import os
import re
import tempfile
from datetime import date
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Bytes that are enough to read the header of any supported format (the .ibt YAML sits after the
# variable table, ~40 KB in + ~25-95 KB long in real iRacing files).
HEADER_SNIFF_BYTES = 256 * 1024

_CSV_KEYS = {"venue": "venue", "vehicle": "vehicle", "driver": "driver", "log date": "log_date",
             "log time": "log_time", "session": "session_type", "comment": "comment"}
# iRacing / Acti file names embed the local recording time: "... 2026-06-09 21-10-09 ..."
_FILENAME_DT = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ _T](\d{2})-(\d{2})-(\d{2})")


def parse_log_date(raw: Any, time_raw: Any = None) -> Optional[date]:
    """
    Parse the 'Log Date' of a MoTeC header.

    Ambiguous day/month orders are resolved with the unambiguous cases first (a part > 12),
    then with the clock format: Spanish 'a. m.' / 'p. m.' markers (and 24 h clocks) come from
    day-first locales, English 'AM'/'PM' from month-first ones.
    """
    if not raw:
        return None
    s = str(raw).strip()
    m = re.fullmatch(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", s)
    try:
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", s)
        if not m:
            return None
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12:
            return date(y, b, a)
        if b > 12:
            return date(y, a, b)
        tr = str(time_raw or "").lower()
        day_first = bool(re.search(r"a\.\s?m\.|p\.\s?m\.", tr)) or not re.search(r"\b(am|pm)\b", tr)
        return date(y, b, a) if day_first else date(y, a, b)
    except ValueError:
        return None


def _csv_header(path: str) -> dict:
    out: dict = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
            for i, row in enumerate(csv.reader(f)):
                if i >= 20:
                    break
                for j in range(0, len(row) - 1):
                    k = row[j].strip().lower()
                    if k in _CSV_KEYS and row[j + 1].strip() and _CSV_KEYS[k] not in out:
                        out[_CSV_KEYS[k]] = row[j + 1].strip()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("csv header: %s", exc)
    return out


def _native_header(path: str, fmt: str) -> dict:
    """Map the metadata the native loaders already extract to the normalised keys."""
    from src.io.native_common import read_native_metadata
    meta = read_native_metadata(path, fmt) or {}
    out: dict = {"format": fmt}
    for k in ("venue", "vehicle", "driver", "session_type"):
        if meta.get(k):
            out[k] = str(meta[k]).strip()
    if fmt == "ld":
        if meta.get("date"):
            out["log_date"] = str(meta["date"])
        if meta.get("time"):
            out["log_time"] = str(meta["time"])
    elif meta.get("date"):
        out["date_iso"] = str(meta["date"])
    return out


def _date_from_filename(name: Optional[str]) -> Optional[date]:
    m = _FILENAME_DT.search(name or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def read_header(path: str, filename: Optional[str] = None) -> dict:
    """Header metadata of a file on disk (CSV, .ibt or .ld; format detected from the signature)."""
    out: dict = {}
    try:
        from src.io.native_common import detect_format
        fmt = detect_format(path)
        if fmt in ("ibt", "ld"):
            out = _native_header(path, fmt)
        else:
            out = _csv_header(path)
            out["format"] = "csv"
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("read_header: %s", exc)
    d = parse_log_date(out.get("log_date"), out.get("log_time"))
    if out.get("format") in ("ibt", "ld"):
        # the recording time inside the file is UTC; the file name carries the local date
        d = _date_from_filename(filename) or _date_from_filename(os.path.basename(path)) or d \
            or (date.fromisoformat(out["date_iso"]) if out.get("date_iso") else None)
    if d:
        out["date_iso"] = d.isoformat()
    if filename:
        out["file"] = filename
    return out


def read_header_bytes(data: bytes, filename: Optional[str] = None) -> dict:
    """Same as :func:`read_header` for the first bytes of a file (uploads sent head-only)."""
    from src.io.native_common import sniff_bytes
    data = data[:HEADER_SNIFF_BYTES]
    fmt = sniff_bytes(data[:144]) or "csv"
    if fmt == "ld":
        return _ld_header_from_head(data, filename)
    fd, path = tempfile.mkstemp(suffix=".bin", prefix="hdr_")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return read_header(path, filename)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _ld_header_from_head(data: bytes, filename: Optional[str]) -> dict:
    """A truncated .ld cannot be opened as a whole; its fixed header is enough."""
    from src.io.ld_loader import _DATE_OFF, _DRIVER_OFF, _TIME_OFF, _VEHICLE_OFF, _VENUE_OFF, _cstr
    out: dict = {"format": "ld"}
    try:
        for key, off, ln in (("log_date", _DATE_OFF, 16), ("log_time", _TIME_OFF, 16), ("driver", _DRIVER_OFF, 64),
                             ("vehicle", _VEHICLE_OFF, 64), ("venue", _VENUE_OFF, 64)):
            v = _cstr(data[off:off + ln])
            if v:
                out[key] = v
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("ld head: %s", exc)
    d = _date_from_filename(filename) or parse_log_date(out.get("log_date"), out.get("log_time"))
    if d:
        out["date_iso"] = d.isoformat()
    if filename:
        out["file"] = filename
    return out
