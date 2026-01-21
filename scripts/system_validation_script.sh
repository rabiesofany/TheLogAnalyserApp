#!/usr/bin/env bash
set -euo pipefail

csv_path="${1:-./plc_log_samples.csv}"
output_dir="${2:-logs/system_validation}"

mkdir -p "$output_dir"

CSV_PATH="$csv_path" OUTPUT_DIR="$output_dir" python - <<'PY'
import csv
import os
import json
import subprocess
import sys

csv_path = os.environ["CSV_PATH"]
output_dir = os.environ["OUTPUT_DIR"]

def run_curl(payload, output_file):
    proc = subprocess.Popen(
        [
            "curl",
            "-N",
            "-H", "Content-Type: application/json",
            "-d", payload,
            "http://localhost:8001/classify"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    with open(output_file, "wb") as out:
        while True:
            chunk = proc.stdout.read(4096)
            if not chunk:
                break
            out.write(chunk)
            sys.stdout.buffer.write(chunk)
    proc.wait()
    if proc.returncode != 0:
        raise SystemExit(f"curl exited with {proc.returncode}")

with open(csv_path, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        sample_id = row.get("sample_id") or "unknown"
        payload = json.dumps({"error_log": row["raw_log"]})
        output_file = os.path.join(output_dir, f"sample_{sample_id}.json")
        print(f"Running sample {sample_id} -> {output_file}", file=sys.stderr)
        run_curl(payload, output_file)
PY
