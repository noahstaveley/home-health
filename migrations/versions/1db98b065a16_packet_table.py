"""packet table

Revision ID: 1db98b065a16
Revises: 57820ddd21ce
Create Date: 2022-02-12 01:35:45.118500

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1db98b065a16'
down_revision = '57820ddd21ce'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('packet', sa.Column('packet_count_store', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_packet_packet_count_store'), 'packet', ['packet_count_store'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_packet_packet_count_store'), table_name='packet')
    op.drop_column('packet', 'packet_count_store')
    # ### end Alembic commands ###
