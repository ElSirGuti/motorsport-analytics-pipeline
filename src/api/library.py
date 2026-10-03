"""Biblioteca de sesiones: guardar, listar, abrir, renombrar, borrar y comparar.

Se incluye desde main.py con una linea (``app.include_router(library_router)``).
Funciona igual con SQLite (desarrollo/tests) y PostgreSQL (contenedores).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, defer

from src.analytics.session_compare import compare_sessions, compatibility, norm_key, racing_laps
from src.db import LibrarySession, get_db
from src.i18n import _l

router = APIRouter(prefix="/api/library", tags=["library"])

MAX_PAYLOAD_BYTES = 5 * 1024 * 1024
MAX_SNIFF_BYTES = 256 * 1024
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


# ── Utilidades ────────────────────────────────────────────────────────────────
def _lang(request: Request) -> str:
    lang = request.query_params.get("lang", "")
    if lang in ("es", "en"):
        return lang
    return "es" if request.headers.get("accept-language", "").lower().startswith("es") else "en"


def _err(request: Request, status: int, key: str, **kw) -> HTTPException:
    return HTTPException(status_code=status, detail=_l(_lang(request), key, **kw))


def _clean(obj: Any) -> Any:
    """Sustituye NaN/Inf por None (no son JSON valido y JSONB los rechaza)."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    return obj


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _blank(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _circuit_of(venue: Optional[str]) -> Optional[dict]:
    """Canonical circuit (id + name) for a venue string, or None if unknown."""
    from src.analytics.circuits import find_circuit
    c = find_circuit(venue)
    return {"id": c["id"], "name": c["name"], "country": c.get("country")} if c else None


def summary(row: LibrarySession) -> dict:
    return {
        "circuit": _circuit_of(row.venue),
        "id": str(row.id),
        "created_at": _aware(row.created_at).isoformat() if row.created_at else None,
        "updated_at": _aware(row.updated_at).isoformat() if row.updated_at else None,
        "title": row.title,
        "sim": row.sim,
        "vehicle": row.vehicle,
        "venue": row.venue,
        "driver": row.driver,
        "best_lap_s": row.best_lap_s,
        "n_laps": row.n_laps,
        "source_filename": row.source_filename,
        "file_sha256": row.file_sha256,
        "notes": row.notes,
    }


def _derive_stats(payload: dict) -> tuple[Optional[float], Optional[int]]:
    sess = payload.get("session") or {}
    stint = payload.get("stint") or {}
    best = None
    fl = sess.get("fastest_lap") or {}
    try:
        best = float(fl.get("lap_time")) if fl.get("lap_time") else None
    except (TypeError, ValueError):
        best = None
    if best is None:
        times = [l["time"] for l in racing_laps(payload)]
        best = min(times) if times else None
    n = sess.get("total_laps") or stint.get("n_laps") or len(sess.get("laps") or []) or None
    return best, (int(n) if n else None)


def _fingerprint(payload: dict) -> str:
    """Huella del contenido cuando el cliente no envia el SHA-256 del CSV."""
    core = {"laps": (payload.get("session") or {}).get("laps"), "stint": (payload.get("stint") or {}).get("laps")}
    return hashlib.sha256(json.dumps(core, sort_keys=True, default=str).encode("utf-8")).hexdigest()


# ── Esquemas ──────────────────────────────────────────────────────────────────
class LibraryPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session: Optional[dict[str, Any]] = None
    stint: Optional[dict[str, Any]] = None
    extras: dict[str, Any] = Field(default_factory=dict)


class SaveRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: Optional[str] = Field(default=None, max_length=200)
    sim: Optional[str] = Field(default=None, max_length=80)
    vehicle: Optional[str] = Field(default=None, max_length=160)
    venue: Optional[str] = Field(default=None, max_length=160)
    driver: Optional[str] = Field(default=None, max_length=160)
    source_filename: Optional[str] = Field(default=None, max_length=260)
    file_sha256: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=5000)
    payload: LibraryPayload

    @field_validator("file_sha256")
    @classmethod
    def _sha(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, ""):
            return None
        if not _HEX64.match(v):
            raise ValueError("file_sha256 must be 64 hex characters")
        return v.lower()


class PatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=5000)
    venue: Optional[str] = Field(default=None, max_length=160)
    vehicle: Optional[str] = Field(default=None, max_length=160)
    driver: Optional[str] = Field(default=None, max_length=160)


