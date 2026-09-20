"""Public API models (also the source of the generated OpenAPI document)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from face_detection.detector import Face
from face_detection.jobs import JobStatus


class Box(BaseModel):
    x: float = Field(description="Left edge in pixels of the (EXIF-upright) image")
    y: float = Field(description="Top edge in pixels")
    width: float
    height: float


class Point(BaseModel):
    x: float
    y: float


class Landmarks(BaseModel):
    right_eye: Point
    left_eye: Point
    nose: Point
    right_mouth: Point
    left_mouth: Point


class FaceOut(BaseModel):
    box: Box
    score: float = Field(ge=0, le=1, description="Detection confidence")
    landmarks: Landmarks

    @classmethod
    def from_face(cls, face: Face) -> FaceOut:
        re, le, nose, rm, lm = (Point(x=x, y=y) for x, y in face.landmarks)
        return cls(
            box=Box(x=face.x, y=face.y, width=face.width, height=face.height),
            score=face.score,
            landmarks=Landmarks(right_eye=re, left_eye=le, nose=nose, right_mouth=rm, left_mouth=lm),
        )


class ImageInfo(BaseModel):
    width: int
    height: int


class ModelInfo(BaseModel):
    name: str
    sha256: str
    execution_providers: list[str]


class DetectResult(BaseModel):
    image: ImageInfo
    faces: list[FaceOut]
    inference_ms: float = Field(description="Server-side detection time (excludes network and queueing)")
    model: ModelInfo


class DetectResponse(DetectResult):
    request_id: str


class JobAccepted(BaseModel):
    job_id: str
    status: JobStatus
    status_url: str


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: float
    updated_at: float
    attempts: int
    result: DetectResult | None = None
    error: str | None = None


class ProblemDetails(BaseModel):
    """RFC 9457 problem document."""

    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    request_id: str | None = None
    errors: list[dict[str, Any]] | None = None


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, bool] = Field(default_factory=dict)
    version: str | None = None
