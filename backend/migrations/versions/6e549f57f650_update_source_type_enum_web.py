"""update_source_type_enum_web

Revision ID: 6e549f57f650
Revises: c87867dfd10a
Create Date: 2025-10-15 23:55:37.057723

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6e549f57f650'
down_revision = 'c87867dfd10a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update the enum to change WEBSITE to WEB
    op.execute("ALTER TYPE sourcetype RENAME VALUE 'WEBSITE' TO 'WEB';")


def downgrade() -> None:
    # Revert the enum change
    op.execute("ALTER TYPE sourcetype RENAME VALUE 'WEB' TO 'WEBSITE';")

