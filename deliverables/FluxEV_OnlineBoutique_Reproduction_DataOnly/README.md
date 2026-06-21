# FluxEV Online Boutique Data Collection

本目录是用于 FluxEV 算法复现的数据交付包。数据来自 Online Boutique 微服务系统，在周期负载下采集 Prometheus 指标和主动探测指标，并通过 Chaos Mesh 注入 CPU、网络延迟、Pod kill 三类故障。

## 1. 数据概览

- 系统：Online Boutique
- Kubernetes namespace：`default`
- Chaos Mesh namespace：`chaos-testing`
- Prometheus 查询方式：HTTP API `query_range`
- 采样频率：5 秒
- 最终时间网格：所有 processed 序列统一为 `T0 + n * 5s`
- 每条序列点数：2881
- 序列数量：15
- 总表行数：43216 行，包括表头
- QA 结果：`PASS`

实验时间均为 UTC：

| 阶段 | 时间范围 | 时长 | 说明 |
|---|---|---:|---|
| warm-up | 2026-06-13T17:07:03Z ~ 2026-06-13T17:17:03Z | 10 min | 预热，不进入最终 FluxEV 数据 |
| train/init | 2026-06-13T17:17:03Z ~ 2026-06-13T19:17:03Z | 120 min | 无故障，`is_test=0`，`label=0` |
| test | 2026-06-13T19:17:03Z ~ 2026-06-13T21:17:03Z | 120 min | 注入 9 次故障，`is_test=1` |

周期负载：

| 阶段 | loadgenerator replicas | 持续时间 |
|---|---:|---:|
| low | 1 | 60s |
| mid | 2 | 60s |
| high | 4 | 60s |
| mid | 2 | 60s |
| low | 1 | 60s |

一个完整负载周期为 300 秒。采样间隔 5 秒，因此周期点数 `l = 300 / 5 = 60`。

FluxEV 复现建议参数：

| 参数 | 值 | 含义 |
|---|---:|---|
| `s` | 10 | FluxEV fluctuation extraction 参数 |
| `p` | 5 | second-step smoothing 使用的周期数 |
| `d` | 2 | 周期位置漂移容忍参数 |
| `l` | 60 | 一个负载周期内的采样点数 |
| `q` | 0.001 | SPOT/POT 阈值相关参数 |
| train length | 1440 | 2 小时训练段点数 |
| estimated `a` | 262 | `2s + d + l(p - 1)` |
| estimated `k` | 1178 | `1440 - 262` |

## 2. 目录结构

```text
fluxev_data/
  README.md
  config/
    experiment_config.yaml
    metrics_config.yaml
  metadata/
    fault_windows.csv
    load_profile.csv
    series_catalog.csv
    series_fault_map.csv
  raw/
    prometheus/*.csv
    probe/frontend_probe.csv
  processed/
    fluxev_total.csv
    series/*.csv
  qa/
    data_quality_report.md
    preview_plots/*.png
  chaos/*.yaml
```

如果只需要跑算法，优先使用：

- `processed/fluxev_total.csv`
- `processed/series/*.csv`
- `metadata/fault_windows.csv`
- `metadata/series_fault_map.csv`
- `config/experiment_config.yaml`

## 3. 核心文件说明

### `processed/fluxev_total.csv`

FluxEV 算法复现主输入文件。所有 KPI 序列合并在一个 CSV 中，每一行是一条单变量 KPI 在某个时间点的值。

字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `timestamp` | integer | Unix seconds，UTC 时间戳。所有序列统一到同一个 5s 网格。 |
| `value` | float 或 `NaN` | 原始指标值，未做标准化。缺失点为 `NaN`。 |
| `label` | 0/1 | 异常标签。训练段全为 0；测试段按故障窗口和序列映射打标。 |
| `KPI ID` | string | 单变量序列 ID，例如 `recommendationservice_cpu`。 |
| `missing` | 0/1 | 该时间点原始数据是否缺失。缺失为 1。 |
| `is_test` | 0/1 | 训练段为 0，测试段为 1。 |
| `fault_type` | string | `normal`、`cpu_stress`、`network_delay` 或 `pod_kill`。 |
| `fault_id` | string | 故障编号，例如 `F001`。正常点为空。 |

注意：FluxEV 是单变量检测算法，复现时应按 `KPI ID` 分组，每次输入一条序列，不要把多条 KPI 拼成多变量输入。

### `processed/series/*.csv`

每条 KPI 的独立文件，字段和 `fluxev_total.csv` 相同。用于单独运行某个 KPI 或单独画图。

包含 15 条序列：

