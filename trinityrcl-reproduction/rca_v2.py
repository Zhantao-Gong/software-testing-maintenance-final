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

fault_time = pd.Timestamp("2026-06-12 01:25:18")

# 前2分钟正常窗口
normal = metrics[
    metrics["timestamp"] < fault_time
]

# 后1分钟故障窗口
fault = metrics[
    metrics["timestamp"] >= fault_time
]

# ==========================
# 异常检测
# ==========================

services = metrics["service"].unique()

scores = {}

for svc in services:

    n = normal[normal["service"] == svc]
    f = fault[fault["service"] == svc]

    if len(n) == 0 or len(f) == 0:
        continue

    # CPU峰值
    cpu_normal = n["cpu"].mean()
    cpu_std = n["cpu"].std()

    cpu_fault = f["cpu"].max()

    cpu_z = 0

    if cpu_std > 0:
        cpu_z = abs(cpu_fault - cpu_normal) / cpu_std

    # Memory谷值
    mem_normal = n["memory"].mean()
    mem_std = n["memory"].std()

    mem_fault = f["memory"].min()

    mem_z = 0

    if mem_std > 0:
        mem_z = abs(mem_fault - mem_normal) / mem_std

    score = cpu_z + mem_z

    scores[svc] = score

# ==========================
# 构建依赖图
# ==========================

G = nx.DiGraph()

for _, row in dependency.iterrows():

    source = row["source"]
    target = row["target"]

    G.add_edge(source, target)

# ==========================
# Random Walk
# ==========================

total_score = sum(scores.values())

personalization = {}

for svc in G.nodes():

    personalization[svc] = (
        scores.get(svc, 0.01)
        / total_score
    )

rw_scores = nx.pagerank(
    G,
    alpha=0.85,
    personalization=personalization
)

# ==========================
# 综合评分
# ==========================

final_scores = {}

for svc in rw_scores:

    anomaly = scores.get(svc, 0)

    rw = rw_scores[svc]

    final_scores[svc] = anomaly + rw * 100

# ==========================
# 排序
# ==========================

ranking = sorted(
    final_scores.items(),
    key=lambda x: x[1],
    reverse=True
)

print("\n===== RCA Ranking =====\n")

for i, (svc, score) in enumerate(ranking, start=1):

    print(
        f"{i:2d}. {svc:20s} {score:.2f}"
    )

# ==========================
# 可视化
# ==========================

services = [x[0] for x in ranking]
values = [x[1] for x in ranking]

plt.figure(figsize=(10,6))

plt.barh(
    services[::-1],
    values[::-1]
)

plt.xlabel("RCA Score")
plt.title("Root Cause Ranking")

plt.tight_layout()

plt.show()