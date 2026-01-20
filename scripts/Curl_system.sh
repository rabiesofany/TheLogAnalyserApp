#!/usr/bin/env bash
set -euo pipefail

payload=$(python - <<'PY'
import json
from pathlib import Path

log_path = Path("constant_error.txt")
payload = {"error_log": log_path.read_text()}
print(json.dumps(payload))
PY
)

output_file="curl_output.json"
mkdir -p "$(dirname "$output_file")"
curl -N \
  -H "Content-Type: application/json" \
  -d "$payload" \
  http://localhost:8001/classify/stream | tee "$output_file"
