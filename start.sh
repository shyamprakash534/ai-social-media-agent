#!/usr/bin/env sh
set -eu
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit SECRET_KEY and ENCRYPTION_SECRET before using integrations."
fi
docker compose up --build
