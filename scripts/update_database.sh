#!/usr/bin/env bash
set -euo pipefail

HH_URL="${HELLHADES_URL:-https://hellhades.com/raid/tier-list/}"
DB_PATH="${CHAMPION_DB:-champions.db}"
CACHE_DIR="${INTELERIA_CACHE_DIR:-downloaded_pages}"
LIMIT="${LIMIT:-}"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)

cd "$PROJECT_ROOT"

# Ensure the in-repo package is importable without requiring installation.
export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH:-}"

CMD_DOWNLOAD=(python -m inteleria.scraper download --output-dir "$CACHE_DIR" --hellhades-url "$HH_URL")
CMD_BULK=(python -m inteleria.scraper bulk --hellhades-url "$HH_URL" --inteleria-dir "$CACHE_DIR" --db "$DB_PATH")

if [[ -n "$LIMIT" ]]; then
  CMD_DOWNLOAD+=(--limit "$LIMIT")
  CMD_BULK+=(--limit "$LIMIT")
fi

echo "[1/2] Downloading champion pages from Inteleria using HellHades list..."
"${CMD_DOWNLOAD[@]}"

echo "[2/2] Importing champions into database $DB_PATH..."
"${CMD_BULK[@]}"

echo "Database refresh complete."
