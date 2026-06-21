#!/usr/bin/env python3
import argparse
import csv
import os
import subprocess
import time
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def append_row(path, row):
    new_file = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["timestamp_iso", "replicas", "phase"])
        writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Scale Online Boutique loadgenerator in a 5-minute periodic pattern.")
    parser.add_argument("--namespace", default=os.environ.get("OB_NS", "default"))
    parser.add_argument("--deployment", default=os.environ.get("LOADGEN_DEPLOYMENT", "loadgenerator"))
    parser.add_argument("--out-dir", default=os.environ.get("OUT_DIR", "fluxev_data"))
    parser.add_argument("--pattern", default=os.environ.get("LOAD_PATTERN", "1:low,2:mid,4:high,2:mid,1:low"))
    parser.add_argument("--end-at", default="")
    args = parser.parse_args()

    end_at = parse_iso(args.end_at) if args.end_at else None
    steps = []
    for item in args.pattern.split(","):
        replicas, phase = item.split(":", 1)
        steps.append((int(replicas), phase))
    log_path = os.path.join(args.out_dir, "metadata", "load_profile.csv")

    while end_at is None or utc_now() < end_at:
        for replicas, phase in steps:
            if end_at is not None and utc_now() >= end_at:
                return
            ts = utc_now()
            cmd = ["kubectl", "scale", f"deployment/{args.deployment}", "-n", args.namespace, f"--replicas={replicas}"]
            print("+", " ".join(cmd), flush=True)
            subprocess.run(cmd, check=True)
            append_row(log_path, [iso(ts), replicas, phase])
            print(f"{iso(ts)},{replicas},{phase}", flush=True)
            time.sleep(60)


if __name__ == "__main__":
    main()
