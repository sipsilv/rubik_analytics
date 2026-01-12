"""add telegram messages table

Revision ID: 001_telegram_messages
Revises: 
Create Date: 2026-01-12 21:20:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_telegram_messages'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'telegram_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.String(), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('from_user', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('admin_username', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index(op.f('ix_telegram_messages_id'), 'telegram_messages', ['id'], unique=False)
    op.create_index(op.f('ix_telegram_messages_user_id'), 'telegram_messages', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_telegram_messages_user_id'), table_name='telegram_messages')
    op.drop_index(op.f('ix_telegram_messages_id'), table_name='telegram_messages')
    op.drop_table('telegram_messages')
