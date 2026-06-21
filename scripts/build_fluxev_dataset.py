#!/usr/bin/env python3
import argparse
import csv
import math
import os
from datetime import datetime, timezone


PRIMARY_MAP = {
    ("cpu_stress", "recommendationservice_cpu"),
    ("network_delay", "frontend_p95_latency"),
    ("network_delay", "frontend_avg_latency_ms"),
    ("network_delay", "frontend_probe_latency_ms"),
    ("pod_kill", "cartservice_restarts"),
    ("pod_kill", "cartservice_pod_ready"),
    ("pod_kill", "cartservice_available_replicas"),
}


CATALOG = [
    ("recommendationservice_cpu", "prometheus", "recommendationservice", "cpu", "cores", 1, "primary for CPU stress"),
    ("frontend_probe_latency_ms", "probe", "frontend", "latency", "ms", 1, "primary for network delay if no Prometheus latency"),
    ("frontend_probe_error_rate", "probe", "frontend", "error_rate", "ratio", 0, "probe errors"),
    ("frontend_p95_latency", "prometheus", "frontend", "latency", "ms", 1, "primary for network delay if available"),
    ("frontend_avg_latency_ms", "prometheus", "frontend", "latency", "ms", 1, "application average latency if available"),
    ("cartservice_restarts", "prometheus", "cartservice", "restarts", "count", 1, "primary for pod kill"),
    ("cartservice_pod_ready", "prometheus", "cartservice", "pod_ready", "count", 1, "primary for pod kill"),
    ("cartservice_available_replicas", "prometheus", "cartservice", "available_replicas", "count", 1, "primary for pod kill"),
    ("frontend_cpu", "prometheus", "frontend", "cpu", "cores", 0, "secondary"),
    ("cartservice_cpu", "prometheus", "cartservice", "cpu", "cores", 0, "secondary"),
    ("recommendationservice_memory", "prometheus", "recommendationservice", "memory", "bytes", 0, "secondary"),
    ("frontend_memory", "prometheus", "frontend", "memory", "bytes", 0, "secondary"),
    ("cartservice_memory", "prometheus", "cartservice", "memory", "bytes", 0, "secondary"),
    ("frontend_pod_ready", "prometheus", "frontend", "pod_ready", "count", 0, "secondary"),
    ("recommendationservice_pod_ready", "prometheus", "recommendationservice", "pod_ready", "count", 0, "secondary"),
]


def parse_iso(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def read_windows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["label_start_unix"] = parse_iso(row["label_start_iso"])
        row["label_end_unix"] = parse_iso(row["label_end_iso"])
    return rows


def fault_for(series_id, ts, windows):
    for row in windows:
        if (row["fault_type"], series_id) in PRIMARY_MAP and row["label_start_unix"] <= ts <= row["label_end_unix"]:
            return 1, row["fault_type"], row["fault_id"]
    return 0, "normal", ""


def read_series_files(raw_dir):
    files = []
    prom_dir = os.path.join(raw_dir, "prometheus")
    probe_file = os.path.join(raw_dir, "probe", "frontend_probe.csv")
    if os.path.isdir(prom_dir):
        files.extend(os.path.join(prom_dir, name) for name in os.listdir(prom_dir) if name.endswith(".csv"))
    if os.path.exists(probe_file):
        files.append(probe_file)
    return sorted(files)


def nearest_grid_ts(ts, start, end, step):
    offset = round((ts - start) / step) * step
    snapped = start + offset
    if snapped < start or snapped > end:
        return None
    return snapped


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def write_metadata(out_dir):
    metadata_dir = os.path.join(out_dir, "metadata")
    os.makedirs(metadata_dir, exist_ok=True)
    with open(os.path.join(metadata_dir, "series_catalog.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["series_id", "source", "service", "metric", "unit", "primary_eval", "notes"])
        writer.writerows(CATALOG)
    with open(os.path.join(metadata_dir, "series_fault_map.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fault_type", "target_service", "series_id", "label_as_anomaly"])
        writer.writerows([
            ("cpu_stress", "recommendationservice", "recommendationservice_cpu", 1),
            ("network_delay", "frontend", "frontend_p95_latency", 1),
            ("network_delay", "frontend", "frontend_avg_latency_ms", 1),
            ("network_delay", "frontend", "frontend_probe_latency_ms", 1),
            ("pod_kill", "cartservice", "cartservice_restarts", 1),
            ("pod_kill", "cartservice", "cartservice_pod_ready", 1),
            ("pod_kill", "cartservice", "cartservice_available_replicas", 1),
        ])


def main():
    parser = argparse.ArgumentParser(description="Build FluxEV-ready dataset from raw CSV files.")
    parser.add_argument("--out-dir", default="fluxev_data")
    parser.add_argument("--start", required=True)
    parser.add_argument("--test-start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()

    start = parse_iso(args.start)
    test_start = parse_iso(args.test_start)
    end = parse_iso(args.end)
    windows = read_windows(os.path.join(args.out_dir, "metadata", "fault_windows.csv"))
    raw_dir = os.path.join(args.out_dir, "raw")
    processed_dir = os.path.join(args.out_dir, "processed")
    series_dir = os.path.join(processed_dir, "series")
    os.makedirs(series_dir, exist_ok=True)
    write_metadata(args.out_dir)

    total_path = os.path.join(processed_dir, "fluxev_total.csv")
    with open(total_path, "w", newline="", encoding="utf-8") as total:
        total_writer = csv.writer(total)
        total_writer.writerow(["timestamp", "value", "label", "KPI ID", "missing", "is_test", "fault_type", "fault_id"])

        for path in read_series_files(raw_dir):
            grouped = {}
            with open(path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    ts = int(float(row["timestamp_unix"]))
                    snapped_ts = nearest_grid_ts(ts, start, end, 5)
                    if snapped_ts is None:
                        continue
                    series_id = row["series_id"]
                    row = dict(row)
                    row["timestamp_unix"] = str(snapped_ts)
                    grouped.setdefault(series_id, {})[snapped_ts] = row

            for series_id, rows_by_ts in grouped.items():
                with open(os.path.join(series_dir, f"{series_id}.csv"), "w", newline="", encoding="utf-8") as sf:
                    writer = csv.writer(sf)
                    writer.writerow(["timestamp", "value", "label", "KPI ID", "missing", "is_test", "fault_type", "fault_id"])
                    for ts in range(start, end + 1, 5):
                        row = rows_by_ts.get(ts)
                        missing = 1 if row is None else int(float(row.get("missing", 0)))
                        value = math.nan if row is None else safe_float(row.get("value"))
                        label, fault_type, fault_id = fault_for(series_id, ts, windows)
                        is_test = 1 if ts >= test_start else 0
                        if is_test == 0:
                            label, fault_type, fault_id = 0, "normal", ""
                        output = [ts, "NaN" if math.isnan(value) else value, label, series_id, missing, is_test, fault_type, fault_id]
                        writer.writerow(output)
                        total_writer.writerow(output)

    print(f"wrote {total_path}")


if __name__ == "__main__":
    main()
