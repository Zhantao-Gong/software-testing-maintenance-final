#!/usr/bin/env python3
import argparse
import csv
import struct
import zlib
import math
import os
from collections import Counter, defaultdict
from datetime import datetime


PRIMARY_SERIES = {
    "recommendationservice_cpu",
    "frontend_p95_latency",
    "frontend_avg_latency_ms",
    "frontend_probe_latency_ms",
    "cartservice_restarts",
    "cartservice_pod_ready",
    "cartservice_available_replicas",
}


def parse_iso(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def numeric_values(rows):
    values = []
    for row in rows:
        try:
            value = float(row["value"])
            if not math.isnan(value):
                values.append(value)
        except ValueError:
            pass
    return values


def mean(values):
    return sum(values) / len(values) if values else math.nan


def try_plot(series_id, rows, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return fallback_plot(series_id, rows, out_dir)
    xs = [int(row["timestamp"]) for row in rows]
    ys = []
    for row in rows:
        try:
            ys.append(float(row["value"]))
        except ValueError:
            ys.append(math.nan)
    labels = [int(row["label"]) for row in rows]
    if not xs:
        return False
    os.makedirs(out_dir, exist_ok=True)
    plt.figure(figsize=(12, 4))
    plt.plot(xs, ys, linewidth=1)
    for x, label in zip(xs, labels):
        if label:
            plt.axvline(x, color="red", alpha=0.03)
    plt.title(series_id)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{series_id}.png"))
    plt.close()
    return True


def format_time_label(ts):
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def unit_for_series(series_id):
    if series_id.endswith("_cpu"):
        return "CPU cores"
    if "latency" in series_id:
        return "latency (ms)"
    if "memory" in series_id:
        return "memory (bytes)"
    if "restarts" in series_id:
        return "restart count"
    if "ready" in series_id or "replicas" in series_id:
        return "pod/replica count"
    if "qps" in series_id:
        return "requests/sec"
    return "value"


def pil_plot(series_id, rows, out_dir):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False

    width, height = 1200, 520
    left, right, top, bottom = 92, 36, 58, 86
    plot_w = width - left - right
    plot_h = height - top - bottom
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 15)
        small = ImageFont.truetype("arial.ttf", 12)
        title_font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
        small = ImageFont.load_default()
        title_font = ImageFont.load_default()

    points = []
    labels = []
    for row in rows:
        try:
            value = float(row["value"])
        except ValueError:
            value = math.nan
        points.append((int(row["timestamp"]), value))
        labels.append(int(row["label"]))
    finite = [(ts, value) for ts, value in points if not math.isnan(value)]
    if not finite:
        return False

    xs = [ts for ts, _ in points]
    values = [value for _, value in finite]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(values), max(values)
    pad = (ymax - ymin) * 0.08 if ymax != ymin else 1.0
    ymin -= pad
    ymax += pad

    def x_to_px(ts):
        return left + int((ts - xmin) * plot_w / max(1, xmax - xmin))

    def y_to_px(value):
        return top + int((ymax - value) * plot_h / max(1e-12, ymax - ymin))

    # Anomaly background.
    in_label = False
    start_x = None
    for (ts, _), label in zip(points, labels):
        if label and not in_label:
            in_label = True
            start_x = x_to_px(ts)
        if in_label and not label:
            draw.rectangle([start_x, top, x_to_px(ts), top + plot_h], fill=(255, 232, 232))
            in_label = False
    if in_label:
        draw.rectangle([start_x, top, left + plot_w, top + plot_h], fill=(255, 232, 232))

    # Grid, ticks, and axes.
    for i in range(6):
        y = top + int(i * plot_h / 5)
        value = ymax - i * (ymax - ymin) / 5
        draw.line([(left, y), (left + plot_w, y)], fill=(232, 232, 232))
        draw.text((8, y - 7), f"{value:.4g}", fill=(55, 55, 55), font=small)
    for i in range(7):
        x = left + int(i * plot_w / 6)
        ts = xmin + int(i * (xmax - xmin) / 6)
        draw.line([(x, top), (x, top + plot_h)], fill=(242, 242, 242))
        draw.text((x - 18, top + plot_h + 10), format_time_label(ts), fill=(55, 55, 55), font=small)

    draw.line([(left, top), (left, top + plot_h), (left + plot_w, top + plot_h)], fill=(40, 40, 40), width=2)

    # Data line.
    line = []
    for ts, value in points:
        if math.isnan(value):
            if len(line) > 1:
                draw.line(line, fill=(28, 88, 168), width=2)
            line = []
        else:
            line.append((x_to_px(ts), y_to_px(value)))
    if len(line) > 1:
        draw.line(line, fill=(28, 88, 168), width=2)

    draw.text((left, 20), series_id, fill=(20, 20, 20), font=title_font)
    draw.text((left + plot_w // 2 - 48, height - 38), "time (UTC)", fill=(40, 40, 40), font=font)
    draw.text((10, 22), unit_for_series(series_id), fill=(40, 40, 40), font=font)
    draw.rectangle([left + plot_w - 180, 20, left + plot_w - 166, 34], fill=(255, 232, 232))
    draw.text((left + plot_w - 158, 18), "labeled anomaly window", fill=(55, 55, 55), font=small)

    os.makedirs(out_dir, exist_ok=True)
    image.save(os.path.join(out_dir, f"{series_id}.png"))
    return True


def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path, width, height, pixels):
    raw = b"".join(b"\x00" + bytes(row) for row in pixels)
    data = b"\x89PNG\r\n\x1a\n"
    data += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += png_chunk(b"IDAT", zlib.compress(raw, 9))
    data += png_chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)


def draw_line(pixels, x0, y0, x1, y1, color):
    width = len(pixels[0]) // 3
    height = len(pixels)
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        if 0 <= x < width and 0 <= y < height:
            idx = x * 3
            pixels[y][idx:idx + 3] = color
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def fallback_plot(series_id, rows, out_dir):
    if pil_plot(series_id, rows, out_dir):
        return True
    width, height = 1000, 320
    margin = 36
    values = []
    labels = []
    for row in rows:
        try:
            value = float(row["value"])
        except ValueError:
            value = math.nan
        values.append(value)
        labels.append(int(row["label"]))
    finite = [value for value in values if not math.isnan(value)]
    if not finite:
        return False
    ymin, ymax = min(finite), max(finite)
    if ymin == ymax:
        ymin -= 1.0
        ymax += 1.0
    pixels = [bytearray([255, 255, 255] * width) for _ in range(height)]
    plot_w = width - 2 * margin
    plot_h = height - 2 * margin

    for i, label in enumerate(labels):
        if label:
            x = margin + int(i * plot_w / max(1, len(values) - 1))
            for y in range(margin, height - margin):
                idx = x * 3
                pixels[y][idx:idx + 3] = b"\xff\xe0\xe0"

    prev = None
    for i, value in enumerate(values):
        if math.isnan(value):
            prev = None
            continue
        x = margin + int(i * plot_w / max(1, len(values) - 1))
        y = height - margin - int((value - ymin) * plot_h / (ymax - ymin))
        if prev:
            draw_line(pixels, prev[0], prev[1], x, y, b"\x1f\x5f\xb8")
        prev = (x, y)

    draw_line(pixels, margin, margin, margin, height - margin, b"\x40\x40\x40")
    draw_line(pixels, margin, height - margin, width - margin, height - margin, b"\x40\x40\x40")
    os.makedirs(out_dir, exist_ok=True)
    write_png(os.path.join(out_dir, f"{series_id}.png"), width, height, pixels)
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate FluxEV data quality report.")
    parser.add_argument("--out-dir", default="fluxev_data")
    parser.add_argument("--start", required=True)
    parser.add_argument("--test-start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--step", type=int, default=5)
    args = parser.parse_args()

    start = parse_iso(args.start)
    test_start = parse_iso(args.test_start)
    end = parse_iso(args.end)
    expected_points = ((end - start) // args.step) + 1
    total_path = os.path.join(args.out_dir, "processed", "fluxev_total.csv")
    rows = read_rows(total_path)
    by_series = defaultdict(list)
    for row in rows:
        by_series[row["KPI ID"]].append(row)

    windows_path = os.path.join(args.out_dir, "metadata", "fault_windows.csv")
    windows = read_rows(windows_path) if os.path.exists(windows_path) else []
    fault_counts = Counter(row["fault_type"] for row in windows)
    report = []
    report.append("# Data Quality Report")
    report.append("")
    report.append(f"- expected_points_per_series: {expected_points}")
    report.append(f"- total_rows: {len(rows)}")
    report.append(f"- series_count: {len(by_series)}")
    report.append("")
    report.append("## Series Checks")
    report.append("")
    report.append("| series_id | points | missing_ratio | strict_5s | train_label_sum | label_sum | pass |")
    report.append("| --- | ---: | ---: | --- | ---: | ---: | --- |")
    failures = []
    for series_id, series_rows in sorted(by_series.items()):
        series_rows.sort(key=lambda row: int(row["timestamp"]))
        points = len(series_rows)
        missing = sum(int(float(row["missing"])) for row in series_rows)
        labels = sum(int(row["label"]) for row in series_rows)
        train_labels = sum(int(row["label"]) for row in series_rows if int(row["timestamp"]) < test_start)
        timestamps = [int(row["timestamp"]) for row in series_rows]
        strict_5s = all((b - a) == args.step for a, b in zip(timestamps, timestamps[1:]))
        missing_ratio = missing / points if points else 1.0
        ok = points == expected_points and strict_5s and train_labels == 0
        if series_id in PRIMARY_SERIES:
            ok = ok and missing_ratio < 0.05
        if not ok:
            failures.append(series_id)
        report.append(f"| {series_id} | {points} | {missing_ratio:.4f} | {strict_5s} | {train_labels} | {labels} | {ok} |")

    report.append("")
    report.append("## Fault Windows")
    report.append("")
    for fault_type in ["cpu_stress", "network_delay", "pod_kill"]:
        report.append(f"- {fault_type}: {fault_counts.get(fault_type, 0)} windows")

    report.append("")
    report.append("## Fault Signal Checks")
    report.append("")
    for series_id, series_rows in sorted(by_series.items()):
        if series_id not in PRIMARY_SERIES:
            continue
        train_values = numeric_values([row for row in series_rows if int(row["timestamp"]) < test_start])
        anomaly_values = numeric_values([row for row in series_rows if int(row["label"]) == 1])
        report.append(f"- {series_id}: train_mean={mean(train_values):.6g}, anomaly_mean={mean(anomaly_values):.6g}, anomaly_points={len(anomaly_values)}")

    report.append("")
    report.append("## Result")
    report.append("")
    report.append("PASS" if not failures and all(fault_counts.get(ft, 0) == 3 for ft in ["cpu_stress", "network_delay", "pod_kill"]) else "REVIEW_REQUIRED")
    if failures:
        report.append("")
        report.append("Series needing review: " + ", ".join(failures))

    qa_dir = os.path.join(args.out_dir, "qa")
    os.makedirs(qa_dir, exist_ok=True)
    preview_dir = os.path.join(qa_dir, "preview_plots")
    for series_id in ["recommendationservice_cpu", "frontend_probe_latency_ms", "frontend_p95_latency", "frontend_avg_latency_ms", "cartservice_restarts", "cartservice_pod_ready"]:
        if series_id in by_series:
            try_plot(series_id, by_series[series_id], preview_dir)
    with open(os.path.join(qa_dir, "data_quality_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(os.path.join(qa_dir, "data_quality_report.md"))


if __name__ == "__main__":
    main()
