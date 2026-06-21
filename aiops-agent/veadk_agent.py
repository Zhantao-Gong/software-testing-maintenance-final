import json
import os
import time
from typing import Any, Dict, List

import requests
from openai import OpenAI


PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://prometheus.monitoring.svc.cluster.local:9090",
).rstrip("/")
K8S_NAMESPACE = os.getenv("K8S_NAMESPACE", "default")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-v4-pro")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
REASONING_EFFORT = os.getenv("REASONING_EFFORT")
ENABLE_THINKING = os.getenv("ENABLE_THINKING", "").lower() in {"1", "true", "yes"}
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "30"))
RECOMMENDATION_CPU_THRESHOLD = float(os.getenv("RECOMMENDATION_CPU_THRESHOLD", "0.1"))
FRONTEND_CPU_THRESHOLD = float(os.getenv("FRONTEND_CPU_THRESHOLD", "0.1"))


def execute_promql(query_str: str) -> str:
    """Run an instant PromQL query against Prometheus."""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query_str},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            return f"Prometheus returned non-success status: {payload}"
        results = payload.get("data", {}).get("result", [])
        return json.dumps(results, ensure_ascii=False) if results else "No data returned."
    except Exception as exc:
        return f"PromQL query failed: {exc}"


def _k8s_request(method: str, path: str, **kwargs: Any) -> requests.Response:
    token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
    with open(token_path, "r", encoding="utf-8") as token_file:
        token = token_file.read().strip()
    host = os.environ["KUBERNETES_SERVICE_HOST"]
    port = os.environ["KUBERNETES_SERVICE_PORT"]
    url = f"https://{host}:{port}{path}"
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    response = requests.request(
        method,
        url,
        headers=headers,
        verify=ca_path,
        timeout=10,
        **kwargs,
    )
    response.raise_for_status()
    return response


def get_service_logs(service_name: str, tail_lines: int = 80) -> str:
    """Fetch recent logs for pods matching app=<service_name>."""
    selector = f"app={service_name}"
    pods_path = (
        f"/api/v1/namespaces/{K8S_NAMESPACE}/pods"
        f"?labelSelector={selector}"
    )
    try:
        pods = _k8s_request("GET", pods_path).json().get("items", [])
        if not pods:
            return f"No pods found for selector {selector}."
        chunks = []
        for pod in pods[:3]:
            pod_name = pod["metadata"]["name"]
            log_path = (
                f"/api/v1/namespaces/{K8S_NAMESPACE}/pods/{pod_name}/log"
                f"?tailLines={tail_lines}"
            )
            log_text = _k8s_request("GET", log_path).text
            chunks.append(f"--- {pod_name} ---\n{log_text}")
        return "\n".join(chunks)
    except Exception as exc:
        return f"Failed to get logs for {service_name}: {exc}"


def restart_deployment(service_name: str) -> str:
    """Restart an Online-Boutique deployment by patching its pod template."""
    patch = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "aiops-agent/restarted-at": str(int(time.time()))
                    }
                }
            }
        }
    }
    path = f"/apis/apps/v1/namespaces/{K8S_NAMESPACE}/deployments/{service_name}"
    try:
        _k8s_request(
            "PATCH",
            path,
            headers={"Content-Type": "application/strategic-merge-patch+json"},
            data=json.dumps(patch),
        )
        return f"Deployment {service_name} restart requested."
    except Exception as exc:
        return f"Failed to restart deployment {service_name}: {exc}"


AVAILABLE_TOOLS = {
    "execute_promql": execute_promql,
    "get_service_logs": get_service_logs,
    "restart_deployment": restart_deployment,
}


TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "execute_promql",
            "description": "Execute a PromQL query to collect Online-Boutique metrics.",
            "parameters": {
                "type": "object",
                "properties": {"query_str": {"type": "string"}},
                "required": ["query_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_service_logs",
            "description": "Read recent Kubernetes pod logs for an Online-Boutique service.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string"},
                    "tail_lines": {"type": "integer"},
                },
                "required": ["service_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restart_deployment",
            "description": "Restart a deployment only when evidence shows it is stuck or unrecoverable.",
            "parameters": {
                "type": "object",
                "properties": {"service_name": {"type": "string"}},
                "required": ["service_name"],
            },
        },
    },
]


