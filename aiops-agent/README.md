# Online-Boutique AIOps Agent

This directory contains an OpenAI-compatible AIOps agent  for the current Online-Boutique deployment.

## What it does

- Polls Prometheus inside Kubernetes.
- Watches Online-Boutique signals for CPU spikes, pod readiness, and cartservice restarts.
- Uses function calling to collect PromQL evidence and pod logs.
- Can restart a deployment through the Kubernetes API when the model has strong evidence.

## Deploy

Create the local conda environment:

```powershell
conda env create -f .\aiops-agent\environment.yml
conda activate online-boutique-aiops
```

Start the existing Minikube cluster first. If the machine is memory constrained, use a smaller profile than the PDF example:

```powershell
minikube start --cpus=3 --memory=4g --registry-mirror="https://docker.m.daocloud.io"
```

Build the image into Minikube's Docker daemon:

```powershell
minikube image build -t aiops-agent:local .\aiops-agent
```

API key step:

```powershell
kubectl create secret generic aiops-agent-secrets `
  -n default `
  --from-literal=OPENAI_API_KEY="YOUR_API_KEY" `
  --from-literal=OPENAI_BASE_URL="https://api.deepseek.com" `
  --from-literal=OPENAI_MODEL="deepseek-v4-pro" `
  --from-literal=REASONING_EFFORT="high" `
  --from-literal=ENABLE_THINKING="true"
```

Then apply the deployment:

```powershell
kubectl apply -f .\aiops-agent\k8s.yaml
kubectl logs -n default deploy/aiops-agent -f
```

If you use the official OpenAI API, omit `OPENAI_BASE_URL`.