| KPI ID | 来源 | 主要用途 |
|---|---|---|
| `recommendationservice_cpu` | Prometheus/cAdvisor | CPU stress 主评估序列 |
| `recommendationservice_memory` | Prometheus/cAdvisor | recommendationservice 内存辅助序列 |
| `recommendationservice_pod_ready` | Prometheus/kube-state | recommendationservice Ready 辅助序列 |
| `frontend_probe_latency_ms` | 主动探测 | Network delay 主评估序列 |
| `frontend_probe_error_rate` | 主动探测 | frontend 探测错误率 |
| `frontend_avg_latency_ms` | Prometheus 应用指标 | frontend 平均请求延迟辅助序列 |
| `frontend_qps` | Prometheus 应用指标 | frontend 请求速率辅助序列 |
| `frontend_cpu` | Prometheus/cAdvisor | frontend CPU 辅助序列 |
| `frontend_memory` | Prometheus/cAdvisor | frontend 内存辅助序列 |
| `frontend_pod_ready` | Prometheus/kube-state | frontend Ready 辅助序列 |
| `cartservice_restarts` | Prometheus/kube-state | Pod kill 主评估序列之一 |
| `cartservice_pod_ready` | Prometheus/kube-state | Pod kill 主评估序列之一 |
| `cartservice_available_replicas` | Prometheus/kube-state | Pod kill 主评估序列之一 |
| `cartservice_cpu` | Prometheus/cAdvisor | cartservice CPU 辅助序列 |
| `cartservice_memory` | Prometheus/cAdvisor | cartservice 内存辅助序列 |

### `metadata/fault_windows.csv`

记录 9 次真实故障注入窗口，是生成 `label` 的主要依据。

字段：

| 字段 | 含义 |
|---|---|
| `fault_id` | 故障编号，`F001` 到 `F009`。 |
| `fault_type` | 故障类型：`cpu_stress`、`network_delay`、`pod_kill`。 |
| `chaos_kind` | Chaos Mesh CR 类型：`StressChaos`、`NetworkChaos`、`PodChaos`。 |
| `chaos_name` | Chaos Mesh 对象名。 |
| `target_service` | 故障注入目标服务。 |
| `apply_time_iso` | Chaos 对象创建/生效时间，UTC。 |
| `end_time_iso` | 故障结束时间，UTC。 |
| `label_start_iso` | 异常标签窗口开始时间。 |
| `label_end_iso` | 异常标签窗口结束时间。 |
| `duration_seconds` | 故障持续秒数。Pod kill 是瞬时事件，因此为 0。 |
| `notes` | 注入参数说明。 |

### `metadata/series_fault_map.csv`

定义哪些序列在对应故障窗口内被标为异常。不是所有 KPI 都在所有故障窗口打 `label=1`。

例如：

- `cpu_stress` 只主要标注 `recommendationservice_cpu`
- `network_delay` 标注 `frontend_probe_latency_ms` 和 `frontend_avg_latency_ms`
- `pod_kill` 标注 `cartservice_restarts`、`cartservice_pod_ready`、`cartservice_available_replicas`

### `metadata/series_catalog.csv`

KPI 目录表。记录每条序列的来源、服务、指标类别、单位、是否主评估序列和备注。

### `metadata/load_profile.csv`

记录实验期间负载发生变化的时间点，即 loadgenerator replicas 的周期变化。用于解释正常周期波动。

字段：

| 字段 | 含义 |
|---|---|
| `timestamp_iso` | UTC 时间 |
| `replicas` | loadgenerator 副本数 |
| `phase` | 负载阶段：`low`、`mid`、`high` |

### `raw/prometheus/*.csv`

Prometheus 原始导出文件。每个 KPI 一个 CSV，已经重建到 5s 时间网格，但尚未合并成 FluxEV 总表。

字段：

| 字段 | 含义 |
|---|---|
| `timestamp_iso` | UTC ISO 时间 |
| `timestamp_unix` | Unix seconds |
| `series_id` | KPI ID |
| `value` | 指标值 |
| `missing` | 是否缺失 |

### `raw/probe/frontend_probe.csv`

主动探测 frontend 得到的原始数据。每 5 秒请求 frontend 3 次，记录平均延迟和错误率。

序列：

- `frontend_probe_latency_ms`
- `frontend_probe_error_rate`

### `qa/data_quality_report.md`

数据质量报告。检查内容包括：

- 每条序列是否为 2881 个点
- 是否严格 5s 间隔
- missing ratio
- 训练段是否无异常标签
- 三类故障是否各 3 个窗口
- 主评估序列在故障窗口内是否有可见变化

本次结果为 `PASS`。

### `qa/preview_plots/*.png`

关键序列预览图。红色淡背景为标注异常窗口，蓝线为 KPI 值。

文件：

- `recommendationservice_cpu.png`
- `frontend_probe_latency_ms.png`
- `frontend_avg_latency_ms.png`
- `cartservice_restarts.png`
- `cartservice_pod_ready.png`

### `chaos/*.yaml`

实际用于 Chaos Mesh 注入的 YAML 文件。用于复现实验环境或写报告说明故障参数。

