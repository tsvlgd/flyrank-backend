"""Create the original PostgreSQL tasks table.

Revision ID: 0001_create_tasks_table
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_create_tasks_table"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tasks")
