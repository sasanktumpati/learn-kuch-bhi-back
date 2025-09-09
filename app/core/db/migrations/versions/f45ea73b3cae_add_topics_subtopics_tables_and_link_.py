"""add topics/subtopics tables and link flashcard sets

Revision ID: f45ea73b3cae
Revises: 52533e1e5b14
Create Date: 2025-09-09 18:46:17.254147

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f45ea73b3cae"
down_revision: Union[str, Sequence[str], None] = "52533e1e5b14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with data backfill for topics/subtopics and set links."""
    bind = op.get_bind()
    # 1) Create new normalized tables
    op.create_table(
        "fc_topics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("multi_result_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["multi_result_id"],
            ["multi_flashcards_results.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_fc_topics_created_at"), "fc_topics", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_fc_topics_id"), "fc_topics", ["id"], unique=False)
    op.create_index(
        op.f("ix_fc_topics_multi_result_id"),
        "fc_topics",
        ["multi_result_id"],
        unique=False,
    )
    op.create_table(
        "fc_subtopics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["fc_topics.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_fc_subtopics_created_at"), "fc_subtopics", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_fc_subtopics_id"), "fc_subtopics", ["id"], unique=False)
    op.create_index(
        op.f("ix_fc_subtopics_topic_id"), "fc_subtopics", ["topic_id"], unique=False
    )
    # 2) Add FK column to flashcard_sets (keep old name columns temporarily)
    op.add_column(
        "flashcard_sets", sa.Column("subtopic_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_flashcard_sets_subtopic_id"),
        "flashcard_sets",
        ["subtopic_id"],
        unique=False,
    )
    op.create_foreign_key(
        "flashcard_sets_subtopic_id_fkey",
        "flashcard_sets",
        "fc_subtopics",
        ["subtopic_id"],
        ["id"],
    )

    # 3) Backfill topics and subtopics from existing flashcard_sets name columns
    conn = bind
    mids = conn.execute(
        sa.text(
            "SELECT DISTINCT multi_result_id FROM flashcard_sets WHERE multi_result_id IS NOT NULL"
        )
    ).fetchall()
    for (m_id,) in mids:
        # Create topics by distinct topic_name values
        topics = conn.execute(
            sa.text(
                "SELECT DISTINCT topic_name FROM flashcard_sets "
                "WHERE multi_result_id = :mid AND topic_name IS NOT NULL ORDER BY topic_name"
            ),
            dict(mid=m_id),
        ).fetchall()
        topic_id_map: dict[str, int] = {}
        for t_idx, (t_name,) in enumerate(topics):
            topic_row = conn.execute(
                sa.text(
                    "INSERT INTO fc_topics (multi_result_id, name, description, order_index) "
                    "VALUES (:mid, :name, :desc, :ord) RETURNING id"
                ),
                dict(mid=m_id, name=t_name, desc=None, ord=t_idx),
            ).first()
            topic_id = topic_row[0]
            topic_id_map[t_name] = topic_id

            # Create subtopics under this topic from distinct subtopic_name
            subs = conn.execute(
                sa.text(
                    "SELECT DISTINCT subtopic_name FROM flashcard_sets "
                    "WHERE multi_result_id = :mid AND topic_name = :tname AND subtopic_name IS NOT NULL "
                    "ORDER BY subtopic_name"
                ),
                dict(mid=m_id, tname=t_name),
            ).fetchall()
            for s_idx, (s_name,) in enumerate(subs):
                sub_row = conn.execute(
                    sa.text(
                        "INSERT INTO fc_subtopics (topic_id, name, description, order_index) "
                        "VALUES (:tid, :name, :desc, :ord) RETURNING id"
                    ),
                    dict(tid=topic_id, name=s_name, desc=None, ord=s_idx),
                ).first()
                sub_id = sub_row[0]
                # Link sets
                conn.execute(
                    sa.text(
                        "UPDATE flashcard_sets SET subtopic_id = :sid "
                        "WHERE multi_result_id = :mid AND topic_name = :tname AND subtopic_name = :sname"
                    ),
                    dict(sid=sub_id, mid=m_id, tname=t_name, sname=s_name),
                )

    # 4) Drop old unique constraint and name columns
    op.drop_constraint(
        op.f("uq_set_multi_topic_subtopic"), "flashcard_sets", type_="unique"
    )
    op.drop_column("flashcard_sets", "topic_name")
    op.drop_column("flashcard_sets", "subtopic_name")
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "flashcard_sets",
        sa.Column("subtopic_name", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "flashcard_sets",
        sa.Column("topic_name", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.drop_constraint(None, "flashcard_sets", type_="foreignkey")
    op.drop_index(op.f("ix_flashcard_sets_subtopic_id"), table_name="flashcard_sets")
    op.create_unique_constraint(
        op.f("uq_set_multi_topic_subtopic"),
        "flashcard_sets",
        ["multi_result_id", "topic_name", "subtopic_name"],
        postgresql_nulls_not_distinct=False,
    )
    op.drop_column("flashcard_sets", "subtopic_id")
    op.drop_index(op.f("ix_fc_subtopics_topic_id"), table_name="fc_subtopics")
    op.drop_index(op.f("ix_fc_subtopics_id"), table_name="fc_subtopics")
    op.drop_index(op.f("ix_fc_subtopics_created_at"), table_name="fc_subtopics")
    op.drop_table("fc_subtopics")
    op.drop_index(op.f("ix_fc_topics_multi_result_id"), table_name="fc_topics")
    op.drop_index(op.f("ix_fc_topics_id"), table_name="fc_topics")
    op.drop_index(op.f("ix_fc_topics_created_at"), table_name="fc_topics")
    op.drop_table("fc_topics")
    # ### end Alembic commands ###