## 4. 故障注入说明

测试段共注入 3 类故障，每类重复 3 次，共 9 次。

### 4.1 CPU stress

- 目标服务：`recommendationservice`
- Chaos 类型：`StressChaos`
- 参数：`workers=2`，`load=80`
- 每次持续：3 分钟
- 标签窗口：故障 3 分钟 + 60 秒尾部影响，共约 4 分钟
- 主观察序列：`recommendationservice_cpu`

| fault_id | 时间 UTC | 目标 |
|---|---|---|
| F001 | 2026-06-13T19:17:03Z ~ 2026-06-13T19:20:03Z | recommendationservice |
| F002 | 2026-06-13T19:27:03Z ~ 2026-06-13T19:30:03Z | recommendationservice |
| F003 | 2026-06-13T19:37:03Z ~ 2026-06-13T19:40:03Z | recommendationservice |

### 4.2 Network delay

- 目标服务：`frontend`
- Chaos 类型：`NetworkChaos`
- 参数：`latency=300ms`，`jitter=50ms`，`correlation=25`
- 每次持续：3 分钟
- 标签窗口：故障 3 分钟 + 60 秒尾部影响，共约 4 分钟
- 主观察序列：`frontend_probe_latency_ms`、`frontend_avg_latency_ms`

| fault_id | 时间 UTC | 目标 |
|---|---|---|
| F004 | 2026-06-13T19:47:03Z ~ 2026-06-13T19:50:03Z | frontend |
| F005 | 2026-06-13T19:57:03Z ~ 2026-06-13T20:00:03Z | frontend |
| F006 | 2026-06-13T20:07:03Z ~ 2026-06-13T20:10:03Z | frontend |

### 4.3 Pod kill

- 目标服务：`cartservice`
- Chaos 类型：`PodChaos`
- 动作：`pod-kill`
- 每次为瞬时 kill
- 标签窗口：约 2 分钟，用于覆盖 Pod 重建和 Ready 状态恢复
- 主观察序列：`cartservice_restarts`、`cartservice_pod_ready`、`cartservice_available_replicas`

| fault_id | 时间 UTC | 目标 |
|---|---|---|
| F007 | 2026-06-13T20:17:03Z | cartservice |
| F008 | 2026-06-13T20:27:03Z | cartservice |
| F009 | 2026-06-13T20:37:03Z | cartservice |

每类故障重复 3 次的目的：

- 给算法提供多个连续异常窗口，而不是单个偶然事件
- 覆盖周期负载下的不同时间位置
- 降低单次故障注入不明显带来的风险
- 便于计算段级检测效果

## 5. 标签生成规则

标签由 `metadata/fault_windows.csv` 和 `metadata/series_fault_map.csv` 共同决定。

规则：

1. 训练段 `2026-06-13T17:17:03Z ~ 2026-06-13T19:17:03Z` 全部 `label=0`。
2. 测试段只有 `series_fault_map.csv` 中列出的主评估序列会在对应故障窗口内标为 `label=1`。
3. 不相关序列即使处于某个故障时间窗口，也不强行标为异常。
4. 无故障点为 `fault_type=normal`，`fault_id` 为空。

## 6. 算法复现建议

使用 `processed/fluxev_total.csv`：

1. 按 `KPI ID` 分组。
2. 对每个 KPI 单独取 `timestamp,value,label,missing,is_test`。
3. 使用 `is_test=0` 的前 1440 个点作为初始化/训练段。
4. 从 `is_test=1` 开始做在线检测评估。
5. 缺失值可按 FluxEV 论文策略做 preprocessing，短缺失线性插值，长缺失按周期补偿。

重点复现序列：

- CPU 故障：`recommendationservice_cpu`
- 网络延迟故障：`frontend_probe_latency_ms`
- Pod kill 故障：`cartservice_pod_ready`、`cartservice_available_replicas`

`cartservice_restarts` 也已标注为 Pod kill 主序列，但本次 QA 中它的窗口均值变化不如 Ready/available replicas 明显，建议作为辅助观察。

## 7. 注意事项

- 所有时间均为 UTC。
- `value` 保留原始量纲，未做标准化。
- `missing=1` 表示该时间点原始采集缺失，不代表该行被删除。
- `frontend_avg_latency_ms` 来自应用 Prometheus 指标，数值可能因原始指标尺度较小而不如 `frontend_probe_latency_ms` 直观。
- `raw/` 是原始导出，`processed/` 是算法复现应优先使用的数据。
- `metadata/*.log`、`*.pid`、`__pycache__` 不属于算法复现必要文件，交付包中不会包含它们。

## 8. 本交付包不包含的内容

本包面向 FluxEV 算法复现，只包含数据、标签、配置、QA 报告、预览图和 Chaos YAML 记录；不包含数据采集脚本、运行日志、pid 文件或 Python 缓存。
