#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
dest="${1:-out/offline}"
(cd "$dest" && sha256sum -c SHA256SUMS)
docker image load -i "$dest/microbind-images.tar"
bash scripts/deploy.sh offline
