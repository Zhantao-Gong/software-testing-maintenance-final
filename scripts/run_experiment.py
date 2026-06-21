#!/usr/bin/env python3
import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def py():
    return sys.executable


def run(cmd, **kwargs):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, cwd=ROOT, **kwargs)


def ready(url):
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/-/ready", timeout=5) as response:
            return response.status < 500
    except Exception:
        return False


def start_port_forward(local_port, prometheus_namespace):
    cmd = ["kubectl", "port-forward", "-n", prometheus_namespace, "deployment/prometheus-deployment", f"{local_port}:9090"]
    log_path = os.path.join(ROOT, "fluxev_data", "metadata", "prometheus_port_forward.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=log)
    for _ in range(30):
        if ready(f"http://localhost:{local_port}"):
            return proc
        time.sleep(1)
    raise RuntimeError("Prometheus port-forward did not become ready")


def terminate(proc):
    if not proc or proc.poll() is not None:
        return
    if os.name == "nt":
        proc.terminate()
    else:
        proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def main():
    parser = argparse.ArgumentParser(description="Run the full FluxEV data collection experiment.")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--chaos-namespace", default="chaos-testing")
    parser.add_argument("--prometheus-namespace", default="monitoring")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--frontend-url", default="http://localhost:8080/")
    parser.add_argument("--out-dir", default="fluxev_data")
    parser.add_argument("--warmup-minutes", type=int, default=10)
    parser.add_argument("--train-minutes", type=int, default=120)
    parser.add_argument("--test-minutes", type=int, default=120)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--skip-wait", action="store_true", help="Use only for script testing; skips the 4h collection wait.")
    args = parser.parse_args()

    out_dir = os.path.join(ROOT, args.out_dir)
    for subdir in ["config", "metadata", "raw/prometheus", "raw/probe", "processed/series", "qa/preview_plots", "chaos"]:
        os.makedirs(os.path.join(out_dir, subdir), exist_ok=True)

    port_forward = None
    if not ready(args.prometheus_url):
        port_forward = start_port_forward(9090, args.prometheus_namespace)

    run([py(), "scripts/preflight.py", "--namespace", args.namespace, "--prometheus-namespace", args.prometheus_namespace, "--frontend-url", args.frontend_url, "--prometheus-url", args.prometheus_url])

    now = datetime.now(timezone.utc).replace(microsecond=0)
    warmup_start = now
    t0 = warmup_start + timedelta(minutes=args.warmup_minutes)
    test_start = t0 + timedelta(minutes=args.train_minutes)
    end = test_start + timedelta(minutes=args.test_minutes)

    env = os.environ.copy()
    env.update({
        "OB_NS": args.namespace,
        "CHAOS_NS": args.chaos_namespace,
        "OUT_DIR": args.out_dir,
        "FRONTEND_URL": args.frontend_url,
        "START_AT_ISO": iso(t0),
    })

    with open(os.path.join(out_dir, "config", "experiment_config.yaml"), "w", encoding="utf-8") as f:
        f.write(f"""system: Online-Boutique
namespace: {args.namespace}
chaos_namespace: {args.chaos_namespace}
prometheus_url: {args.prometheus_url}
frontend_url: {args.frontend_url}
sampling:
  scrape_interval_seconds: {args.step}
  query_range_step: {args.step}s
workload:
  type: periodic_loadgenerator_replicas
  period_seconds: 300
  period_points_l: 60
  pattern:
    - {{phase: low, replicas: 1, duration_seconds: 60}}
    - {{phase: mid, replicas: 2, duration_seconds: 60}}
    - {{phase: high, replicas: 4, duration_seconds: 60}}
    - {{phase: mid, replicas: 2, duration_seconds: 60}}
    - {{phase: low, replicas: 1, duration_seconds: 60}}
fluxev_parameters:
  s: 10
  p: 5
  d: 2
  q: 0.001
  period_l: 60
  init_points_target: 1440
  estimated_a: 262
  estimated_k: 1178
timeline:
  warmup_start_iso: {iso(warmup_start)}
  t0_iso: {iso(t0)}
  test_start_iso: {iso(test_start)}
  end_iso: {iso(end)}
  warmup_minutes: {args.warmup_minutes}
  init_train_minutes: {args.train_minutes}
  test_minutes: {args.test_minutes}
""")

    with open(os.path.join(out_dir, "config", "metrics_config.yaml"), "w", encoding="utf-8") as f:
        f.write("""required_series:
  - recommendationservice_cpu
  - frontend_cpu
  - cartservice_cpu
  - recommendationservice_memory
  - frontend_memory
  - cartservice_memory
  - cartservice_pod_ready
  - frontend_pod_ready
  - recommendationservice_pod_ready
  - cartservice_restarts
  - cartservice_available_replicas
optional_series:
  - frontend_qps
  - frontend_5xx_rate
  - frontend_p95_latency
  - frontend_avg_latency_ms
probe_series:
  - frontend_probe_latency_ms
  - frontend_probe_error_rate
""")

    logs_dir = os.path.join(out_dir, "metadata")
    load_log = open(os.path.join(logs_dir, "periodic_load.log"), "a", encoding="utf-8")
    probe_log = open(os.path.join(logs_dir, "frontend_probe.log"), "a", encoding="utf-8")
    fault_log = open(os.path.join(logs_dir, "fault_schedule.log"), "a", encoding="utf-8")

    load_proc = subprocess.Popen([py(), "scripts/run_periodic_load.py", "--namespace", args.namespace, "--out-dir", args.out_dir, "--end-at", iso(end)], cwd=ROOT, env=env, stdout=load_log, stderr=load_log)
    total_probe_seconds = int((end - warmup_start).total_seconds()) + 30
    probe_proc = subprocess.Popen([py(), "scripts/run_frontend_probe.py", "--url", args.frontend_url, "--out", os.path.join(args.out_dir, "raw/probe/frontend_probe.csv"), "--interval", str(args.step), "--duration-seconds", str(total_probe_seconds)], cwd=ROOT, env=env, stdout=probe_log, stderr=probe_log)
    fault_proc = subprocess.Popen([py(), "scripts/run_fault_schedule.py", "--namespace", args.namespace, "--chaos-namespace", args.chaos_namespace, "--out-dir", args.out_dir, "--start-at", iso(t0)], cwd=ROOT, env=env, stdout=fault_log, stderr=fault_log)

    try:
        if args.skip_wait:
            print("skip-wait enabled; leaving collection processes running for manual inspection")
            return
        wait_seconds = max(0, int((end - datetime.now(timezone.utc)).total_seconds()) + 30)
        print(f"collection running: T0={iso(t0)} test_start={iso(test_start)} end={iso(end)} wait_seconds={wait_seconds}", flush=True)
        time.sleep(wait_seconds)
    finally:
        terminate(load_proc)
        terminate(probe_proc)
        try:
            fault_proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            terminate(fault_proc)
        load_log.close()
        probe_log.close()
        fault_log.close()

    try:
        run([py(), "scripts/export_prometheus.py", "--prometheus-url", args.prometheus_url, "--namespace", args.namespace, "--start", iso(t0), "--end", iso(end), "--step", str(args.step), "--out-dir", os.path.join(args.out_dir, "raw/prometheus")])
        run([py(), "scripts/build_fluxev_dataset.py", "--out-dir", args.out_dir, "--start", iso(t0), "--test-start", iso(test_start), "--end", iso(end)])
        run([py(), "scripts/qa_report.py", "--out-dir", args.out_dir, "--start", iso(t0), "--test-start", iso(test_start), "--end", iso(end), "--step", str(args.step)])
    finally:
        terminate(port_forward)


if __name__ == "__main__":
    main()
