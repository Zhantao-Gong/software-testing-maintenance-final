#!/usr/bin/env bash
set -euo pipefail

OB_NS="${OB_NS:-default}"
OUT_DIR="${OUT_DIR:-fluxev_data}"
LOADGEN_DEPLOYMENT="${LOADGEN_DEPLOYMENT:-loadgenerator}"
PATTERN="${LOAD_PATTERN:-1:low,2:mid,4:high,2:mid,1:low}"

mkdir -p "$OUT_DIR/metadata"
LOAD_LOG="$OUT_DIR/metadata/load_profile.csv"
if [ ! -f "$LOAD_LOG" ]; then
  echo "timestamp_iso,replicas,phase" > "$LOAD_LOG"
fi

while true; do
  IFS=',' read -ra STEPS <<< "$PATTERN"
  for step in "${STEPS[@]}"; do
    replicas="${step%%:*}"
    phase="${step#*:}"
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    kubectl scale "deployment/${LOADGEN_DEPLOYMENT}" -n "$OB_NS" --replicas="$replicas"
    echo "$ts,$replicas,$phase" | tee -a "$LOAD_LOG"
    sleep 60
  done
done
