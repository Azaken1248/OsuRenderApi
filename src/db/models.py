import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
class Base(DeclarativeBase):
    pass
class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", create_type=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    progress: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )
    replay_storage_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    beatmap_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    map_title: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    client_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        index=True,
    )
    video_storage_key: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    thumb_storage_key: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    __table_args__ = (
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_created_at", "created_at"),
    )
    def __repr__(self) -> str:
        return f"<Job id={self.id} status={self.status.value} progress={self.progress}%>"