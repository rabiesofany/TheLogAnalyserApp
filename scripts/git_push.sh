#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"commit message\""
  exit 1
fi

COMMIT_MESSAGE="$*"

if [[ -z "$(git status --porcelain)" ]]; then
  echo "No changes to commit."
  exit 0
fi

git add -A
git commit -m "$COMMIT_MESSAGE"
git push
