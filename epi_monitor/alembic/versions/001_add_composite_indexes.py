"""Add composite SQL indexes to eventos table

Revision ID: 001_add_composite_indexes
Revises: 
Create Date: 2026-07-24

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_add_composite_indexes'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('idx_evento_data_tipo', 'eventos', ['data_hora', 'tipo_evento'], unique=False)
    op.create_index('idx_evento_camera_tipo_data', 'eventos', ['camera_id', 'tipo_evento', 'data_hora'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_evento_camera_tipo_data', table_name='eventos')
    op.drop_index('idx_evento_data_tipo', table_name='eventos')
