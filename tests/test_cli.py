from __future__ import annotations

import json
from pathlib import Path

import pytest

from face_detection.cli import main
from face_detection.config import hash_api_key
from tests.conftest import DATA, MODEL


def test_detect_prints_json_and_writes_annotated_image(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out.jpg"
    assert main(["detect", str(DATA / "two_faces.jpg"), "-o", str(out), "--model", str(MODEL)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["faces"]) == 2 and out.stat().st_size > 1000


def test_detect_missing_file_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["detect", "/no/such/file.jpg", "--model", str(MODEL)]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_detect_invalid_image_exit_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"garbage")
    assert main(["detect", str(bad), "--model", str(MODEL)]) == 2


def test_detect_unwritable_output_fails_cleanly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["detect", str(DATA / "astronaut.jpg"), "-o", str(tmp_path / "nodir" / "x.jpg"), "--model", str(MODEL)])
    assert rc == 2 and "could not write" in capsys.readouterr().err


def test_keygen_hash_matches_key(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["keygen"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    key, digest = lines[0].split()[-1], lines[1].split()[-1]
    assert hash_api_key(key) == digest and len(key) >= 40


def test_verify_model(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["verify-model", "--model", str(MODEL)]) == 0
    tampered = tmp_path / "m.onnx"
    tampered.write_bytes(MODEL.read_bytes() + b"\x00")
    assert main(["verify-model", "--model", str(tampered)]) == 1
    assert "MISMATCH" in capsys.readouterr().out
    assert main(["verify-model", "--model", str(tmp_path / "missing")]) == 2


def test_tampered_model_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tampered = tmp_path / "m.onnx"
    tampered.write_bytes(MODEL.read_bytes() + b"\x00")
    assert main(["detect", str(DATA / "astronaut.jpg"), "--model", str(tampered)]) == 3
    assert "checksum mismatch" in capsys.readouterr().err


class TestInitStorage:
    def test_creates_bucket_and_lifecycle(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import boto3
        from moto import mock_aws

        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "t")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "t")
        monkeypatch.setenv("FD_S3_BUCKET", "cli-bucket")
        with mock_aws():
            assert main(["init-storage", "--expire-days", "3"]) == 0
            rules = boto3.client("s3", region_name="us-east-1").get_bucket_lifecycle_configuration(Bucket="cli-bucket")
            assert rules["Rules"][0]["Expiration"]["Days"] == 3
        assert "cli-bucket" in capsys.readouterr().out

    def test_unreachable_storage_exits_nonzero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("FD_S3_ENDPOINT_URL", "http://127.0.0.1:1")
        monkeypatch.setenv("FD_S3_ACCESS_KEY_ID", "a")
        monkeypatch.setenv("FD_S3_SECRET_ACCESS_KEY", "b")
        assert main(["init-storage"]) == 1
        assert "storage request failed" in capsys.readouterr().err


class TestWebcam:
    """Uses a fake camera so no real device (or macOS camera-permission prompt) is involved."""

    def test_camera_unavailable(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        import cv2

        class Closed:
            def __init__(self, *_: object) -> None: ...
            def isOpened(self) -> bool:
                return False

            def release(self) -> None: ...

        monkeypatch.setattr(cv2, "VideoCapture", Closed)
        assert main(["webcam", "--model", str(MODEL)]) == 2
        assert "cannot open camera" in capsys.readouterr().err

    def test_stream_end_is_clean_exit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import cv2
        import numpy as np

        frames = [np.zeros((64, 64, 3), np.uint8)]
        shown: list[object] = []

        class Cam:
            def __init__(self, *_: object) -> None: ...
            def isOpened(self) -> bool:
                return True

            def read(self) -> tuple[bool, object]:
                return (True, frames.pop()) if frames else (False, None)

            def release(self) -> None: ...

        monkeypatch.setattr(cv2, "VideoCapture", Cam)
        monkeypatch.setattr(cv2, "imshow", lambda *_: shown.append(1))
        monkeypatch.setattr(cv2, "waitKey", lambda *_: 0)
        monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
        assert main(["webcam", "--model", str(MODEL)]) == 0 and shown == [1]

    def test_headless_opencv_gives_actionable_error(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import cv2
        import numpy as np

        class Cam:
            def __init__(self, *_: object) -> None: ...
            def isOpened(self) -> bool:
                return True

            def read(self) -> tuple[bool, object]:
                return True, np.zeros((64, 64, 3), np.uint8)

            def release(self) -> None: ...

        def no_gui(*_: object) -> None:
            raise cv2.error("The function is not implemented (imshow)")

        monkeypatch.setattr(cv2, "VideoCapture", Cam)
        monkeypatch.setattr(cv2, "imshow", no_gui)
        monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
        assert main(["webcam", "--model", str(MODEL)]) == 2
        assert "opencv-python-headless" in capsys.readouterr().err