class CompareRequest(BaseModel):
    a: uuid.UUID
    b: uuid.UUID
    force: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("")
async def save_session(request: Request, db: Session = Depends(get_db)):
    """Guarda (o actualiza si ya existe el mismo CSV en el mismo circuito) una sesion analizada."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_PAYLOAD_BYTES:
        raise _err(request, 413, "lib_err_payload_too_large", mb=MAX_PAYLOAD_BYTES // (1024 * 1024))
    raw = await request.body()
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise _err(request, 413, "lib_err_payload_too_large", mb=MAX_PAYLOAD_BYTES // (1024 * 1024))
    try:
        body = SaveRequest.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json(include_url=False, include_context=False)))

    payload = _clean(body.payload.model_dump())
    if not payload.get("session") and not payload.get("stint"):
        raise _err(request, 422, "lib_err_empty_payload")

    best, n_laps = _derive_stats(payload)
    venue, vehicle = _blank(body.venue), _blank(body.vehicle)
    sha = body.file_sha256 or _fingerprint(payload)
    title = _blank(body.title) or _blank(body.source_filename) or _l(_lang(request), "lib_default_title")

    q = select(LibrarySession).where(LibrarySession.file_sha256 == sha)
    q = q.where(LibrarySession.venue.is_(None) if venue is None else LibrarySession.venue == venue)
    row = db.scalars(q.limit(1)).first()

    status = "updated"
    if row is None:
        status = "created"
        row = LibrarySession(title=title[:200], file_sha256=sha, venue=venue, payload=payload)
        db.add(row)
    row.payload = payload
    row.best_lap_s, row.n_laps = best, n_laps
    row.vehicle = vehicle or row.vehicle
    row.driver = _blank(body.driver) or row.driver
    row.sim = _blank(body.sim) or row.sim
    row.source_filename = _blank(body.source_filename) or row.source_filename
    if status == "created":
        row.notes = _blank(body.notes)
    elif _blank(body.notes):
        row.notes = _blank(body.notes)
    db.commit()
    db.refresh(row)
    return {"status": status, "duplicate": status == "updated", "session": summary(row)}


@router.get("")
def list_sessions(
    q: Optional[str] = Query(None, max_length=200),
    venue: Optional[str] = None,
    vehicle: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    circuit: Optional[str] = Query(None, max_length=80, description="Id canonico de circuito (circuits.json)"),
    db: Session = Depends(get_db),
):
    """Lista paginada y filtrable, sin el payload pesado."""
    cond = []
    if circuit:
        # all stored venue strings that resolve to this canonical circuit (aliases included)
        venues = [v for (v,) in db.execute(select(LibrarySession.venue).where(LibrarySession.venue.is_not(None)).distinct()).all()
                  if (_circuit_of(v) or {}).get("id") == circuit]
        cond.append(LibrarySession.venue.in_(venues) if venues else LibrarySession.id.is_(None))
    if q and q.strip():
        pat = _like(q.strip().lower())
        cond.append(or_(*[
            func.lower(func.coalesce(col, "")).like(pat, escape="\\")
            for col in (LibrarySession.title, LibrarySession.venue, LibrarySession.vehicle,
                        LibrarySession.driver, LibrarySession.source_filename, LibrarySession.notes)
        ]))
    if venue:
        cond.append(func.lower(LibrarySession.venue) == norm_key(venue))
    if vehicle:
        cond.append(func.lower(LibrarySession.vehicle) == norm_key(vehicle))
    if date_from:
        cond.append(LibrarySession.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        cond.append(LibrarySession.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))

    total = db.scalar(select(func.count()).select_from(LibrarySession).where(*cond)) or 0
    rows = db.scalars(
        select(LibrarySession).where(*cond).options(defer(LibrarySession.payload))
        .order_by(LibrarySession.created_at.desc(), LibrarySession.id).limit(limit).offset(offset)
    ).all()
    return {"items": [summary(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/facets")
def facets(db: Session = Depends(get_db)):
    """Circuitos y coches disponibles (con recuento) y combinaciones circuito+coche."""
    def counts(col):
        return [{"value": v, "count": c} for v, c in db.execute(
            select(col, func.count()).where(col.is_not(None)).group_by(col).order_by(col)).all()]

    combos = db.execute(
        select(LibrarySession.venue, LibrarySession.vehicle, func.count())
        .group_by(LibrarySession.venue, LibrarySession.vehicle)
    ).all()
    by_circuit: dict = {}
    for v, _veh, n in combos:
        c = _circuit_of(v)
        if c:
            e = by_circuit.setdefault(c["id"], {**c, "count": 0})
            e["count"] += n
    return {
        "circuits": sorted(by_circuit.values(), key=lambda e: e["name"]),
        "venues": counts(LibrarySession.venue),
        "vehicles": counts(LibrarySession.vehicle),
        "combos": [{"venue": v, "vehicle": c, "count": n} for v, c, n in combos],
    }


@router.post("/sniff")
async def sniff_metadata(head: UploadFile = File(..., description="Primeros KB del CSV")):
    """Lee circuito/coche/piloto de la cabecera MoTeC de un CSV (solo se envian los primeros KB)."""
    from src.io.loaders import read_motec_metadata

    data = await head.read(MAX_SNIFF_BYTES + 1)
    data = data[:MAX_SNIFF_BYTES]
    fd, path = tempfile.mkstemp(suffix=".csv", prefix="sniff_")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        meta = read_motec_metadata(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    return {
        "venue": _pretty(meta.get("venue")),
        "vehicle": _pretty(meta.get("vehicle")),
        "driver": meta.get("driver"),
        "raw": meta,
    }


def _pretty(value: Optional[str]) -> Optional[str]:
    """'ks_porsche_cayman_gt4_clubsport' -> 'Porsche Cayman GT4 Clubsport'."""
    if not value:
        return None
    s = re.sub(r"^(ks|fn|acc|rf2)_", "", value.strip(), flags=re.I)
    if "_" not in s and " " in s:
        return s
    words = []
    for w in s.replace("_", " ").split():
        words.append(w.upper() if re.search(r"\d", w) and len(w) <= 4 else w.capitalize())
    return " ".join(words) or None


@router.post("/compare")
def compare(body: CompareRequest, request: Request, db: Session = Depends(get_db)):
    lang = _lang(request)
    if body.a == body.b:
        raise _err(request, 400, "lib_err_same_session")
    ra, rb = db.get(LibrarySession, body.a), db.get(LibrarySession, body.b)
    if ra is None or rb is None:
        raise _err(request, 404, "lib_err_not_found")

    info = {"venue": ra.venue, "vehicle": ra.vehicle}, {"venue": rb.venue, "vehicle": rb.vehicle}
    compat = compatibility(*info)
    if not compat["compatible"] and not body.force:
        fields = ", ".join(_l(lang, f"lib_field_{f}") for f in compat["mismatch"])
        raise HTTPException(status_code=400, detail=_l(lang, "lib_err_incompatible", fields=fields))

    result = compare_sessions(ra.payload or {}, rb.payload or {}, lang=lang)
    warnings = []
    if compat["unknown"]:
        warnings.append(_l(lang, "lib_warn_unknown", fields=", ".join(_l(lang, f"lib_field_{f}") for f in compat["unknown"])))
    result.update({
        "a": summary(ra), "b": summary(rb),
        "compatibility": compat, "forced": bool(body.force and not compat["compatible"]),
        "warnings": warnings,
    })
    return result


def _get_or_404(request: Request, db: Session, sid: uuid.UUID) -> LibrarySession:
    row = db.get(LibrarySession, sid)
    if row is None:
        raise _err(request, 404, "lib_err_not_found")
    return row


@router.get("/{session_id}")
def get_session(session_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    row = _get_or_404(request, db, session_id)
    return {**summary(row), "payload": row.payload}


@router.patch("/{session_id}")
def patch_session(session_id: uuid.UUID, body: PatchRequest, request: Request, db: Session = Depends(get_db)):
    row = _get_or_404(request, db, session_id)
    for field in body.model_fields_set:
        value = getattr(body, field)
        if field == "title":
            value = _blank(value)
            if not value:
                raise HTTPException(status_code=422, detail="title must not be blank")
        else:
            value = _blank(value)
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return summary(row)


@router.delete("/{session_id}")
def delete_session(session_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    row = _get_or_404(request, db, session_id)
    db.delete(row)
    db.commit()
    return {"status": "deleted", "id": str(session_id)}
