#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env && -f secrets/api_token.txt ]] || { echo 'Run bash scripts/init.sh first.' >&2; exit 1; }
docker compose version
docker compose config --quiet
mode="${1:-online}"
if [[ "$mode" == offline ]]; then
  docker compose up -d --no-build --pull never
elif [[ "$mode" == online ]]; then
  docker compose build api frontend
  if docker compose config --services | grep -qx verifier; then docker compose build verifier; fi
  docker compose up -d --no-build --pull never
else echo 'Usage: bash scripts/deploy.sh online|offline' >&2; exit 1; fi
docker compose ps
echo 'Log in with the token in secrets/api_token.txt; see docs/DEPLOYMENT.md for SSH forwarding.'
