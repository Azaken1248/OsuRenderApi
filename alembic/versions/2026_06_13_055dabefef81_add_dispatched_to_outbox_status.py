"""add DISPATCHED to outbox_status

Revision ID: 055dabefef81
Revises: e5e9b8371bcd
Create Date: 2026-06-13 17:49:29.583936+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '055dabefef81'
down_revision: Union[str, None] = 'e5e9b8371bcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE cannot run inside a transaction block
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE outbox_status ADD VALUE IF NOT EXISTS 'DISPATCHED'")


def downgrade() -> None:
    pass
