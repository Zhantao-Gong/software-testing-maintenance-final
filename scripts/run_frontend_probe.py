#!/usr/bin/env python3
import argparse
import csv
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def utc_iso(ts=None):
    dt = datetime.fromtimestamp(ts or time.time(), tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def probe_once(url, timeout):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            response.read(256)
            ok = 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        ok = False
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return ok, elapsed_ms


def main():
    parser = argparse.ArgumentParser(description="Probe Online Boutique frontend every N seconds.")
    parser.add_argument("--url", default=os.environ.get("FRONTEND_URL", "http://localhost:8080/"))
    parser.add_argument("--out", default="fluxev_data/raw/probe/frontend_probe.csv")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--requests", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--duration-seconds", type=int, default=0, help="0 means run forever.")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    new_file = not os.path.exists(args.out)
    end_at = time.time() + args.duration_seconds if args.duration_seconds > 0 else None

    with open(args.out, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["timestamp_iso", "timestamp_unix", "series_id", "value", "missing"])
            f.flush()

        while True:
            cycle_started = time.time()
            unix_ts = int(cycle_started // args.interval * args.interval)
            results = [probe_once(args.url, args.timeout) for _ in range(args.requests)]
            latencies = [latency for ok, latency in results if ok]
            errors = sum(1 for ok, _ in results if not ok)
            latency_value = sum(latencies) / len(latencies) if latencies else args.timeout * 1000.0
            error_rate = errors / max(args.requests, 1)
            timestamp = utc_iso(unix_ts)
            writer.writerow([timestamp, unix_ts, "frontend_probe_latency_ms", latency_value, 0])
            writer.writerow([timestamp, unix_ts, "frontend_probe_error_rate", error_rate, 0])
            f.flush()

            if end_at and time.time() >= end_at:
                break
            sleep_for = args.interval - ((time.time() - cycle_started) % args.interval)
            time.sleep(max(0.1, sleep_for))


if __name__ == "__main__":
    main()
