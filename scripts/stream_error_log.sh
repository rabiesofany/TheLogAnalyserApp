#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="sample_data/constant_error.txt"

if [[ ! -f "$LOG_FILE" ]]; then
  echo "Log file $LOG_FILE not found."
  exit 1
fi

echo "Streaming $LOG_FILE to /classify/stream..."

PAYLOAD="$(python - <<'PY'
import json, pathlib
path = pathlib.Path("sample_data/constant_error.txt")
print(json.dumps({"error_log": path.read_text()}))
PY
)"

curl -N -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  http://localhost:8000/classify/stream
