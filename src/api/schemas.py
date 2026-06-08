import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
class RenderConfig(BaseModel):
    skin: str = Field(
        default="Default",
        max_length=128,
        description="Selected skin name for rendering.",
        examples=["Default", "Rafis HDDT", "WhiteCat 1.0"],
    )
    bg_dim: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Background dim percentage (0.0 = no dim, 1.0 = full dim).",
    )
    resolution: str = Field(
        default="1080p",
        description="Output video resolution.",
        examples=["1080p", "4k"],
    )
    motion_blur: bool = Field(
        default=True,
        description="Enable motion blur in the render.",
    )
    storyboard: bool = Field(
        default=True,
        description="Load beatmap storyboard during render.",
    )
    video: bool = Field(
        default=False,
        description="Load beatmap background video during render.",
    )
    snaking_in: bool = Field(
        default=True,
        description="Enable slider snaking-in animation.",
    )
    snaking_out: bool = Field(
        default=True,
        description="Enable slider snaking-out animation.",
    )
    hit_error_meter: bool = Field(
        default=True,
        description="Show hit error meter overlay.",
    )
    key_overlay: bool = Field(
        default=True,
        description="Show key press overlay.",
    )
    @field_validator("bg_dim", mode="before")
    @classmethod
    def normalize_bg_dim(cls, v):
        if isinstance(v, (int, float)) and v > 1.0:
            return v / 100.0
        return v
    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, v):
        allowed = {"1080p", "4k"}
        if v not in allowed:
            raise ValueError(f"Resolution must be one of: {allowed}")
        return v
class JobCreatedResponse(BaseModel):
    job_id: uuid.UUID
    status: str = "queued"
    links: dict = Field(
        description="HATEOAS-style links for the client to follow.",
    )
    model_config = {"json_schema_extra": {
        "example": {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "queued",
            "links": {
                "status": "/v1/jobs/550e8400-e29b-41d4-a716-446655440000",
            },
        }
    }}
class ArtifactLinks(BaseModel):
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
class JobStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    progress: float = 0.0
    map_title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    config: dict = {}
    artifacts: ArtifactLinks = ArtifactLinks()
    model_config = {"from_attributes": True}
class JobListResponse(BaseModel):
    total: int
    jobs: list[JobStatusResponse]