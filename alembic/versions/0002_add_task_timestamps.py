"""Add and backfill task timestamps.

Revision ID: 0002_add_task_timestamps
Revises: 0001_create_tasks_table
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_task_timestamps"
down_revision = "0001_create_tasks_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows need nullable columns until their values are backfilled.
    op.add_column("tasks", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    # Old rows did not have historical timestamps, so the migration time is used.
    op.execute(
        """
        UPDATE tasks
        SET created_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE created_at IS NULL OR updated_at IS NULL
        """
    )

    # Future rows must always provide timestamps.
    op.alter_column("tasks", "created_at", nullable=False)
    op.alter_column("tasks", "updated_at", nullable=False)


def downgrade() -> None:
    op.drop_column("tasks", "updated_at")
    op.drop_column("tasks", "created_at")
