"""Repair the dead-letter timestamp schema used by persistence and replay."""

from alembic import op
import sqlalchemy as sa


revision = "20260914_repair_dead_letter_created_at"
down_revision = "20260914_add_ground_truth_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "dead_letters" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("dead_letters")}
    if "created_at" not in columns:
        op.add_column(
            "dead_letters",
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.execute(
            sa.text(
                "UPDATE dead_letters SET created_at = COALESCE(received_at, CURRENT_TIMESTAMP) "
                "WHERE created_at IS NULL"
            )
        )

    indexes = {index["name"] for index in inspector.get_indexes("dead_letters")}
    if "ix_dead_letters_created" not in indexes:
        op.create_index(
            "ix_dead_letters_created",
            "dead_letters",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "dead_letters" not in inspector.get_table_names():
        return
    indexes = {index["name"] for index in inspector.get_indexes("dead_letters")}
    if "ix_dead_letters_created" in indexes:
        op.drop_index("ix_dead_letters_created", table_name="dead_letters")
    columns = {column["name"] for column in inspector.get_columns("dead_letters")}
    if "created_at" in columns:
        op.drop_column("dead_letters", "created_at")
