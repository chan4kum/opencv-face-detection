"""Generate the Grafana dashboard JSON (kept as code so panels stay reviewable)."""

import json
import sys

DS = {"type": "prometheus", "uid": "prometheus"}


def panel(
    pid: int,
    title: str,
    exprs: list[tuple[str, str]],
    x: int,
    y: int,
    unit: str = "short",
    w: int = 12,
    h: int = 8,
    desc: str = "",
) -> dict:
    return {
        "id": pid,
        "type": "timeseries",
        "title": title,
        "description": desc,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {"defaults": {"unit": unit, "custom": {"lineWidth": 2, "fillOpacity": 8}}, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}},
        "targets": [
            {"refId": chr(65 + i), "datasource": DS, "expr": e, "legendFormat": legend}
            for i, (e, legend) in enumerate(exprs)
        ],
    }


def q(p: float, metric: str, by: str = "", extra: str = "") -> str:
    return f"histogram_quantile({p}, sum by (le{by}) (rate({metric}_bucket{extra}[$__rate_interval])))"


panels = [
    panel(
        1,
        "Request rate by route",
        [
            (
                'sum by (route) (rate(fd_http_requests_total{route!~"/healthz|/readyz|/metrics"}[$__rate_interval]))',
                "{{route}}",
            )
        ],
        0,
        0,
        "reqps",
    ),
    panel(
        2,
        "Error ratio (5xx)",
        [
            (
                'sum(rate(fd_http_requests_total{status=~"5.."}[$__rate_interval])) / clamp_min(sum(rate(fd_http_requests_total[$__rate_interval])), 1e-9)',
                "5xx ratio",
            )
        ],
        12,
        0,
        "percentunit",
    ),
    panel(
        3,
        "Latency: /v1/detect",
        [
            (q(0.5, "fd_http_request_duration_seconds", extra='{route="/v1/detect"}'), "p50"),
            (q(0.95, "fd_http_request_duration_seconds", extra='{route="/v1/detect"}'), "p95"),
            (q(0.99, "fd_http_request_duration_seconds", extra='{route="/v1/detect"}'), "p99"),
        ],
        0,
        8,
        "s",
    ),
    panel(
        4,
        "Model inference latency",
        [
            (q(0.5, "fd_inference_duration_seconds", ",source"), "p50 {{source}}"),
            (q(0.95, "fd_inference_duration_seconds", ",source"), "p95 {{source}}"),
        ],
        12,
        8,
        "s",
    ),
    panel(
        5,
        "In-flight HTTP requests / worker jobs",
        [
            ("sum(fd_http_requests_in_flight)", "http in flight"),
            ("sum(fd_worker_jobs_in_flight)", "worker jobs in flight"),
        ],
        0,
        16,
    ),
    panel(
        6,
        "Load shedding & rejected inputs",
        [
            ("sum by (reason) (rate(fd_inference_rejected_total[$__rate_interval]))", "shed: {{reason}}"),
            ("sum by (reason) (rate(fd_images_rejected_total[$__rate_interval]))", "rejected: {{reason}}"),
        ],
        12,
        16,
        "ops",
    ),
    panel(
        7,
        "Async jobs by outcome",
        [
            ("sum by (outcome) (rate(fd_jobs_processed_total[$__rate_interval]))", "{{outcome}}"),
            ("sum(rate(fd_jobs_submitted_total[$__rate_interval]))", "submitted"),
        ],
        0,
        24,
        "ops",
    ),
    panel(
        8,
        "Job end-to-end latency (submit to done)",
        [(q(0.5, "fd_job_end_to_end_seconds"), "p50"), (q(0.95, "fd_job_end_to_end_seconds"), "p95")],
        12,
        24,
        "s",
    ),
    panel(
        9,
        "Queue depth (pending jobs)",
        [
            ('max(nats_consumer_num_pending{consumer_name="fd-workers"})', "pending"),
            ('max(nats_consumer_num_ack_pending{consumer_name="fd-workers"})', "ack pending"),
        ],
        0,
        32,
        desc="Requires the NATS Prometheus exporter.",
    ),
    panel(
        10,
        "Faces per image (p50 / p95)",
        [(q(0.5, "fd_faces_per_image"), "p50"), (q(0.95, "fd_faces_per_image"), "p95")],
        12,
        32,
    ),
]
dash = {
    "uid": "face-detection",
    "title": "Face Detection Service",
    "schemaVersion": 39,
    "version": 1,
    "editable": True,
    "refresh": "10s",
    "time": {"from": "now-1h", "to": "now"},
    "tags": ["face-detection"],
    "panels": panels,
}
json.dump(dash, sys.stdout, indent=2)
print()
