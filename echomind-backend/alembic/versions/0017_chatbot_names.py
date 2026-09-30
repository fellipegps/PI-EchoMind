"""Rename the public FAQ and chat voice fields for the web chatbot.

Revision ID: 0017
Revises: 0016
"""

from alembic import op
import sqlalchemy as sa


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_faqs_show_on_totem", table_name="faqs")
    op.alter_column(
        "faqs",
        "show_on_totem",
        new_column_name="show_in_chatbot",
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    op.create_index("ix_faqs_show_in_chatbot", "faqs", ["show_in_chatbot"])
    op.alter_column(
        "config",
        "totem_voice_gender",
        new_column_name="chat_voice_gender",
        existing_type=sa.String(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "config",
        "chat_voice_gender",
        new_column_name="totem_voice_gender",
        existing_type=sa.String(),
        existing_nullable=True,
    )
    op.drop_index("ix_faqs_show_in_chatbot", table_name="faqs")
    op.alter_column(
        "faqs",
        "show_in_chatbot",
        new_column_name="show_on_totem",
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    op.create_index("ix_faqs_show_on_totem", "faqs", ["show_on_totem"])
