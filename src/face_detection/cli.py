"""Command-line interface: local detection, webcam demo, API-key generation, model verification."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

import anyio
import cv2

from face_detection.annotate import draw_faces
from face_detection.config import DEFAULT_MODEL_SHA256, Settings, hash_api_key
from face_detection.detector import ModelIntegrityError, YuNetDetector, sha256_file
from face_detection.errors import AppError
from face_detection.imaging import validate_and_decode
from face_detection.schemas import FaceOut
from face_detection.storage import ObjectStore

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray


def _detector(model: Path | None, score: float | None) -> YuNetDetector:
    s = Settings(environment="dev")
    return YuNetDetector(
        model or s.model_path,
        expected_sha256=s.model_sha256,
        score_threshold=score if score is not None else s.score_threshold,
        nms_threshold=s.nms_threshold,
        max_faces=s.max_faces,
        max_side=s.inference_max_side,
    )


def _cmd_detect(args: argparse.Namespace) -> int:
    settings = Settings(environment="dev")
    try:
        image = validate_and_decode(args.image.read_bytes(), max_pixels=settings.max_image_pixels)
    except OSError as exc:
        print(f"error: cannot read {args.image}: {exc}", file=sys.stderr)
        return 2
    except AppError as exc:
        print(f"error: {exc.detail}", file=sys.stderr)
        return 2
    faces = _detector(args.model, args.score).detect(image)
    payload = {
        "image": {"width": image.shape[1], "height": image.shape[0]},
        "faces": [FaceOut.from_face(f).model_dump() for f in faces],
    }
    if args.output and not cv2.imwrite(str(args.output), draw_faces(image, faces)):
        print(f"error: could not write {args.output}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2 if sys.stdout.isatty() else None))
    return 0


def _cmd_webcam(args: argparse.Namespace) -> int:
    detector = _detector(args.model, args.score)
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"error: cannot open camera {args.camera}", file=sys.stderr)
        return 2
    try:
        while True:
            ok, raw = cap.read()
            if not ok:
                break
            frame = cast("NDArray[np.uint8]", raw)
            cv2.imshow("face-detection (q to quit)", draw_faces(frame, detector.detect(frame)))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except cv2.error as exc:
        print(
            "error: this OpenCV build has no GUI support (headless). For the webcam demo run:\n"
            "  uv pip uninstall opencv-python-headless && uv pip install opencv-python\n"
            f"({exc})",
            file=sys.stderr,
        )
        return 2
    finally:
        cap.release()
        cv2.destroyAllWindows()
    return 0


def _cmd_keygen(_: argparse.Namespace) -> int:
    key = secrets.token_urlsafe(32)
    print(f"API key (give to the client, shown once): {key}")
    print(f"FD_API_KEY_HASHES entry (put on the server):  {hash_api_key(key)}")
    return 0


def _cmd_init_storage(args: argparse.Namespace) -> int:
    settings = Settings(environment="dev")
    store = ObjectStore(settings)
    try:
        notes = anyio.run(lambda: store.ensure_bucket(expire_days=args.expire_days, region=settings.s3_region))
    except AppError as exc:
        print(f"error: {exc.detail}", file=sys.stderr)
        return 1
    for note in notes:
        print(f"warning: {note}", file=sys.stderr)
    print(f"bucket {settings.s3_bucket!r} ready (inputs/ expire after {args.expire_days} day(s))")
    return 0


def _cmd_verify_model(args: argparse.Namespace) -> int:
    path = args.model or Settings(environment="dev").model_path
    try:
        actual = sha256_file(path)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    ok = actual == DEFAULT_MODEL_SHA256
    print(f"{path}: sha256={actual} {'OK' if ok else 'MISMATCH (expected ' + DEFAULT_MODEL_SHA256 + ')'}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="face-detection", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    det = sub.add_parser("detect", help="detect faces in an image file and print JSON")
    det.add_argument("image", type=Path)
    det.add_argument("-o", "--output", type=Path, help="write an annotated copy here")
    det.add_argument("--model", type=Path)
    det.add_argument("--score", type=float, help="score threshold override (0-1)")
    det.set_defaults(func=_cmd_detect)

    cam = sub.add_parser("webcam", help="live webcam demo (requires GUI-enabled OpenCV)")
    cam.add_argument("--camera", type=int, default=0)
    cam.add_argument("--model", type=Path)
    cam.add_argument("--score", type=float)
    cam.set_defaults(func=_cmd_webcam)

    sub.add_parser("keygen", help="generate an API key and its SHA-256 hash").set_defaults(func=_cmd_keygen)

    ini = sub.add_parser("init-storage", help="create the S3 bucket and its input-expiry lifecycle rule")
    ini.add_argument("--expire-days", type=int, default=1)
    ini.set_defaults(func=_cmd_init_storage)

    ver = sub.add_parser("verify-model", help="check the model file against the pinned checksum")
    ver.add_argument("--model", type=Path)
    ver.set_defaults(func=_cmd_verify_model)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ModelIntegrityError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
