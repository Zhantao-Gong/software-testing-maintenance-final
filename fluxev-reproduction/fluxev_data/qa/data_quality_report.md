# Data Quality Report

- expected_points_per_series: 2881
- total_rows: 43215
- series_count: 15

## Series Checks

| series_id | points | missing_ratio | strict_5s | train_label_sum | label_sum | pass |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| cartservice_available_replicas | 2881 | 0.0000 | True | 0 | 75 | True |
| cartservice_cpu | 2881 | 0.0014 | True | 0 | 0 | True |
| cartservice_memory | 2881 | 0.0000 | True | 0 | 0 | True |
| cartservice_pod_ready | 2881 | 0.0000 | True | 0 | 75 | True |
| cartservice_restarts | 2881 | 0.0000 | True | 0 | 75 | True |
| frontend_avg_latency_ms | 2881 | 0.0354 | True | 0 | 147 | True |
| frontend_cpu | 2881 | 0.0010 | True | 0 | 0 | True |
| frontend_memory | 2881 | 0.0000 | True | 0 | 0 | True |
| frontend_pod_ready | 2881 | 0.0000 | True | 0 | 0 | True |
| frontend_probe_error_rate | 2881 | 0.0274 | True | 0 | 0 | True |
| frontend_probe_latency_ms | 2881 | 0.0274 | True | 0 | 147 | True |
| frontend_qps | 2881 | 0.0354 | True | 0 | 0 | True |
| recommendationservice_cpu | 2881 | 0.0000 | True | 0 | 147 | True |
| recommendationservice_memory | 2881 | 0.0000 | True | 0 | 0 | True |
| recommendationservice_pod_ready | 2881 | 0.0000 | True | 0 | 0 | True |

## Fault Windows

- cpu_stress: 3 windows
- network_delay: 3 windows
- pod_kill: 3 windows

## Fault Signal Checks

- cartservice_available_replicas: train_mean=1, anomaly_mean=0.76, anomaly_points=75
- cartservice_pod_ready: train_mean=1, anomaly_mean=0.76, anomaly_points=75
- cartservice_restarts: train_mean=0, anomaly_mean=0, anomaly_points=75
- frontend_avg_latency_ms: train_mean=1.96391e-06, anomaly_mean=3.85252e-07, anomaly_points=147
- frontend_probe_latency_ms: train_mean=51.6311, anomaly_mean=1661.5, anomaly_points=93
- recommendationservice_cpu: train_mean=0.0117631, anomaly_mean=0.145108, anomaly_points=147

## Result

PASS
