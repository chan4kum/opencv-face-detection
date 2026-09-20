"""Inference service shared by the HTTP API and the queue workers."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import anyio
import numpy as np

from face_detection.detector import Face, YuNetDetector
from face_detection.errors import AppError, OverloadedError
from face_detection.imaging import validate_and_decode
from face_detection.metrics import FACES_PER_IMAGE, IMAGES_REJECTED, INFERENCE_DURATION, INFERENCE_REJECTED
from face_detection.schemas import DetectResult, FaceOut, ImageInfo, ModelInfo
from face_detection.telemetry import get_tracer

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from face_detection.config import Settings

MODEL_NAME = "yunet-2026may"


class InferenceService:
    """Bounded-concurrency wrapper: validate -> decode -> detect, off the event loop."""

    def __init__(self, detector: YuNetDetector, settings: Settings) -> None:
        self._detector = detector
        self._settings = settings
        self._slots = asyncio.Semaphore(settings.max_concurrent_inference)
        self._model = ModelInfo(
            name=MODEL_NAME, sha256=settings.model_sha256, execution_providers=list(detector.providers)
        )

    @property
    def model(self) -> ModelInfo:
        return self._model

    async def detect_bytes(self, data: bytes, *, source: str) -> tuple[DetectResult, NDArray[np.uint8], list[Face]]:
        """Validate and run detection. Sheds load (503) instead of queueing without bound."""
        try:
            await asyncio.wait_for(self._slots.acquire(), timeout=self._settings.inference_queue_timeout_s)
        except TimeoutError:
            INFERENCE_REJECTED.labels(reason="queue_timeout").inc()
            raise OverloadedError("inference capacity exhausted, retry shortly", headers={"Retry-After": "1"}) from None
        try:
            with get_tracer().start_as_current_span("detect") as span:
                try:
                    image, faces, elapsed = await anyio.to_thread.run_sync(self._process, data)
                except AppError as exc:
                    IMAGES_REJECTED.labels(reason=exc.code).inc()
                    raise
                span.set_attribute("faces.count", len(faces))
                span.set_attribute("image.width", image.shape[1])
                span.set_attribute("image.height", image.shape[0])
        finally:
            self._slots.release()

        INFERENCE_DURATION.labels(source=source).observe(elapsed)
        FACES_PER_IMAGE.observe(len(faces))
        result = DetectResult(
            image=ImageInfo(width=image.shape[1], height=image.shape[0]),
            faces=[FaceOut.from_face(f) for f in faces],
            inference_ms=round(elapsed * 1000, 3),
            model=self._model,
        )
        return result, image, faces

    def _process(self, data: bytes) -> tuple[NDArray[np.uint8], list[Face], float]:
        image = validate_and_decode(data, max_pixels=self._settings.max_image_pixels)
        start = time.perf_counter()
        faces = self._detector.detect(image)
        return image, faces, time.perf_counter() - start
