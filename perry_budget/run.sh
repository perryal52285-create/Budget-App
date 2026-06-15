#!/usr/bin/with-contenv bashio
# Perry Budget add-on entrypoint

export DATA_DIR="/data"

echo "[perry_budget] starting on :8099 (ingress)"
# --proxy-headers so the app sees the real scheme (https) behind HA ingress and
# a Cloudflare tunnel -> session cookies are marked Secure when appropriate.
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8099 \
  --proxy-headers --forwarded-allow-ips='*'
