"""Add scoped, auditable dead-letter replay state."""

from alembic import op
import sqlalchemy as sa


revision = "20260913_harden_dead_letter_replay"
down_revision = "20260912_convert_money_to_numeric"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("dead_letters")}
    additions = {
        "replay_status": sa.Column("replay_status", sa.String(), nullable=False, server_default="idle"),
        "replayed_by": sa.Column("replayed_by", sa.String(), nullable=True),
        "replayed_at": sa.Column("replayed_at", sa.DateTime(timezone=True), nullable=True),
        "replay_reason": sa.Column("replay_reason", sa.Text(), nullable=True),
        "provider_account_id": sa.Column("provider_account_id", sa.String(), nullable=True),
        "event_key": sa.Column("event_key", sa.String(), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("dead_letters", column)
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("dead_letters")}
    if "ix_dead_letters_event_key" not in indexes:
        op.create_index("ix_dead_letters_event_key", "dead_letters", ["event_key"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("dead_letters")}
    if "ix_dead_letters_event_key" in indexes:
        op.drop_index("ix_dead_letters_event_key", table_name="dead_letters")
    for name in ("event_key", "provider_account_id", "replay_reason", "replayed_at", "replayed_by", "replay_status"):
        op.drop_column("dead_letters", name)