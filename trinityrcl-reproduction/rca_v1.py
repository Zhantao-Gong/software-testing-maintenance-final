import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt

# ==========================
# 读取数据
# ==========================

metrics = pd.read_csv("metrics.csv")

dependency = pd.read_csv("dependency.csv")

metrics["timestamp"] = pd.to_datetime(metrics["timestamp"])

# ==========================
# 故障时间
# ==========================

FAULT_TIME = pd.Timestamp("2026-06-12 01:25:18")

# ==========================
# 基线数据
# ==========================

baseline = metrics[
    metrics["timestamp"] < FAULT_TIME
]

fault_window = metrics[
    metrics["timestamp"] >= FAULT_TIME
]

# ==========================
# 异常检测
# ==========================

scores = {}

services = metrics["service"].unique()

for service in services:

    base = baseline[
        baseline["service"] == service
    ]

    fault = fault_window[
        fault_window["service"] == service
    ]

    if len(base) < 3:
        continue

    if len(fault) == 0:
        continue

    cpu_mean = base["cpu"].mean()
    cpu_std = base["cpu"].std()

    mem_mean = base["memory"].mean()
    mem_std = base["memory"].std()

    if cpu_std == 0:
        cpu_std = 1e-6

    if mem_std == 0:
        mem_std = 1e-6

    cpu_fault = fault["cpu"].max()
    mem_fault = fault["memory"].min()

    cpu_score = abs(
        (cpu_fault - cpu_mean)
        / cpu_std
    )

    mem_score = abs(
        (mem_fault - mem_mean)
        / mem_std
    )

    score = cpu_score + mem_score

    scores[service] = score

# ==========================
# 构建服务图
# ==========================

G = nx.DiGraph()

for _, row in dependency.iterrows():

    G.add_edge(
        row["source"],
        row["target"]
    )

# ==========================
# RCA传播分数
# ==========================

final_scores = {}

for service in scores:

    score = scores[service]

    downstream = list(
        G.successors(service)
    ) if service in G else []

    downstream_score = 0

    for node in downstream:

        downstream_score += scores.get(
            node,
            0
        )

    final_score = (
        score
        + 0.5 * downstream_score
    )

    final_scores[service] = final_score

# ==========================
# 排序
# ==========================

ranking = sorted(
    final_scores.items(),
    key=lambda x: x[1],
    reverse=True
)

print()
print("========= RCA Result =========")
print()

for i, (service, score) in enumerate(ranking[:10]):

    print(
        f"{i+1:2d}. "
        f"{service:25s}"
        f"{score:.2f}"
    )

print()
print(
    "Predicted Root Cause:",
    ranking[0][0]
)

# ==========================
# 保存结果
# ==========================

result_df = pd.DataFrame(
    ranking,
    columns=[
        "service",
        "score"
    ]
)

result_df.to_csv(
    "rca_result.csv",
    index=False
)

# ==========================
# 画图
# ==========================

top = result_df.head(10)

plt.figure(figsize=(10,6))

plt.barh(
    top["service"],
    top["score"]
)

plt.gca().invert_yaxis()

plt.title(
    "Root Cause Ranking"
)

plt.xlabel(
    "RCA Score"
)

plt.tight_layout()

plt.savefig(
    "rca_ranking.png",
    dpi=300
)

plt.show()

print()
print(
    "Saved: rca_result.csv"
)
print(
    "Saved: rca_ranking.png"
)