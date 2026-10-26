#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mode="${1:-cn}"
case "$mode" in cn|global) ;; *) echo 'Usage: bash scripts/init.sh cn|global [verify]' >&2; exit 1;; esac
if [[ -e .env ]]; then echo '.env already exists; edit it directly. Nothing overwritten.' >&2; exit 1; fi
umask 077
cp .env.example .env
printf '\nLAB_INTERNAL_KEY=' >> .env
od -An -N32 -tx1 /dev/urandom | tr -d ' \n' >> .env
printf '\n' >> .env
mkdir -p secrets
if [[ ! -f secrets/api_token.txt ]]; then
  od -An -N32 -tx1 /dev/urandom | tr -d ' \n' > secrets/api_token.txt
fi
# Bind-mounted Compose secrets retain file mode. Directory remains private.
chmod 700 secrets
chmod 444 secrets/api_token.txt
if [[ "$mode" == cn ]]; then
  sed -i 's|^PIP_INDEX_URL=.*|PIP_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple|' .env
  sed -i 's|^NPM_REGISTRY=.*|NPM_REGISTRY=https://registry.npmmirror.com|' .env
  sed -i 's|^MAVEN_REPOSITORY=.*|MAVEN_REPOSITORY=https://maven.aliyun.com/repository/public|' .env
fi
if [[ "${2:-}" == verify ]]; then
  sed -i 's/^MICROBIND_VERIFY_ENABLED=.*/MICROBIND_VERIFY_ENABLED=1/;s/^COMPOSE_PROFILES=.*/COMPOSE_PROFILES=verify/' .env
fi
echo 'Created .env and secrets/api_token.txt. Review project name, port and memory limits before deploy.'
