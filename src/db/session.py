"""Engine, sesiones y arranque de la base de datos.

Variables de entorno (contrato compartido):
  DATABASE_URL  por defecto ``sqlite:///data/motorsport.db`` (relativo al repo);
                en contenedores ``postgresql+psycopg://user:pass@host:5432/db``.
  STORAGE_DIR   por defecto ``./data/storage`` (CSV originales, opcional).

El mismo codigo sirve para SQLite y PostgreSQL. ``psycopg`` solo hace falta con
PostgreSQL y SQLAlchemy lo importa de forma perezosa al crear el engine.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.models import Base

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = "sqlite:///data/motorsport.db"

_lock = threading.Lock()
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None
_initialized = False


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip() or DEFAULT_DATABASE_URL


def get_storage_dir() -> Path:
    raw = os.getenv("STORAGE_DIR", "").strip() or "./data/storage"
    p = Path(raw)
    return p if p.is_absolute() else REPO_ROOT / p


def normalize_url(url: str) -> str:
    """SQLite relativo -> relativo al repo (no al cwd); ``postgresql://`` -> psycopg 3."""
    u = make_url(url)
    if u.drivername == "sqlite" and u.database and u.database != ":memory:":
        db_path = Path(u.database)
        if not db_path.is_absolute():
            db_path = REPO_ROOT / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        u = u.set(database=str(db_path))
    elif u.drivername in ("postgres", "postgresql"):
        u = u.set(drivername="postgresql+psycopg")
    return u.render_as_string(hide_password=False)


def make_engine(url: Optional[str] = None) -> Engine:
    url = normalize_url(url or get_database_url())
    kwargs: dict = {"pool_pre_ping": True}
    parsed = make_url(url)
    if parsed.drivername.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if parsed.database in (None, "", ":memory:"):
            kwargs["poolclass"] = StaticPool  # una unica conexion: la BD en memoria persiste
    return create_engine(url, **kwargs)


def get_engine() -> Engine:
    global _engine, _SessionLocal
    with _lock:
        if _engine is None:
            _engine = make_engine()
            _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
        return _engine


def reset_engine(engine: Optional[Engine] = None) -> None:
    """Sustituye el engine global (tests). ``None`` lo descarta."""
    global _engine, _SessionLocal, _initialized
    with _lock:
        if _engine is not None and _engine is not engine:
            _engine.dispose()
        _engine = engine
        _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False) if engine else None
        _initialized = False


def _run_migrations(engine: Engine) -> bool:
    """Aplica ``alembic upgrade head``. Devuelve False si Alembic no esta disponible."""
    ini = REPO_ROOT / "alembic.ini"
    if not ini.exists():
        return False
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError:
        return False
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    return True


def init_db(engine: Optional[Engine] = None, use_migrations: bool = True) -> None:
    """Crea/actualiza el esquema. Idempotente y seguro de llamar en cada arranque.

    Con Alembic disponible aplica las migraciones (``upgrade head``); si no, o si
    falla, recurre a ``create_all`` (que solo crea lo que falta).
    """
    engine = engine or get_engine()
    migrated = False
    if use_migrations:
        try:
            migrated = _run_migrations(engine)
        except Exception as exc:  # pragma: no cover - ruta defensiva
            logger.warning("Alembic upgrade fallo (%s); usando create_all", exc)
    if not migrated:
        Base.metadata.create_all(engine)
    logger.info("Biblioteca lista (%s, tablas: %s)", engine.url.render_as_string(hide_password=True),
                inspect(engine).get_table_names())


def ensure_initialized() -> None:
    """Inicializacion perezosa y unica por proceso (primera peticion a la biblioteca)."""
    global _initialized
    if _initialized:
        return
    engine = get_engine()
    with _lock:
        if _initialized:
            return
        init_db(engine)
        _initialized = True


def get_db() -> Iterator[Session]:
    """Dependencia FastAPI: una sesion SQLAlchemy por peticion."""
    ensure_initialized()
    assert _SessionLocal is not None
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
