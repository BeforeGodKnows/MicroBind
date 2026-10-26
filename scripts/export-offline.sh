#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
dest="${1:-out/offline}"
mkdir -p "$dest"
docker compose config --quiet
mapfile -t images < <(docker compose config --images | sort -u)
docker image save -o "$dest/microbind-images.tar" "${images[@]}"
docker image inspect "${images[@]}" --format '{{.RepoTags}} {{.Id}} {{.Os}}/{{.Architecture}}' > "$dest/images.txt"
(cd "$dest" && sha256sum microbind-images.tar > SHA256SUMS)
echo "Offline image archive: $dest. Transfer source release separately; do not transfer API/model secrets."
