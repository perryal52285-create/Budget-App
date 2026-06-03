"""Home Assistant integration via the Supervisor proxy to the Core API.

When this add-on runs under Home Assistant, the Supervisor injects a
``SUPERVISOR_TOKEN`` env var and exposes the Core API at ``http://supervisor/core``.
We use only the Python standard library (urllib) so there's no extra dependency
to break HA rebuilds. Every call is best-effort: failures are swallowed and
reported as a boolean so the UI never crashes when HA isn't reachable
(e.g. local dev outside HA).
"""
import json
import os
import urllib.error
import urllib.request

CORE = "http://supervisor/core/api"
TIMEOUT = 5


def _token():
    return os.environ.get("SUPERVISOR_TOKEN", "")


def available():
    return bool(_token())


def _post(path, payload):
    token = _token()
    if not token:
        return False, "no supervisor token (not running under Home Assistant)"
    req = urllib.request.Request(
        f"{CORE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return 200 <= resp.status < 300, f"{resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"http {e.code}"
    except Exception as e:  # network/url errors
        return False, str(e)


def push_sensor(key, state, unit=None, name=None, icon=None):
    """Create/update sensor.perry_budget_<key> in Home Assistant."""
    attrs = {}
    if unit:
        attrs["unit_of_measurement"] = unit
    if name:
        attrs["friendly_name"] = name
    if icon:
        attrs["icon"] = icon
    ok, _ = _post(f"/states/sensor.perry_budget_{key}",
                  {"state": state, "attributes": attrs})
    return ok


def push_sensors(payload):
    """payload: {key: {state, unit?, name?, icon?}}. Returns (ok_count, total)."""
    if not available():
        return 0, len(payload)
    ok = 0
    for key, s in payload.items():
        if push_sensor(key, s["state"], s.get("unit"), s.get("name"), s.get("icon")):
            ok += 1
    return ok, len(payload)


def notify(message, title="Perry Budget", service="notify"):
    """Fire a Home Assistant notify service (default notify.notify)."""
    ok, info = _post(f"/services/notify/{service}", {"message": message, "title": title})
    return ok, info
