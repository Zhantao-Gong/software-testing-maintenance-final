#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import urllib.request


def run(cmd, timeout=30, check=True):
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{result.stderr.strip()}")
    return result.stdout.strip()


def http_ok(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status < 500
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Preflight checks for FluxEV data collection.")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--prometheus-namespace", default="monitoring")
    parser.add_argument("--frontend-url", default="http://localhost:8080/")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    args = parser.parse_args()

    checks = []
    for deployment in ["frontend", "cartservice", "recommendationservice", "loadgenerator"]:
        run(["kubectl", "get", "deploy", "-n", args.namespace, deployment], timeout=30)
        checks.append(f"deployment/{deployment}: ok")
    run(["kubectl", "get", "deploy", "-n", args.prometheus_namespace, "prometheus-deployment"], timeout=30)
    checks.append("monitoring/prometheus-deployment: ok")
    for crd in ["stresschaos.chaos-mesh.org", "networkchaos.chaos-mesh.org", "podchaos.chaos-mesh.org"]:
        run(["kubectl", "get", "crd", crd], timeout=30)
        checks.append(f"crd/{crd}: ok")
    if not http_ok(args.frontend_url):
        raise RuntimeError(f"frontend not reachable: {args.frontend_url}")
    checks.append(f"frontend_url: {args.frontend_url}")
    if not http_ok(args.prometheus_url.rstrip("/") + "/-/ready"):
        checks.append(f"prometheus_url: not ready at {args.prometheus_url}; use port-forward before collection")
    else:
        checks.append(f"prometheus_url: {args.prometheus_url}")
    print(json.dumps({"ok": True, "checks": checks}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)
