#!/bin/sh
set -eu
if [ ! -f /cache/maven/.microbind-v0.3.4 ]; then
  cp -R /opt/maven-cache/. /cache/maven/
  touch /cache/maven/.microbind-v0.3.4
fi
exec python -m microbind.server.worker --kind verify
