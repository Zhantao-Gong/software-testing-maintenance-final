#!/usr/bin/env python3
import argparse
import csv
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone


METRICS = {
    "recommendationservice_cpu": 'sum(rate(container_cpu_usage_seconds_total{namespace="${OB_NS}",pod=~"recommendationservice-.*",cpu="total"}[1m]))',
    "frontend_cpu": 'sum(rate(container_cpu_usage_seconds_total{namespace="${OB_NS}",pod=~"frontend-.*",cpu="total"}[1m]))',
    "cartservice_cpu": 'sum(rate(container_cpu_usage_seconds_total{namespace="${OB_NS}",pod=~"cartservice-.*",cpu="total"}[1m]))',
    "recommendationservice_memory": 'sum(container_memory_working_set_bytes{namespace="${OB_NS}",pod=~"recommendationservice-.*"})',
    "frontend_memory": 'sum(container_memory_working_set_bytes{namespace="${OB_NS}",pod=~"frontend-.*"})',
    "cartservice_memory": 'sum(container_memory_working_set_bytes{namespace="${OB_NS}",pod=~"cartservice-.*"})',
    "cartservice_pod_ready": 'sum(kube_pod_status_ready{namespace="${OB_NS}",pod=~"cartservice-.*",condition="true"})',
    "frontend_pod_ready": 'sum(kube_pod_status_ready{namespace="${OB_NS}",pod=~"frontend-.*",condition="true"})',
    "recommendationservice_pod_ready": 'sum(kube_pod_status_ready{namespace="${OB_NS}",pod=~"recommendationservice-.*",condition="true"})',
    "cartservice_restarts": 'sum(kube_pod_container_status_restarts_total{namespace="${OB_NS}",pod=~"cartservice-.*"})',
    "cartservice_available_replicas": 'kube_deployment_status_replicas_available{namespace="${OB_NS}",deployment="cartservice"}',
}

OPTIONAL_METRICS = {
    "frontend_qps": 'sum(rate(istio_requests_total{destination_workload_namespace="${OB_NS}",destination_workload="frontend"}[1m]))',
    "frontend_5xx_rate": 'sum(rate(istio_requests_total{destination_workload_namespace="${OB_NS}",destination_workload="frontend",response_code=~"5.."}[1m])) / clamp_min(sum(rate(istio_requests_total{destination_workload_namespace="${OB_NS}",destination_workload="frontend"}[1m])), 1e-9)',
    "frontend_p95_latency": 'histogram_quantile(0.95, sum(rate(istio_request_duration_milliseconds_bucket{destination_workload_namespace="${OB_NS}",destination_workload="frontend"}[1m])) by (le))',
}

APP_METRICS = {
    "frontend_qps": 'sum(rate(microservices_demo_user_request_count[1m]))',
    "frontend_avg_latency_ms": 'sum(rate(microservices_demo_user_request_latency_microseconds_sum[1m])) / clamp_min(sum(rate(microservices_demo_user_request_latency_microseconds_count[1m])), 1e-9) / 1000',
}


def parse_time(value):
    if value.isdigit():
        return int(value)
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def request_json(url, params=None, timeout=30):
    full_url = url
    if params:
        full_url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(full_url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def query_range(base_url, query, start, end, step):
    data = request_json(
        base_url.rstrip("/") + "/api/v1/query_range",
        {"query": query, "start": start, "end": end, "step": f"{step}s"},
        timeout=60,
    )
    if data.get("status") != "success":
        raise RuntimeError(data)
    return data["data"]["result"]


def pick_values(result):
    if not result:
        return {}
    if len(result) == 1:
        return {int(float(ts)): float(value) for ts, value in result[0].get("values", [])}
    combined = {}
    for series in result:
        for ts, value in series.get("values", []):
            ts_int = int(float(ts))
            combined[ts_int] = combined.get(ts_int, 0.0) + float(value)
    return combined


def write_series(path, series_id, values, start, end, step):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_iso", "timestamp_unix", "series_id", "value", "missing"])
        for ts in range(start, end + 1, step):
            value = values.get(ts)
            missing = 1 if value is None or math.isnan(value) else 0
            writer.writerow([iso(ts), ts, series_id, "NaN" if missing else value, missing])


def metric_exists(base_url, metric_name):
    try:
        result = request_json(base_url.rstrip() + "/api/v1/series", {"match[]": metric_name, "start": int(time.time()) - 3600, "end": int(time.time())})
        return result.get("status") == "success" and bool(result.get("data"))
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Export Prometheus metrics to 5s CSV grids.")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--out-dir", default="fluxev_data/raw/prometheus")
    parser.add_argument("--include-optional", action="store_true")
    args = parser.parse_args()

    start = parse_time(args.start)
    end = parse_time(args.end)
    metrics = dict(METRICS)
    if metric_exists(args.prometheus_url, "microservices_demo_user_request_latency_microseconds_count"):
        metrics.update(APP_METRICS)
    if args.include_optional or metric_exists(args.prometheus_url, "istio_requests_total"):
        metrics.update(OPTIONAL_METRICS)

    failures = []
    for series_id, template in metrics.items():
        query = template.replace("${OB_NS}", args.namespace)
        try:
            values = pick_values(query_range(args.prometheus_url, query, start, end, args.step))
            write_series(os.path.join(args.out_dir, f"{series_id}.csv"), series_id, values, start, end, args.step)
            print(f"exported {series_id}: {len(values)} raw points")
        except Exception as exc:
            failures.append((series_id, str(exc)))
            write_series(os.path.join(args.out_dir, f"{series_id}.csv"), series_id, {}, start, end, args.step)
            print(f"warning: failed to export {series_id}: {exc}", file=sys.stderr)

    if failures:
        os.makedirs("fluxev_data/metadata", exist_ok=True)
        with open("fluxev_data/metadata/prometheus_export_failures.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["series_id", "error"])
            writer.writerows(failures)


if __name__ == "__main__":
    main()
