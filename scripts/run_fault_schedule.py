#!/usr/bin/env python3
import argparse
import csv
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def write_yaml(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def apply_yaml(path):
    run(["kubectl", "apply", "-f", path])


def delete_chaos(kind, name, chaos_ns):
    subprocess.run(["kubectl", "delete", kind, name, "-n", chaos_ns, "--ignore-not-found=true"], check=False)


def sleep_until(start_at, offset_seconds):
    target = start_at + timedelta(seconds=offset_seconds)
    wait_for = (target - utc_now()).total_seconds()
    if wait_for > 0:
        time.sleep(wait_for)


def append_fault(log_path, row):
    new_file = not os.path.exists(log_path)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["fault_id", "fault_type", "chaos_kind", "chaos_name", "target_service", "apply_time_iso", "end_time_iso", "label_start_iso", "label_end_iso", "duration_seconds", "notes"])
        writer.writerow(row)


def run_cpu(idx, offset, args, start_at, fault_log):
    sleep_until(start_at, offset)
    fault_id = f"F{idx:03d}"
    name = f"cpu-stress-recommendationservice-{idx:03d}"
    path = os.path.join(args.out_dir, "chaos", f"{name}.yaml")
    apply_time = utc_now()
    write_yaml(path, f"""apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: {name}
  namespace: {args.chaos_namespace}
spec:
  mode: all
  selector:
    namespaces:
      - {args.namespace}
    labelSelectors:
      app: recommendationservice
  stressors:
    cpu:
      workers: 2
      load: 80
  duration: "3m"
""")
    apply_yaml(path)
    append_fault(fault_log, [fault_id, "cpu_stress", "StressChaos", name, "recommendationservice", iso(apply_time), iso(apply_time + timedelta(seconds=180)), iso(apply_time), iso(apply_time + timedelta(seconds=240)), 180, "workers=2 load=80"])


def run_network(idx, offset, args, start_at, fault_log):
    sleep_until(start_at, offset)
    fault_id = f"F{idx:03d}"
    name = f"network-delay-frontend-{idx:03d}"
    path = os.path.join(args.out_dir, "chaos", f"{name}.yaml")
    apply_time = utc_now()
    write_yaml(path, f"""apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: {name}
  namespace: {args.chaos_namespace}
spec:
  action: delay
  mode: all
  selector:
    namespaces:
      - {args.namespace}
    labelSelectors:
      app: frontend
  delay:
    latency: "300ms"
    correlation: "25"
    jitter: "50ms"
  duration: "3m"
""")
    apply_yaml(path)
    append_fault(fault_log, [fault_id, "network_delay", "NetworkChaos", name, "frontend", iso(apply_time), iso(apply_time + timedelta(seconds=180)), iso(apply_time), iso(apply_time + timedelta(seconds=240)), 180, "latency=300ms jitter=50ms"])


def run_pod_kill(idx, offset, args, start_at, fault_log):
    sleep_until(start_at, offset)
    fault_id = f"F{idx:03d}"
    name = f"pod-kill-cartservice-{idx:03d}"
    path = os.path.join(args.out_dir, "chaos", f"{name}.yaml")
    apply_time = utc_now()
    write_yaml(path, f"""apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: {name}
  namespace: {args.chaos_namespace}
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - {args.namespace}
    labelSelectors:
      app: cartservice
""")
    apply_yaml(path)
    append_fault(fault_log, [fault_id, "pod_kill", "PodChaos", name, "cartservice", iso(apply_time), iso(apply_time + timedelta(seconds=5)), iso(apply_time), iso(apply_time + timedelta(seconds=120)), 0, "mode=one"])
    time.sleep(20)
    delete_chaos("PodChaos", name, args.chaos_namespace)


def main():
    parser = argparse.ArgumentParser(description="Run the FluxEV Chaos Mesh fault schedule.")
    parser.add_argument("--namespace", default=os.environ.get("OB_NS", "default"))
    parser.add_argument("--chaos-namespace", default=os.environ.get("CHAOS_NS", "chaos-testing"))
    parser.add_argument("--out-dir", default=os.environ.get("OUT_DIR", "fluxev_data"))
    parser.add_argument("--start-at", default=os.environ.get("START_AT_ISO"))
    args = parser.parse_args()

    if not args.start_at:
        raise SystemExit("--start-at or START_AT_ISO is required")
    start_at = parse_iso(args.start_at)
    fault_log = os.path.join(args.out_dir, "metadata", "fault_windows.csv")

    run_cpu(1, 7200, args, start_at, fault_log)
    run_cpu(2, 7800, args, start_at, fault_log)
    run_cpu(3, 8400, args, start_at, fault_log)
    run_network(4, 9000, args, start_at, fault_log)
    run_network(5, 9600, args, start_at, fault_log)
    run_network(6, 10200, args, start_at, fault_log)
    run_pod_kill(7, 10800, args, start_at, fault_log)
    run_pod_kill(8, 11400, args, start_at, fault_log)
    run_pod_kill(9, 12000, args, start_at, fault_log)


if __name__ == "__main__":
    main()
