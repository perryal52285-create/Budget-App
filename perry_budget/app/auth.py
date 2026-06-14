"""Authentication: PBKDF2 password hashing + DB-backed sessions.

Deliberately dependency-free (stdlib only) so the Alpine add-on image builds
reliably across architectures. Sessions are opaque random tokens stored in the
`sessions` table; the cookie carries only the token.
"""
import hashlib
import hmac
import secrets
import time

from . import db

DEFAULT_PASSWORD = "Test#1"        # throwaway seed; users must change on first login
SESSION_TTL = 30 * 24 * 3600       # 30 days
PBKDF2_ROUNDS = 200_000
COOKIE_NAME = "pb_session"

# --- naive in-memory login throttle (per username+ip) ---------------------
_FAILS: dict[str, list[float]] = {}
_MAX_FAILS = 8
_WINDOW = 15 * 60


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS)
    return salt, dk.hex()


def verify_password(password: str, salt: str, expected_hex: str) -> bool:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS)
    return hmac.compare_digest(dk.hex(), expected_hex)


def throttled(key: str) -> bool:
    now = time.time()
    hits = [t for t in _FAILS.get(key, []) if now - t < _WINDOW]
    _FAILS[key] = hits
    return len(hits) >= _MAX_FAILS


def record_fail(key: str) -> None:
    _FAILS.setdefault(key, []).append(time.time())


def clear_fails(key: str) -> None:
    _FAILS.pop(key, None)


def authenticate(username: str, password: str):
    rows = db.query("SELECT * FROM users WHERE username=?", (username.strip().lower(),))
    if not rows:
        return None
    u = rows[0]
    if not verify_password(password, u["password_salt"], u["password_hash"]):
        return None
    return u


def set_password(user_id: int, password: str) -> None:
    salt, h = hash_password(password)
    db.execute(
        "UPDATE users SET password_salt=?, password_hash=?, must_change_password=0 WHERE id=?",
        (salt, h, user_id))


# --- sessions -------------------------------------------------------------

def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    db.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        (token, user_id, now, now + SESSION_TTL))
    return token


def get_session_user(token: str | None):
    if not token:
        return None
    rows = db.query(
        "SELECT s.expires_at AS _exp, u.* FROM sessions s "
        "JOIN users u ON u.id = s.user_id WHERE s.token=?", (token,))
    if not rows:
        return None
    row = rows[0]
    if row["_exp"] < int(time.time()):
        delete_session(token)
        return None
    return row


def delete_session(token: str | None) -> None:
    if token:
        db.execute("DELETE FROM sessions WHERE token=?", (token,))


def purge_expired() -> None:
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))


def public_user(u) -> dict:
    return {
        "id": u["id"],
        "username": u["username"],
        "display_name": u["display_name"],
        "earner_id": u["earner_id"],
        "theme": u["theme"] or "",
        "must_change_password": bool(u["must_change_password"]),
    }
