#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=".env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Environment file '$ENV_FILE' not found. Copy .env.example or create .env first."
  exit 1
fi

# Export environment variables so the curl command can read the API key
set -a
source "$ENV_FILE"
set +a

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ANTHROPIC_API_KEY not set in $ENV_FILE"
  exit 1
fi

echo "Listing available Anthropic models for key in $ENV_FILE..."
curl https://api.anthropic.com/v1/models \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
