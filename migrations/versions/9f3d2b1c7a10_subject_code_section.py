"""subject_code_section

Revision ID: 9f3d2b1c7a10
Revises: abc251fbb595
Create Date: 2026-04-20 18:10:00.000000

"""
from datetime import datetime
import re

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f3d2b1c7a10"
down_revision = "abc251fbb595"
branch_labels = None
depends_on = None


def _slug3(text: str) -> str:
    letters = re.sub(r"[^A-Za-z]", "", text or "").upper()
    if len(letters) >= 3:
        return letters[:3]
    return (letters + "XXX")[:3]


def upgrade():
    with op.batch_alter_table("subjects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("section", sa.String(length=1), nullable=True))
        batch_op.add_column(sa.Column("code", sa.String(length=20), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, name, created_at FROM subjects ORDER BY id ASC")
    ).fetchall()

    # In SQLite, uniqueness on subjects.name may live as an index.
    if bind.dialect.name == "sqlite":
        indexes = bind.execute(sa.text("PRAGMA index_list('subjects')")).fetchall()
        for idx in indexes:
            idx_name = idx[1]
            is_unique = idx[2]
            if not is_unique:
                continue
            cols = bind.execute(sa.text(f"PRAGMA index_info('{idx_name}')")).fetchall()
            col_names = [c[2] for c in cols]
            if col_names == ["name"]:
                bind.execute(sa.text(f'DROP INDEX IF EXISTS "{idx_name}"'))

    seen_codes = set()
    for row in rows:
        year = datetime.now().year
        if row.created_at is not None:
            try:
                year = row.created_at.year
            except Exception:
                year = datetime.now().year
        base = f"{_slug3(row.name)}{year}"
        code = base
        n = 1
        while code in seen_codes:
            n += 1
            code = f"{base}-{n}"
        seen_codes.add(code)
        bind.execute(
            sa.text("UPDATE subjects SET section = :section, code = :code WHERE id = :id"),
            {"section": "A", "code": code, "id": row.id},
        )

    with op.batch_alter_table("subjects", schema=None) as batch_op:
        batch_op.alter_column("name", existing_type=sa.String(length=120), nullable=False)
        batch_op.create_unique_constraint("uq_subjects_code", ["code"])
        batch_op.alter_column("section", existing_type=sa.String(length=1), nullable=False)
        batch_op.alter_column("code", existing_type=sa.String(length=20), nullable=False)


def downgrade():
    with op.batch_alter_table("subjects", schema=None) as batch_op:
        batch_op.drop_constraint("uq_subjects_code", type_="unique")
        batch_op.drop_column("code")
        batch_op.drop_column("section")
