"""add pharmacy type column

Revision ID: 20240618_add_pharmacy_type
Revises: 
Create Date: 2026-06-18 17:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20240618_add_pharmacy_type'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add type column to pharmacies."""
    op.add_column('pharmacies', 
        sa.Column('type', sa.String(20), nullable=False, 
                  server_default='customer',
                  comment='Pharmacy type: development, demo, customer'))
    
    # Add check constraint for valid types
    op.create_check_constraint(
        'ck_pharmacies_type',
        'pharmacies',
        "type IN ('development', 'demo', 'customer')"
    )


def downgrade() -> None:
    """Downgrade schema - remove type column from pharmacies."""
    op.drop_constraint('ck_pharmacies_type', 'pharmacies', type_='check')
    op.drop_column('pharmacies', 'type')
