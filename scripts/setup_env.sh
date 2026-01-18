#!/usr/bin/env bash
set -euo pipefail

# Defaults can be overridden via environment variables
REQ_FILE="${REQ_FILE:-requirements.txt}"

# Prefer the project virtualenv
DEFAULT_VENV_PY=".venv/bin/python"
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1090
  source ".venv/bin/activate"
fi
if [[ -x "$DEFAULT_VENV_PY" ]]; then
  PYTHON="${PYTHON:-$DEFAULT_VENV_PY}"
else
  PYTHON="${PYTHON:-python}"
fi

if [[ ! -f "$REQ_FILE" ]]; then
  echo "Requirement file '$REQ_FILE' not found."
  exit 1
fi

echo "Installing dependencies from '$REQ_FILE' using $PYTHON..."
$PYTHON -m pip install -r "$REQ_FILE"
