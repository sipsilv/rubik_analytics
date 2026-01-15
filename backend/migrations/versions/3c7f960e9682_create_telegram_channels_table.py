"""create telegram channels table

Revision ID: 3c7f960e9682
Revises: 3c7f960e9681
Create Date: 2026-01-14 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c7f960e9682'
down_revision = '3c7f960e9681'
branch_labels = None
depends_on = None


def upgrade():
    # Check if table exists to avoid errors in dev environments where it might get out of sync
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'telegram_channels' not in tables:
        op.create_table(
            'telegram_channels',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('connection_id', sa.Integer(), nullable=False),
            sa.Column('channel_id', sa.BigInteger(), nullable=False),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('username', sa.String(), nullable=True),
            sa.Column('type', sa.String(), nullable=False),
            sa.Column('member_count', sa.Integer(), nullable=True),
            sa.Column('is_enabled', sa.Boolean(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['connection_id'], ['connections.id'], )
        )
        op.create_index(op.f('ix_telegram_channels_id'), 'telegram_channels', ['id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_telegram_channels_id'), table_name='telegram_channels')
    op.drop_table('telegram_channels')
