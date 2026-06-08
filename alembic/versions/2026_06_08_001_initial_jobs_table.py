"""Initial jobs table schema

Revision ID: 001
Revises: None
Create Date: 2026-06-08 05:45:00+00:00

Implements the `jobs` table as defined in the Implementation Document (Section 5).
This is the foundational schema for tracking render job lifecycle.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the job_status enum type
    job_status_enum = postgresql.ENUM(
        "queued", "downloading", "rendering", "completed", "failed",
        name="job_status",
        create_type=True,
    )
    job_status_enum.create(op.get_bind(), checkfirst=True)

    # Create the jobs table
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"),
                  comment="Unique job identifier (UUIDv4)."),
        sa.Column("status", job_status_enum, nullable=False,
                  server_default="queued",
                  comment="Current lifecycle state of the render job."),
        sa.Column("progress", sa.Float(), nullable=True, default=0.0,
                  comment="Rendering progress percentage (0.0 - 100.0)."),

        # Inputs
        sa.Column("replay_storage_key", sa.String(512), nullable=False,
                  comment="Object storage key for the uploaded .osr replay file."),
        sa.Column("config", postgresql.JSONB(), nullable=False,
                  server_default="{}",
                  comment="Rendering configuration (skin, resolution, bg_dim, etc.)."),

        # Metadata (populated during processing)
        sa.Column("beatmap_id", sa.Integer(), nullable=True,
                  comment="osu! beatmap ID resolved from the replay hash."),
        sa.Column("map_title", sa.String(512), nullable=True,
                  comment="Human-readable beatmap title."),

        # Outputs
        sa.Column("video_storage_key", sa.String(512), nullable=True,
                  comment="Object storage key for the rendered .mp4 video."),
        sa.Column("thumb_storage_key", sa.String(512), nullable=True,
                  comment="Object storage key for the generated thumbnail."),
        sa.Column("error_message", sa.Text(), nullable=True,
                  comment="Detailed error message if the job failed."),

        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  comment="Timestamp when the job was submitted."),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  comment="Timestamp of the last status update."),
    )

    # Performance indexes
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_created_at", "jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_jobs_created_at", table_name="jobs")
    op.drop_index("idx_jobs_status", table_name="jobs")
    op.drop_table("jobs")

    # Drop the enum type
    job_status_enum = postgresql.ENUM(name="job_status")
    job_status_enum.drop(op.get_bind(), checkfirst=True)
