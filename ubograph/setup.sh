#!/usr/bin/env bash
# One-shot setup: virtualenv, dependencies, and a .env file for your keys.
set -euo pipefail
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python)
echo "using $PY ($($PY --version))"

$PY -m venv .venv
./.venv/bin/pip install --upgrade pip --quiet
./.venv/bin/pip install -r requirements.txt --quiet
echo "dependencies installed"

if [ ! -f .env ]; then
  cp .env.example .env
  echo
  echo "Created .env — open it and paste your keys after the '=' signs:"
  echo "  OPENSANCTIONS_API_KEY=..."
  echo "  OPENCORPORATES_API_TOKEN=..."
  echo "  ANTHROPIC_API_KEY=...   (optional, enables the open-web fallback)"
  echo
  echo "It runs without any keys — you just get the synthetic demo network."
else
  echo ".env already exists, leaving it alone"
fi

echo
echo "Start it with:  ./.venv/bin/python server.py     then open http://localhost:5000"
