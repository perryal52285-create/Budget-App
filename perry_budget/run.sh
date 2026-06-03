#!/usr/bin/with-contenv bashio
# Perry Budget add-on entrypoint

export DATA_DIR="/data"

echo "[perry_budget] starting on :8099 (ingress)"
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8099
