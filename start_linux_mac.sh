#!/usr/bin/env sh
cd "$(dirname "$0")" || exit 1
PYTHONPATH=src python3 -m uvicorn uptimeops.api:app --host 127.0.0.1 --port 8002
