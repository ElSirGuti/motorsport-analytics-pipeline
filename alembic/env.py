"""Entorno de Alembic. La URL sale de DATABASE_URL (mismo contrato que la API)."""
from alembic import context

from src.db.models import Base
from src.db.session import get_database_url, make_engine, normalize_url

target_metadata = Base.metadata


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(url=normalize_url(get_database_url()), target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Si la API paso una conexion abierta (arranque automatico) se reutiliza.
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = make_engine()
    with engine.connect() as conn:
        _run(conn)
        conn.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
