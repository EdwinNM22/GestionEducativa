"""subject_image_path

Revision ID: 6c4e8a2d1f11
Revises: 9f3d2b1c7a10
Create Date: 2026-04-21 04:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6c4e8a2d1f11"
down_revision = "9f3d2b1c7a10"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("subjects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("image_path", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("subjects", schema=None) as batch_op:
        batch_op.drop_column("image_path")
