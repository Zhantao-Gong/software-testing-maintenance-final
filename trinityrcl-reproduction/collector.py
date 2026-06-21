import requests
import pandas as pd
import time
import os
from datetime import datetime

PROM_URL = "http://localhost:9090"

OUTPUT_FILE = "metrics.csv"
FAULT_FILE = "fault_log.csv"

CPU_QUERY = '''
rate(container_cpu_usage_seconds_total{namespace="default"}[1m])
'''

MEM_QUERY = '''
container_memory_usage_bytes{namespace="default"}
'''

POD_STATUS_QUERY = '''
kube_pod_status_phase{phase="Running"}
'''

POD_CREATED_QUERY = '''
kube_pod_created
'''

IGNORE_SERVICES = [
    "prometheus",
    "grafana",
    "alertmanager",
    "node-exporter",
    "jaeger",
    "coredns",
    "etcd",
    "storage",
    "kube"
]

last_created = {}


def query_prometheus(query):

    r = requests.get(
        f"{PROM_URL}/api/v1/query",
        params={"query": query},
        timeout=30
    )

    r.raise_for_status()

    return r.json()["data"]["result"]


def pod_to_service(pod_name):

    if not pod_name:
        return None

    for ignore in IGNORE_SERVICES:
        if ignore in pod_name:
            return None

    parts = pod_name.split("-")

    if len(parts) >= 2:
        return parts[0]

    return pod_name


def collect_cpu():

    result = query_prometheus(CPU_QUERY)

    data = {}

    for item in result:

        pod = item["metric"].get("pod", "")
        service = pod_to_service(pod)

        if service is None:
            continue

        data[service] = float(item["value"][1])

    return data


def collect_memory():

    result = query_prometheus(MEM_QUERY)

    data = {}

    for item in result:

        pod = item["metric"].get("pod", "")
        service = pod_to_service(pod)

        if service is None:
            continue

        data[service] = float(item["value"][1])

    return data


def collect_running():

    result = query_prometheus(POD_STATUS_QUERY)

    data = {}

    for item in result:

        pod = item["metric"].get("pod", "")
        service = pod_to_service(pod)

        if service is None:
            continue

        data[service] = float(item["value"][1])

    return data


def collect_created():

    result = query_prometheus(POD_CREATED_QUERY)

    data = {}

    for item in result:

        pod = item["metric"].get("pod", "")
        service = pod_to_service(pod)

        if service is None:
            continue

        data[service] = float(item["value"][1])

    return data


def append_fault_log(service, old_time, new_time):

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row = pd.DataFrame([{
        "timestamp": now,
        "service": service,
        "event": "pod_recreated",
        "old_created": old_time,
        "new_created": new_time
    }])

    if os.path.exists(FAULT_FILE):

        old = pd.read_csv(FAULT_FILE)
        row = pd.concat([old, row])

    row.to_csv(FAULT_FILE, index=False)


def collect_once():

    global last_created

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cpu = collect_cpu()
    memory = collect_memory()
    running = collect_running()
    created = collect_created()

    services = set()

    services.update(cpu.keys())
    services.update(memory.keys())
    services.update(running.keys())
    services.update(created.keys())

    rows = []

    for service in services:

        cpu_value = cpu.get(service, 0)
        mem_value = memory.get(service, 0)
        running_value = running.get(service, 0)
        created_value = created.get(service, 0)

        if service in last_created:

            if created_value != last_created[service]:

                print(
                    f"[FAULT] {service} recreated "
                    f"{last_created[service]} -> {created_value}"
                )

                append_fault_log(
                    service,
                    last_created[service],
                    created_value
                )

        last_created[service] = created_value

        rows.append({
            "timestamp": now,
            "service": service,
            "cpu": cpu_value,
            "memory": mem_value,
            "pod_running": running_value,
            "pod_created": created_value
        })

    return rows


def save_rows(rows):

    new_df = pd.DataFrame(rows)

    if os.path.exists(OUTPUT_FILE):

        old_df = pd.read_csv(OUTPUT_FILE)

        df = pd.concat(
            [old_df, new_df],
            ignore_index=True
        )

    else:

        df = new_df

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )


def main():

    print("=" * 50)
    print("TrinityRCL Metrics Collector")
    print("Sampling Interval: 10 seconds")
    print("Output:", OUTPUT_FILE)
    print("=" * 50)

    while True:

        try:

            rows = collect_once()

            save_rows(rows)

            print(
                datetime.now().strftime("%H:%M:%S"),
                f"Collected {len(rows)} services"
            )

        except Exception as e:

            print("ERROR:", e)

        time.sleep(10)


if __name__ == "__main__":
    main()