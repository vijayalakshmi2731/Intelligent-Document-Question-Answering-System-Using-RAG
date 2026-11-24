"""Stdlib-only authentication: PBKDF2 password hashing + HMAC-signed bearer tokens."""
import base64, hashlib, hmac, json, os, secrets, time
from fastapi import Depends, HTTPException, Header
from .config import DATA_DIR, TOKEN_TTL_SECONDS
from .db import db

_SECRET_FILE = DATA_DIR / ".secret"


def _secret() -> bytes:
    env = os.getenv("DOCQA_SECRET")
    if env:
        return env.encode()
    if not _SECRET_FILE.exists():
        _SECRET_FILE.write_text(secrets.token_hex(32))
        _SECRET_FILE.chmod(0o600)
    return _SECRET_FILE.read_text().encode()


def hash_password(password: str, salt: str | None = None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return h.hex(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt)[0], hashed)


def make_token(user_id: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"uid": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}).encode()).decode()
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def parse_token(token: str) -> int | None:
    try:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data["uid"] if data["exp"] > time.time() else None
    except Exception:
        return None


def current_user(authorization: str = Header(default="")) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    uid = parse_token(token) if token else None
    if uid is None:
        raise HTTPException(401, "Not authenticated")
    with db() as c:
        row = c.execute("SELECT id,email,name,role,active,bio,created_at FROM users WHERE id=?", (uid,)).fetchone()
    if not row or not row["active"]:
        raise HTTPException(401, "Account unavailable")
    return dict(row)


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    return user
