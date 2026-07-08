#!/bin/bash
set -e

echo "Building..."
docker compose up -d --build

echo
echo "Done."
docker ps --filter name=fb-marketplace-watcher