class AIOpsAgent:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY or DEEPSEEK_API_KEY is required.")
        client_kwargs: Dict[str, Any] = {"api_key": api_key}
        if OPENAI_BASE_URL:
            client_kwargs["base_url"] = OPENAI_BASE_URL
        self.client = OpenAI(**client_kwargs)
        self.system_prompt = """
You are a senior cloud-native AIOps expert for the Online-Boutique microservice system.
Use tools to gather evidence before deciding. Distinguish periodic load changes from real failures.
Prefer diagnosis and reporting. Restart a deployment only when logs and metrics strongly indicate a stuck,
unrecoverable service state.
Return a concise report with evidence, likely root cause, impact, and action taken.
"""

    def run_diagnosis(self, alert_context: str) -> None:
        print("\n" + "=" * 80, flush=True)
        print(f"[Agent] Alert received: {alert_context}", flush=True)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Investigate this Online-Boutique alert: {alert_context}"},
        ]

        for step in range(5):
            print(f"[Agent] Reasoning step {step + 1}", flush=True)
            request_kwargs: Dict[str, Any] = {}
            if REASONING_EFFORT:
                request_kwargs["reasoning_effort"] = REASONING_EFFORT
            if ENABLE_THINKING:
                request_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                **request_kwargs,
            )
            response_message = response.choices[0].message
            messages.append(response_message)

            if not response_message.tool_calls:
                print("[Agent] Final report:", flush=True)
                print(response_message.content, flush=True)
                print("=" * 80 + "\n", flush=True)
                return

            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments or "{}")
                print(f"[Agent] Tool call: {function_name}({function_args})", flush=True)
                tool_result = AVAILABLE_TOOLS[function_name](**function_args)
                print(f"[Agent] Tool result: {str(tool_result)[:1200]}", flush=True)
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(tool_result),
                    }
                )

        messages.append(
            {
                "role": "user",
                "content": "Stop calling tools now. Produce the final diagnosis report from the evidence already collected.",
            }
        )
        final_response = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="none",
        )
        print("[Agent] Final report after max tool steps:", flush=True)
        print(final_response.choices[0].message.content, flush=True)
        print("=" * 80 + "\n", flush=True)


def _prom_value(query: str) -> float:
    result_text = execute_promql(query)
    try:
        result = json.loads(result_text)
        return float(result[0]["value"][1]) if result else 0.0
    except Exception:
        return 0.0


def collect_basic_signals() -> Dict[str, float]:
    return {
        "recommendation_cpu": _prom_value(
            'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"recommendationservice-.*"}[1m]))'
        ),
        "frontend_cpu": _prom_value(
            'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"frontend-.*"}[1m]))'
        ),
        "cart_restarts_5m": _prom_value(
            'sum(increase(kube_pod_container_status_restarts_total{namespace="default",pod=~"cartservice-.*"}[5m]))'
        ),
        "unready_pods": _prom_value(
            'sum(kube_pod_status_ready{namespace="default",condition="false"})'
        ),
    }


def should_alert(signals: Dict[str, float]) -> str:
    reasons = []
    if signals["recommendation_cpu"] > RECOMMENDATION_CPU_THRESHOLD:
        reasons.append(f"recommendationservice CPU is {signals['recommendation_cpu']:.4f}")
    if signals["frontend_cpu"] > FRONTEND_CPU_THRESHOLD:
        reasons.append(f"frontend CPU is {signals['frontend_cpu']:.4f}")
    if signals["cart_restarts_5m"] > 0:
        reasons.append(f"cartservice restarted {signals['cart_restarts_5m']:.0f} times in 5m")
    if signals["unready_pods"] > 0:
        reasons.append(f"{signals['unready_pods']:.0f} pods are not ready")
    return "; ".join(reasons)


def main() -> None:
    agent = AIOpsAgent()
    print("[Agent] Online-Boutique AIOps monitor started.", flush=True)
    print(f"[Agent] Prometheus: {PROMETHEUS_URL}", flush=True)
    while True:
        signals = collect_basic_signals()
        print(f"[Agent] Signals: {json.dumps(signals)}", flush=True)
        alert = should_alert(signals)
        if alert:
            agent.run_diagnosis(alert)
            time.sleep(60)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
