"""biblioteca de sesiones

Revision ID: 0001
Revises:
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotente: si la tabla ya existe (p. ej. creada por create_all) no hace nada.
    if sa.inspect(op.get_bind()).has_table("library_sessions"):
        return
    op.create_table(
        "library_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("sim", sa.String(80)),
        sa.Column("vehicle", sa.String(160)),
        sa.Column("venue", sa.String(160)),
        sa.Column("driver", sa.String(160)),
        sa.Column("best_lap_s", sa.Float()),
        sa.Column("n_laps", sa.Integer()),
        sa.Column("source_filename", sa.String(260)),
        sa.Column("file_sha256", sa.String(64)),
        sa.Column("notes", sa.Text()),
        sa.Column("owner_id", sa.String(64)),
        sa.Column("payload", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    )
    op.create_index("ix_library_sessions_dedupe", "library_sessions", ["file_sha256", "venue"])
    op.create_index("ix_library_sessions_venue_vehicle", "library_sessions", ["venue", "vehicle"])
    op.create_index("ix_library_sessions_created_at", "library_sessions", ["created_at"])


def downgrade() -> None:
    op.drop_table("library_sessions")
