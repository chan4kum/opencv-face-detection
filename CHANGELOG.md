# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/), versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Fixed
- Worker classified every `AppError` as permanent, so an object-store outage would have failed jobs instead of retrying them. Classification is now by status: 4xx permanent, 5xx transient (regression test added).
- The bug-report issue form was invalid YAML and would have been rejected by GitHub.

## [1.0.0]

### Changed
- Rebuilt from a Haar-cascade webcam script into a production-grade service.

### Added
- YuNet face detector (ONNX Runtime) with landmarks, checksum-pinned model, OpenCV-parity tests.
- FastAPI service: `/v1/detect`, `/v1/detect/annotated`, async `/v1/jobs`, health/readiness/metrics, RFC 9457 errors.
- NATS JetStream worker pipeline with S3-compatible storage, retries, idempotency and graceful shutdown.
- API-key auth (hashed), request limits, load shedding, security headers.
- Prometheus metrics, OpenTelemetry tracing (API to worker), structured logs, Grafana dashboard, alert rules.
- Docker image (non-root, read-only rootfs), Docker Compose stack, Helm chart (HPA/KEDA/PDB/NetworkPolicy), CI/CD, docs.
- CLI: `detect`, `webcam`, `keygen`, `verify-model`, `init-storage`.
