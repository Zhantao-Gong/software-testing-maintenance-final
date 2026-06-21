#!/usr/bin/env bash
set -euo pipefail

OB_NS="${OB_NS:-default}"
CHAOS_NS="${CHAOS_NS:-chaos-testing}"
OUT_DIR="${OUT_DIR:-fluxev_data}"
START_AT_ISO="${START_AT_ISO:-}"
mkdir -p "$OUT_DIR/metadata" "$OUT_DIR/chaos"

FAULT_LOG="$OUT_DIR/metadata/fault_windows.csv"
if [ ! -f "$FAULT_LOG" ]; then
  echo "fault_id,fault_type,chaos_kind,chaos_name,target_service,apply_time_iso,end_time_iso,label_start_iso,label_end_iso,duration_seconds,notes" > "$FAULT_LOG"
fi

utc_now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
utc_plus() { date -u -d "$1 + $2 seconds" +"%Y-%m-%dT%H:%M:%SZ"; }
sleep_until_offset() {
  local offset="$1"
  if [ -z "$START_AT_ISO" ]; then
    sleep "$offset"
    return
  fi
  local start_epoch target_epoch now_epoch wait_for
  start_epoch="$(date -u -d "$START_AT_ISO" +%s)"
  target_epoch=$((start_epoch + offset))
  now_epoch="$(date -u +%s)"
  wait_for=$((target_epoch - now_epoch))
  if [ "$wait_for" -gt 0 ]; then sleep "$wait_for"; fi
}

apply_yaml() {
  local file="$1"
  kubectl apply -f "$file"
}

delete_chaos() {
  local kind="$1" name="$2"
  kubectl delete "$kind" "$name" -n "$CHAOS_NS" --ignore-not-found=true
}

run_cpu() {
  local idx="$1" offset="$2" fault_id name file apply end label_end
  fault_id="$(printf "F%03d" "$idx")"
  name="cpu-stress-recommendationservice-$(printf "%03d" "$idx")"
  file="$OUT_DIR/chaos/${name}.yaml"
  sleep_until_offset "$offset"
  apply="$(utc_now)"
  cat > "$file" <<YAML
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: ${name}
  namespace: ${CHAOS_NS}
spec:
  mode: all
  selector:
    namespaces:
      - ${OB_NS}
    labelSelectors:
      app: recommendationservice
  stressors:
    cpu:
      workers: 2
      load: 80
  duration: "3m"
YAML
  apply_yaml "$file"
  end="$(utc_plus "$apply" 180)"
  label_end="$(utc_plus "$apply" 240)"
  echo "$fault_id,cpu_stress,StressChaos,$name,recommendationservice,$apply,$end,$apply,$label_end,180,workers=2 load=80" >> "$FAULT_LOG"
}

run_network() {
  local idx="$1" offset="$2" fault_id name file apply end label_end
  fault_id="$(printf "F%03d" "$idx")"
  name="network-delay-frontend-$(printf "%03d" "$idx")"
  file="$OUT_DIR/chaos/${name}.yaml"
  sleep_until_offset "$offset"
  apply="$(utc_now)"
  cat > "$file" <<YAML
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: ${name}
  namespace: ${CHAOS_NS}
spec:
  action: delay
  mode: all
  selector:
    namespaces:
      - ${OB_NS}
    labelSelectors:
      app: frontend
  delay:
    latency: "300ms"
    correlation: "25"
    jitter: "50ms"
  duration: "3m"
YAML
  apply_yaml "$file"
  end="$(utc_plus "$apply" 180)"
  label_end="$(utc_plus "$apply" 240)"
  echo "$fault_id,network_delay,NetworkChaos,$name,frontend,$apply,$end,$apply,$label_end,180,latency=300ms jitter=50ms" >> "$FAULT_LOG"
}

run_pod_kill() {
  local idx="$1" offset="$2" fault_id name file apply end label_end
  fault_id="$(printf "F%03d" "$idx")"
  name="pod-kill-cartservice-$(printf "%03d" "$idx")"
  file="$OUT_DIR/chaos/${name}.yaml"
  sleep_until_offset "$offset"
  apply="$(utc_now)"
  cat > "$file" <<YAML
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: ${name}
  namespace: ${CHAOS_NS}
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - ${OB_NS}
    labelSelectors:
      app: cartservice
YAML
  apply_yaml "$file"
  end="$(utc_plus "$apply" 5)"
  label_end="$(utc_plus "$apply" 120)"
  echo "$fault_id,pod_kill,PodChaos,$name,cartservice,$apply,$end,$apply,$label_end,0,mode=one" >> "$FAULT_LOG"
  sleep 20
  delete_chaos PodChaos "$name"
}

run_cpu 1 7200
run_cpu 2 7800
run_cpu 3 8400
run_network 4 9000
run_network 5 9600
run_network 6 10200
run_pod_kill 7 10800
run_pod_kill 8 11400
run_pod_kill 9 12000
