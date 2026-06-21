# Software Testing and Maintenance Final Project

This repository stores the code, test assets, reproduction materials, and deliverables that have been uploaded for the course project.

The descriptions below are based on files currently present in this repository and on README or configuration files already included in those directories.

## Repository Contents

### `Online-Boutique/`

This directory contains the `Online-Boutique` microservice application source tree and deployment assets.

Evidence in this repository:
- the upstream project structure is present, including `src/`, `kubernetes-manifests/`, `kustomize/`, `helm-chart/`, `terraform/`, and `release/`
- `deploy/minikube/kustomization.yaml` exists and pins service images such as `frontend`, `checkoutservice`, and `recommendationservice` to `us-central1-docker.pkg.dev/google-samples/microservices-demo/*:v0.10.5`

### `aiops-agent/`

This directory contains the AIOps agent implementation for the current `Online-Boutique` deployment.

According to [aiops-agent/README.md](./aiops-agent/README.md), the agent:
- polls Prometheus inside Kubernetes
- watches CPU spikes, pod readiness, and cartservice restarts
- uses function calling to collect PromQL evidence and pod logs
- can restart a deployment through the Kubernetes API when it has strong evidence

Relevant files include:
- `veadk_agent.py`
- `k8s.yaml`
- `Dockerfile`
- `environment.yml`
- `requirements.txt`

### `black-box-testing/`

This directory stores black-box testing assets for `Online-Boutique`.

Files currently included:
- `selenium_ide_test/Online-Boutique_.side`
- `selenium_ide_test/test_test1.py`
- `selenium_ide_test/test_test2.py`
- `selenium_ide_test/test_test3.py`
- one JMeter `.jmx` test plan under `jmeter_test/`

These filenames show that the repository includes Selenium IDE assets, exported Python test scripts, and a JMeter test plan.

### `trinityrcl-reproduction/`

This directory stores the TrinityRCL reproduction assets used in this project.

According to [trinityrcl-reproduction/README.md](./trinityrcl-reproduction/README.md), it was imported from:
- `https://github.com/FireEverfly/Microservice-RCA-Experiment/tree/main/TrinityRCL`

Included files:
- `collector.py`
- `rca_v1.py`
- `rca_v2.py`
- `dependency.csv`
- `fault_log.csv`
- `metrics.csv`
- `rca_ranking.png`

### `fluxev-reproduction/`

This directory stores the FluxEV anomaly detection reproduction assets used in this project.

According to [fluxev-reproduction/README.md](./fluxev-reproduction/README.md), it was imported from:
- `https://github.com/liaojunfan/fluxev-anomaly-detection-lab`

Included contents:
- `src/`: preprocessing and experiment scripts
- `fluxev_data/`: dataset, metadata, processed series, QA artifacts, and configuration files

### `scripts/`

This directory contains project scripts used for experiment execution, data export, probing, QA, and dataset construction.

The current filenames are:
- `build_fluxev_dataset.py`
- `export_prometheus.py`
- `preflight.py`
- `qa_report.py`
- `run_experiment.py`
- `run_fault_schedule.py`
- `run_fault_schedule.sh`
- `run_frontend_probe.py`
- `run_periodic_load.ps1`
- `run_periodic_load.py`
- `run_periodic_load.sh`

This description is based on the script names only; no broader behavior is claimed here beyond what those names indicate.

### `deliverables/`

This directory stores deliverable-style outputs that were intentionally uploaded.

Current contents:
- `FluxEV_OnlineBoutique_Reproduction_DataOnly/`
- `aiops_agent_chaos_test/`

According to [deliverables/FluxEV_OnlineBoutique_Reproduction_DataOnly/README.md](./deliverables/FluxEV_OnlineBoutique_Reproduction_DataOnly/README.md), `FluxEV_OnlineBoutique_Reproduction_DataOnly/` is a data delivery package for the FluxEV reproduction and includes:
- `config/`
- `metadata/`
- `raw/`
- `processed/`
- `qa/`
- `chaos/`

The `aiops_agent_chaos_test/` directory currently contains HTML and PNG files under `screenshots/`, including:
- `01_deployment_status.*`
- `04_cpu_stress_summary.*`
- `05_podchaos_detection_report.*`

## Notes On Exclusions

Some files were intentionally not uploaded or are ignored in Git, including:
- local cache directories such as `__pycache__/`
- nested Git metadata backup for `Online-Boutique`
- duplicated deliverable archive files such as `deliverables/*.zip`
- generated black-box testing artifacts such as JMeter HTML report output and `.jtl` result data

## Provenance Notes

Two reproduction directories were imported from external public repositories and then placed into dedicated folders in this repository:
- `trinityrcl-reproduction/`
- `fluxev-reproduction/`

Their source links are preserved in their local `README.md` files.
