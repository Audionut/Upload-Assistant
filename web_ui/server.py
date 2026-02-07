# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# ruff: noqa: I001
import ast
import base64
import contextlib
import hashlib
import hmac
import json
import time
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
import traceback
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict, Union, cast

import pyotp
from flask import Flask, Response, g, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import safe_join
from werkzeug.middleware.proxy_fix import ProxyFix

import web_ui.auth as auth_mod
from flask_session import Session

sys.path.insert(0, str(Path(__file__).parent.parent))

# Helper to convert ANSI -> HTML using Rich (optional)
try:
    from src.console import ansi_to_html
except Exception:
    ansi_to_html = None

from src.console import console

cfg_dir = auth_mod.get_config_dir()
cfg_dir.mkdir(parents=True, exist_ok=True)

# Access logging helper
try:
    from web_ui.access_log import AccessLogger
except Exception:
    AccessLogger = None

access_logger = AccessLogger(cfg_dir) if AccessLogger is not None else None

# Helper: simple file-backed config store under the auth config dir. Values
# are stored as raw text. This replaces OS keyring usage and allows Docker
# and non-Docker deployments to persist credentials via the configured
# persistent config mechanism.
def _cfg_file_path(name: str) -> Path:
    return cfg_dir / name


def _cfg_read(name: str) -> Optional[str]:
    p = _cfg_file_path(name)
    with contextlib.suppress(Exception):
        if p.exists():
            return p.read_text(encoding="utf-8")
    return None


def _cfg_write(name: str, value: str) -> None:
    p = _cfg_file_path(name)
    with contextlib.suppress(Exception):
        p.write_text(value, encoding="utf-8")


def _cfg_delete(name: str) -> None:
    p = _cfg_file_path(name)
    with contextlib.suppress(Exception):
        if p.exists():
            p.unlink()


def _sanitize_relpath(rel: str) -> str:
    """Sanitize a relative path coming from user input.

    Splits the path into components, rejects empty/parent segments and
    validates each component for unsafe/control characters. Returns a
    path using the OS separator. Raises ValueError for unsafe input.
    """
    if rel == "" or rel == ".":
        return rel

    if "\x00" in rel:
        raise ValueError("Invalid path")

    # Split on both forward and backward slashes to support Windows/posix
    parts = re.split(r"[\\/]+", rel)
    clean_parts: list[str] = []
    for p in parts:
        if not p or p == "." or p == "..":
            raise ValueError("Invalid path component")
        # Reject NUL/control characters which are unsafe in file names.
        if re.search(r"[\x00-\x1f]", p):
            raise ValueError("Invalid path component")
        # Reject path-separator characters
        if '/' in p or '\\' in p:
            raise ValueError("Invalid path component")

        clean_parts.append(p)

    return os.sep.join(clean_parts)


def _assert_safe_resolved_path(path: str) -> None:
    """Assert that a resolved path is safe and within configured browse roots.

    Raises ValueError if the path is unsafe. This provides an explicit,
    local check at call sites to satisfy static analysis tools.
    """
    if not path or "\x00" in path:
        raise ValueError("Invalid path")

    # Ensure absolute and normalized
    abs_path = os.path.abspath(path)
    real_path = os.path.realpath(abs_path)

    roots = _get_browse_roots()
    if not roots:
        # If no roots configured, be conservative and disallow.
        raise ValueError("Browsing is not configured")

    allowed = False
    for root in roots:
        root_abs = os.path.abspath(root)
        root_real = os.path.realpath(root_abs)
        safe_root_prefix = root_real if root_real.endswith(os.sep) else (root_real + os.sep)
        if real_path == root_real or real_path.startswith(safe_root_prefix):
            allowed = True
            break

    if not allowed:
        raise ValueError("Path outside allowed roots")

Flask = cast(Any, Flask)
Response = cast(Any, Response)
jsonify = cast(Any, jsonify)
render_template = cast(Any, render_template)
request = cast(Any, request)
CORS_fn = cast(Any, CORS)
safe_join = cast(Any, safe_join)

app: Any = Flask(__name__)
# Ensure Flask sees the proxy headers (Host, X-Forwarded-Proto, X-Forwarded-For)
# so `request.host_url` and related values reflect the external URL when
# running behind a reverse proxy (eg. Caddy). Adjust the `x_*` values if
# there are multiple proxies in front of the app.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=2, x_host=1)
# Load stable session secret (env/file/SECRET_KEY fallback). Use bytes directly.

session_secret = auth_mod.load_session_secret()
app.secret_key = session_secret

# Configure server-side filesystem sessions (persisted under config dir)
cfg_dir = auth_mod.get_config_dir()
sess_dir = cfg_dir / "sessions"
sess_dir.mkdir(parents=True, exist_ok=True)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
# Ensure permanent sessions (when set) expire after 30 days to match remember-me cookie
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

# Prefer CacheLib's FileSystemCache when available. Set `SESSION_CACHELIB`
# to an instance of `FileSystemCache` so Flask-Session uses CacheLib's
# implementation and avoids the deprecated `SESSION_FILE_DIR` path.
_session_cache = None
try:
    from cachelib.file import FileSystemCache  # type: ignore

    with contextlib.suppress(Exception):
        _session_cache = FileSystemCache(str(sess_dir))
except Exception:
    _session_cache = None

if _session_cache is not None:
    # Use CacheLib-backed cache for sessions (preferred)
    app.config["SESSION_CACHELIB"] = _session_cache
    try:
        from flask_session.cachelib import CacheLibSessionInterface  # type: ignore

        # Set the session interface directly to the CacheLib-backed implementation
        # Pass the cache as the `client` kwarg to avoid binding it to the
        # positional `app` parameter of the constructor.
        app.session_interface = CacheLibSessionInterface(client=_session_cache)
    except Exception:
        # If for some reason the adapter class isn't available, fall back
        # to letting Flask-Session initialize via Session(app).
        Session(app)
else:
    # Fallback for environments without CacheLib: keep legacy file-dir config
    app.config["SESSION_FILE_DIR"] = str(sess_dir)
    Session(app)

# Initialize Flask-Limiter for rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

def _rate_limit_key_func():
    """Rate limit key function that considers authentication status."""
    if _is_authenticated():
        return f"auth:{get_remote_address()}"
    return f"unauth:{get_remote_address()}"


# Encrypted session helpers --------------------------------------------------
def _derive_aes_key() -> Optional[bytes]:
    try:
        return auth_mod.derive_aes_key(session_secret)
    except Exception:
        return None


def _load_session_dict() -> dict:
    try:
        enc = session.get("enc")
        if not enc:
            return {}
        key = _derive_aes_key()
        if not key:
            return {}
        dec = auth_mod.decrypt_text(key, enc)
        if not dec:
            return {}
        return json.loads(dec)
    except Exception:
        return {}


def _commit_session_dict(d: dict) -> None:
    try:
        key = _derive_aes_key()
        if not key:
            return
        raw = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
        enc = auth_mod.encrypt_text(key, raw)
        session["enc"] = enc
    except Exception:
        pass


def _session_get(key: str, default: Any = None) -> Any:
    return _load_session_dict().get(key, default)


def _session_set(key: str, value: Any) -> None:
    d = _load_session_dict()
    d[key] = value
    _commit_session_dict(d)


def _session_pop(key: str, default: Any = None) -> Any:
    d = _load_session_dict()
    val = d.pop(key, default)
    _commit_session_dict(d)
    return val


# IP control helpers --------------------------------------------------
def _get_ip_whitelist() -> list[str]:
    """Get the list of whitelisted IPs."""
    try:
        path = cfg_dir / "webui_auth.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            val = data.get("ip_whitelist")
            if isinstance(val, list):
                return val
    except Exception:
        pass
    return []


def _set_ip_whitelist(ips: list[str]) -> None:
    """Set the list of whitelisted IPs."""
    try:
        path = cfg_dir / "webui_auth.json"
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8")) or {}
            except Exception:
                return
        data["ip_whitelist"] = ips
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _get_ip_blacklist() -> list[str]:
    """Get the list of blacklisted IPs."""
    try:
        path = cfg_dir / "webui_auth.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            val = data.get("ip_blacklist")
            if isinstance(val, list):
                return val
    except Exception:
        pass
    return []


def _set_ip_blacklist(ips: list[str]) -> None:
    """Set the list of blacklisted IPs."""
    try:
        path = cfg_dir / "webui_auth.json"
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8")) or {}
            except Exception:
                return
        data["ip_blacklist"] = ips
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _get_ip_failures() -> dict[str, list[int]]:
    """Get the dict of IP failure timestamps.

    Returns a mapping of `ip -> list[int]` (UNIX timestamps). For backward
    compatibility any integer legacy counts are converted into recent
    timestamps so they behave as recent failures.
    """
    try:
        path = cfg_dir / "webui_auth.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            val = data.get("ip_failures")
            if isinstance(val, dict):
                now = int(time.time())
                out: dict[str, list[int]] = {}
                for k, v in val.items():
                    if isinstance(v, list):
                        # Coerce list members to ints and filter invalid
                        try:
                            out[k] = [int(x) for x in v]
                        except Exception:
                            out[k] = []
                    elif isinstance(v, int):
                        # Legacy count: treat as recent failures
                        out[k] = [now] * v
                return out
    except Exception:
        pass
    return {}


def _set_ip_failures(failures: dict[str, list[int]]) -> None:
    """Set the dict of IP failure timestamps (ip -> list[timestamps])."""
    try:
        path = cfg_dir / "webui_auth.json"
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8")) or {}
            except Exception:
                return
        data["ip_failures"] = failures
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _is_ip_allowed(ip: str) -> bool:
    """Check if an IP is allowed based on whitelist/blacklist."""
    whitelist = _get_ip_whitelist()
    blacklist = _get_ip_blacklist()

    # Blacklist takes absolute precedence. If an IP is blacklisted,
    # deny it even if it's present in the whitelist.
    if ip in blacklist:
        return False

    # If whitelist is set, only allow IPs in whitelist.
    if whitelist:
        return ip in whitelist

    # Otherwise, allow (not blacklisted).
    return True


def _handle_failed_auth(ip: str) -> None:
    """Handle failed authentication attempt. Track failures and blacklist if too many."""
    # Configuration: threshold and window (seconds)
    FAILURE_THRESHOLD = 5
    FAILURE_WINDOW = 300  # 5 minutes

    failures = _get_ip_failures()
    now = int(time.time())
    pts = failures.get(ip, [])
    # Prune old entries outside the window and append current timestamp
    pts = [t for t in pts if t >= now - FAILURE_WINDOW]
    pts.append(now)
    failures[ip] = pts
    _set_ip_failures(failures)

    # Blacklist if threshold exceeded within window
    if len(pts) >= FAILURE_THRESHOLD:
        blacklist = _get_ip_blacklist()
        if ip not in blacklist:
            blacklist.append(ip)
            _set_ip_blacklist(blacklist)


def _is_authenticated() -> bool:
    if getattr(g, "authenticated", False):
        return True
    return bool(_session_get("authenticated", False))


def _cleanup_duplicate_sessions(username: str) -> None:
    """Remove other session files that belong to `username` to keep a
    single session file per user. This inspects files under the configured
    `SESSION_FILE_DIR` and attempts to decrypt stored `enc` payloads using
    the current derived AES key.
    """
    try:
        key = _derive_aes_key()
        if not key:
            return
        current_enc = session.get("enc")
        sdir = Path(app.config.get("SESSION_FILE_DIR", ""))
        if not sdir or not sdir.exists():
            return
        for p in sdir.iterdir():
            if not p.is_file():
                continue
            # Suppress per-file errors and continue processing other files.
            # Use contextlib.suppress to avoid a try/except/continue pattern
            # that Bandit flags (B112).
            with contextlib.suppress(Exception):
                txt = p.read_text(encoding="utf-8", errors="ignore").strip()
                candidate_enc = None
                # If file is JSON with an 'enc' key, use that
                try:
                    j = json.loads(txt)
                    if isinstance(j, dict) and isinstance(j.get("enc"), str):
                        candidate_enc = j.get("enc")
                except Exception:
                    # Not JSON - treat whole file as enc payload
                    candidate_enc = txt

                if not candidate_enc:
                    continue

                # Skip the file that matches our current session payload
                if current_enc and candidate_enc == current_enc:
                    continue

                dec = None
                try:
                    dec = auth_mod.decrypt_text(key, candidate_enc)
                except Exception:
                    dec = None

                if not dec:
                    continue

                try:
                    obj = json.loads(dec)
                    u = obj.get("username")
                except Exception:
                    u = None

                if u and u == username:
                    # Remove stale session file
                    with contextlib.suppress(Exception):
                        p.unlink()
    except Exception:
        pass

# Supported video file extensions for WebUI file browser
SUPPORTED_VIDEO_EXTS = {'.mkv', '.mp4', '.ts'}

# Supported description file extensions for WebUI description file browser
SUPPORTED_DESC_EXTS = {'.txt', '.nfo', '.md'}

# Lock to prevent concurrent in-process uploads (avoids cross-session interference)
inproc_lock = threading.Lock()

# Runtime browse roots (set by upload.py when starting web UI)
_runtime_browse_roots: Optional[str] = None

# Runtime flags and stored totp
saved_totp_secret: Optional[str] = None

# CSRF helpers ---------------------------------------------------------------
def _verify_csrf_header() -> bool:
    """Verify incoming request contains a valid CSRF token.

    Checks the `X-CSRF-Token` header first, then falls back to JSON/form field
    named `csrf_token` for compatibility with clients that embed it in the body.
    """
    try:
        # If client used a bearer token, treat that as sufficient for CSRF-safe API usage
        auth_header = (request.headers.get("Authorization") or "").strip()
        if auth_header.lower().startswith("bearer "):
            b = auth_header.split(None, 1)[1].strip()
            if b and _verify_api_token(b):
                return True

        token = _session_get("csrf_token")
        if not token:
            return False
        header = request.headers.get("X-CSRF-Token")
        if not header:
            data = None
            try:
                data = request.get_json(silent=True) or {}
            except Exception:
                data = {}
            header = (data or {}).get("csrf_token") or request.form.get("csrf_token")
        if not header:
            return False
        return hmac.compare_digest(str(token), str(header))
    except Exception:
        return False


def _verify_same_origin() -> bool:
    """Require same-origin via Origin or Referer header.

    Returns True if the request appears to be same-origin against the
    server's `request.host_url`. If an Origin header is present it must
    exactly match the host_url; otherwise falls back to checking the
    Referer prefix. Absence or mismatch results in False.
    """
    try:
        # Prefer comparing the origin/referer host:port (netloc) to the
        # request host. This is scheme-insensitive and avoids failures
        # when proxies/Cloudflare terminate TLS or don't forward the
        # original scheme.
        from urllib.parse import urlparse

        origin = request.headers.get("Origin")
        if origin:
            try:
                parsed = urlparse(origin)
                if parsed.netloc:
                    return parsed.netloc == request.host
            except Exception:
                pass
            # Fallback to strict host_url match if parsing fails
            host_url = (request.host_url or "").rstrip("/") + "/"
            return origin.rstrip("/") + "/" == host_url

        referer = request.headers.get("Referer") or request.headers.get("Referrer")
        if referer:
            try:
                parsed = urlparse(referer)
                if parsed.netloc:
                    return parsed.netloc == request.host
            except Exception:
                pass
            host_url = (request.host_url or "").rstrip("/") + "/"
            return referer.startswith(host_url)

        return False
    except Exception:
        return False


# Load TOTP secret
try:
    saved_totp_secret = auth_mod.get_totp_secret()
except Exception:
    saved_totp_secret = None

# Persistent cookie key helpers -------------------------------------------------
def _get_persistent_cookie_key() -> Optional[bytes]:
    """Return a bytes key used to HMAC-sign remember-me cookies.
    Attempt to read from keyring; if missing and not in Docker, generate and store one.
    """
    try:
        raw = _cfg_read("session_key")
        if raw:
            try:
                return bytes.fromhex(raw)
            except Exception:
                return raw.encode("utf-8")
    except Exception:
        pass

    # Generate and persist to config if no persisted key found
    try:
        new = secrets.token_hex(32)
        with contextlib.suppress(Exception):
            _cfg_write("session_key", new)
        return bytes.fromhex(new)
    except Exception:
        return None

def _load_token_store() -> dict[str, Any]:
    try:
        return auth_mod.get_api_tokens() or {}
    except Exception:
        return {}

def _persist_token_store(store: dict[str, Any]) -> None:
    with suppress(Exception):
        auth_mod.set_api_tokens(store)


def _create_api_token(username: str, label: str = "", persist: bool = True, token_value: Optional[str] = None) -> str:
    """Create a new API token. If `persist` is False, do not write the token store to durable storage.
    Optionally accept `token_value` to use an externally-provided token string when persisting.
    """
    store = _load_token_store()
    token_id = str(token_value) if token_value else secrets.token_urlsafe(96)
    # Tokens are non-expiring by default and remain valid until revoked.
    expiry = None
    # Store token metadata (no per-token scopes; tokens are treated as valid/invalid)
    store[token_id] = {"user": username, "label": label, "created": int(datetime.now(timezone.utc).timestamp()), "expiry": expiry}
    if persist:
        _persist_token_store(store)
    with contextlib.suppress(Exception):
        _write_audit_log("create_api_token", [username], None, {"id": token_id, "label": label}, True)
    return token_id


def _persist_existing_api_token(token: str, username: str, label: str = "") -> bool:
    """Persist an existing token string into the token store. Returns True on success."""
    if not token:
        return False
    store = _load_token_store()
    if token in store:
        return False
    # Persisted tokens do not expire unless revoked.
    expiry = None
    store[token] = {"user": username, "label": label, "created": int(datetime.now(timezone.utc).timestamp()), "expiry": expiry}
    _persist_token_store(store)
    with contextlib.suppress(Exception):
        _write_audit_log("create_api_token", [username], None, {"id": token, "label": label}, True)
    return True


def _verify_api_token(token: str) -> Optional[str]:
    if not token:
        return None
    store = _load_token_store()
    info = store.get(token)
    if not info:
        return None
    expiry = info.get("expiry")
    if expiry and int(datetime.now(timezone.utc).timestamp()) > int(expiry):
        return None
    return str(info.get("user"))


def _get_token_info(token: str) -> Optional[dict[str, Any]]:
    """Return stored token info dict or None."""
    if not token:
        return None
    store = _load_token_store()
    info = store.get(token)
    if not info:
        return None
    expiry = info.get("expiry")
    if expiry and int(datetime.now(timezone.utc).timestamp()) > int(expiry):
        return None
    return info


def _token_is_valid(token: str) -> bool:
    """Return True if token is valid. No per-token scopes enforced."""
    info = _get_token_info(token)
    return bool(info)


def _validate_upload_assistant_args(args: list[str]) -> list[str]:
    """Validate upload-assistant arguments to avoid command-injection.

    Rejects arguments containing nulls, newlines, or common shell metacharacters.
    Returns the original args if they pass validation, otherwise raises ValueError.
    """
    if not isinstance(args, list):
        raise ValueError("Invalid args")
    safe_args: list[str] = []
    # Disallow characters that enable shell injection or command chaining.
    forbidden = set(";&|$`><*?~!\n\r\x00")
    for a in args:
        if not isinstance(a, str):
            raise ValueError("Invalid arg type")
        if any(ch in a for ch in forbidden):
            raise ValueError("Invalid characters in arg")
        # Disallow arguments that are just parent-directory references
        if a == ".." or a == ".":
            raise ValueError("Invalid arg")
        safe_args.append(a)
    return safe_args


def _get_bearer_from_header() -> Optional[str]:
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(None, 1)[1].strip()
    return None


def _revoke_api_token(token: str) -> bool:
    store = _load_token_store()
    if token in store:
        owner = store[token].get("user")
        del store[token]
        _persist_token_store(store)
        with contextlib.suppress(Exception):
            _write_audit_log("revoke_api_token", [owner], {"id": token}, None, True)
        return True
    return False


def _list_api_tokens() -> dict[str, Any]:
    return _load_token_store()


def _create_remember_token(username: str, days: int = 30) -> Optional[str]:
    key = _get_persistent_cookie_key()
    if not key:
        return None
    expiry = int(datetime.now(timezone.utc).timestamp()) + days * 86400
    payload = json.dumps({"u": username, "e": expiry}, separators=(",", ":")).encode("utf-8")
    b64 = base64.urlsafe_b64encode(payload).decode("ascii")
    sig = hmac.new(key, b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64}|{sig}"


def _verify_remember_token(token: str) -> Optional[str]:
    key = _get_persistent_cookie_key()
    if not key or not token:
        return None
    try:
        parts = token.split("|")
        if len(parts) != 2:
            return None
        b64, sig = parts
        expected = hmac.new(key, b64.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        payload = base64.urlsafe_b64decode(b64.encode("ascii"))
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict):
            return None
        username = data.get("u")
        expiry = int(data.get("e") or 0)
        if not username or expiry < int(datetime.now(timezone.utc).timestamp()):
            return None
        return str(username)
    except Exception:
        return None



def _hash_code(code: str) -> str:
    return hashlib.pbkdf2_hmac('sha256', code.encode('utf-8'), b'upload-assistant-recovery-salt', 100000).hex()


def _generate_recovery_codes(n: int = 10, length: int = 10) -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Crockford-like, avoid ambiguous chars
    return ["".join(secrets.choice(alphabet) for _ in range(length)) for _ in range(n)]


def _load_recovery_hashes() -> list[str]:
    # Load recovery hashes from the encrypted extras in the user record
    try:
        return auth_mod.get_recovery_hashes() or []
    except Exception:
        return []


def _persist_recovery_hashes(hashes: list[str]) -> None:
    with suppress(Exception):
        auth_mod.set_recovery_hashes(hashes)


def _consume_recovery_code(code: str) -> bool:
    """Return True if code matches an unused recovery code and mark it used (persist)."""
    if not code:
        return False
    hashes = _load_recovery_hashes()
    if not hashes:
        return False
    h = _hash_code(code.strip())
    if h in hashes:
        hashes.remove(h)
        _persist_recovery_hashes(hashes)
        return True
    return False


def _parse_cors_origins() -> list[str]:
    raw = os.environ.get("UA_WEBUI_CORS_ORIGINS", "").strip()
    if not raw:
        return []
    origins: list[str] = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            origins.append(part)
    return origins


cors_origins = _parse_cors_origins()
if cors_origins:
    # Allow the CSRF header and support credentials so browser-based
    # cross-origin requests can send cookies for authenticated sessions.
    CORS_fn(
        app,
        resources={r"/api/*": {"origins": cors_origins}},
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
        supports_credentials=True,
    )

# ANSI color code regex pattern
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class ProcessInfo(TypedDict, total=False):
    process: subprocess.Popen[str]
    mode: str
    input_queue: "queue.Queue[str]"
    # Rich Console type is not imported for typing reasons here; use Any
    record_console: Any


# Store active processes
active_processes: dict[str, ProcessInfo] = {}

# Local store for consoles we've wrapped to avoid assigning attributes on Console
_ua_console_store: dict[int, dict[str, Any]] = {}


def _debug_process_snapshot(session_id: Optional[str] = None) -> dict[str, Any]:
    try:
        snapshot: dict[str, Any] = {
            "active_sessions": list(active_processes.keys()),
            "console_store_keys": list(_ua_console_store.keys()),
            "inproc_lock_locked": inproc_lock.locked(),
        }
        if session_id and session_id in active_processes:
            info = active_processes.get(session_id, {})
            snapshot["session"] = {
                "mode": info.get("mode"),
                "has_worker": isinstance(info.get("worker"), threading.Thread),
                "has_stdout_thread": isinstance(info.get("stdout_thread"), threading.Thread),
                "has_stderr_thread": isinstance(info.get("stderr_thread"), threading.Thread),
            }
        return snapshot
    except Exception:
        return {"error": "failed to build snapshot"}


class BrowseItem(TypedDict, total=False):
    """Serialized representation of an entry returned by the browse API."""

    name: str
    path: str
    type: Literal["folder", "file"]
    children: Union[list["BrowseItem"], None]
    subtitle: str  # Optional hint  (eg, when parent path when names collide)


class ConfigItem(TypedDict, total=False):
    key: str
    value: Any
    source: Literal["config", "example"]
    children: list["ConfigItem"]
    help: list[str]
    subsection: Union[str, bool]


class ConfigSection(TypedDict, total=False):
    section: str
    items: list[ConfigItem]
    client_types: list[str]


def _webui_auth_configured() -> bool:
    # Consider auth configured if a local user file exists
    return bool(auth_mod.load_user())


def _webui_auth_ok() -> bool:
    """Return True when the incoming request is authenticated.

    Authentication sources:
    - Bearer token (API token) — validated via _verify_api_token(); when a
      persisted user exists ensure the token's username matches it.
    - Basic auth — only valid when a persisted user exists and credentials
      validate against that persisted user.
    """
    persisted = auth_mod.load_user()

    # Bearer tokens for API clients
    bearer_token = _get_bearer_from_header()
    if bearer_token:
        user = _verify_api_token(bearer_token)
        if user:
            if persisted:
                stored_username = persisted.get("username")
                if stored_username and user != stored_username:
                    return False
            with contextlib.suppress(Exception):
                g.username = user
            return True
        return False

    # Basic auth is only supported against a persisted user
    auth = request.authorization
    if not auth or auth.type != "basic":
        return False
    if not persisted:
        return False
    return auth_mod.verify_user(auth.username or "", auth.password or "")


@app.before_request
def _require_auth_for_webui():  # pyright: ignore[reportUnusedFunction]
    # Health endpoint can be used for orchestration checks.
    if request.path == "/api/health":
        return None

    # Check IP access control
    client_ip = get_remote_address()
    if not _is_ip_allowed(client_ip):
        # Log the blocked attempt
        if access_logger:
            with contextlib.suppress(AttributeError):
                access_logger.log(
                    endpoint=request.path,
                    method=request.method,
                    remote_addr=client_ip,
                    username=None,
                    success=False,
                    status=403,
                    headers={"User-Agent": request.headers.get("User-Agent", "")},
                    details="IP blocked",
                )
        return jsonify({"error": "Access denied", "success": False}), 403

    # Try to restore session from a long-lived remember-me cookie if present
    try:
        if not _is_authenticated():
            token = request.cookies.get("ua_remember")
            if token:
                username = _verify_remember_token(token)
                if username:
                    # Only accept remember token if it matches the persisted user (if any)
                    persisted = auth_mod.load_user()
                    if persisted:
                        stored = persisted.get("username")
                        if stored and username == stored:
                            g.authenticated = True
                            g.username = username
                    else:
                        # No persisted user yet: accept remembered username as provisional
                        g.authenticated = True
                        g.username = username
    except Exception:
        # Any failure to validate the cookie should not block request flow; fallback to normal auth
        pass

    if request.path.startswith("/api/"):
        # For API, allow basic auth
        if _webui_auth_ok():
            return None
        # Or session auth
        if _is_authenticated():
            # Set username in g for logging if available
            try:
                username = _session_get("username")
                if username:
                    g.username = username
            except Exception:
                pass
            return None
        # If request accepts HTML (browser), redirect to login; else 401 for API clients
        if "text/html" in request.headers.get("Accept", ""):
            return redirect(url_for("login_page"))
        _handle_failed_auth(client_ip)
        return jsonify({"error": "Authentication required", "success": False}), 401

    # For web routes
    if _is_authenticated():
        # Set username in g for logging if available
        try:
            username = _session_get("username")
            if username:
                g.username = username
        except Exception:
            pass
        return None
    if _webui_auth_configured() and _webui_auth_ok():
        return None
    if request.path == "/config" or request.path in ("/", "/index.html"):
        return redirect(url_for("login_page"))

    return None


@app.after_request
def _maybe_log_api_access(response):
    """Log API access attempts according to configured level.

    By default only non-successful API attempts are logged (level: access_denied).
    When level=access all accesses are logged.
    When level=disabled no logging occurs.
    """
    try:
        if access_logger is None:
            return response

        path = request.path or ""
        if not path.startswith("/api/"):
            return response

        status = getattr(response, "status_code", 500)
        success = 200 <= int(status) < 300
        if not access_logger.should_log(success):
            return response

        # Determine username if available
        user = None
        try:
            # First try authenticated user
            user = getattr(g, "username", None) or _session_get("username")

            # For failed auth attempts, try to extract attempted username
            if user is None and not success:
                # Check Basic auth
                if request.authorization and request.authorization.username:
                    user = f"{request.authorization.username} (basic auth)"
                # Check form data (login attempts)
                elif request.method == "POST" and request.form.get("username"):
                    user = f"{request.form.get('username')} (login attempt)"
                # Check Bearer token (even if invalid, might give us a hint)
                elif request.headers.get("Authorization", "").startswith("Bearer "):
                    user = "bearer token attempt"
        except Exception:
            user = None

        # Minimal headers for context
        headers = dict(request.headers) if request.headers else None

        remote = request.remote_addr or request.environ.get('REMOTE_ADDR')

        access_logger.log(
            endpoint=path,
            method=request.method,
            remote_addr=remote,
            username=user,
            success=success,
            status=int(status),
            headers=headers,
            details=None,
        )
    except Exception:
        pass
    return response


def _totp_enabled() -> bool:
    # TOTP is enabled when a TOTP secret is configured either in persisted
    # storage or via environment (saved_totp_secret).
    persisted = auth_mod.load_user()
    if persisted:
        return bool(auth_mod.get_totp_secret())
    return bool(saved_totp_secret)
def _verify_totp_code(code: str) -> bool:
    """Verify a TOTP code against the stored secret."""
    persisted = auth_mod.load_user()
    secret = auth_mod.get_totp_secret() if persisted else saved_totp_secret

    if not secret:
        return False

    try:
        totp = pyotp.TOTP(secret)
        return bool(code and totp.verify(code))
    except Exception:
        return False

def _get_browse_roots() -> list[str]:
    # Check environment first, then runtime browse roots (set by upload.py)
    global _runtime_browse_roots
    raw = os.environ.get("UA_BROWSE_ROOTS", "").strip() or _runtime_browse_roots or ""
    if not raw:
        # Require explicit configuration; do not default to the filesystem root.
        return []

    roots: list[str] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        root = os.path.abspath(part)
        roots.append(root)

    return roots


def set_runtime_browse_roots(browse_roots: str) -> None:
    """Set browse roots at runtime (used by upload.py when starting web UI)"""
    global _runtime_browse_roots
    _runtime_browse_roots = browse_roots


def _load_config_from_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    # Restrict to the repository `data` directory and ensure .py extension.
    repo_data_dir = Path(__file__).resolve().parent.parent / "data"
    try:
        if not path.resolve().is_relative_to(repo_data_dir.resolve()) or path.suffix != ".py":
            return {}
    except Exception:
        return {}

    # Basic permissions check: ensure file is readable and not world-writable (on Unix-like; on Windows, minimal check)
    try:
        stat_info = path.stat()
        # On Windows, check if file is not hidden and readable
        if os.name == 'nt':
            # Windows: check if not hidden (FILE_ATTRIBUTE_HIDDEN = 2)
            if getattr(stat_info, 'st_file_attributes', 0) & 2:  # Hidden
                return {}
        else:
            # Unix-like: check ownership and permissions. Only call os.getuid()
            # on platforms that expose it (non-Windows). This avoids raising
            # AttributeError on Windows.
            if hasattr(os, 'getuid'):
                try:
                    if stat_info.st_uid != os.getuid() or (stat_info.st_mode & 0o022):
                        return {}
                except Exception:
                    return {}
            else:
                # If getuid is not available, fall back to a conservative
                # permissions check using the mode bits only.
                if (stat_info.st_mode & 0o022):
                    return {}
    except Exception:
        return {}

    try:
        with open(path, encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'config':
                        config_value = ast.literal_eval(node.value)
                        if isinstance(config_value, dict):
                            return config_value
        return {}
    except Exception:
        return {}


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)


def _redact_sensitive(value: Any) -> Any:
    """Return a copy of the value with sensitive dictionary fields redacted.

    Keys containing any of these substrings will be redacted (case-insensitive):
    password, pass, secret, token, key, totp, api, credential, auth
    """
    sensitive_parts = ("password", "pass", "secret", "token", "key", "totp", "api", "credential", "auth")

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            try:
                lk = str(k).lower()
            except Exception:
                lk = ""
            if any(p in lk for p in sensitive_parts):
                out[str(k)] = "<redacted>"
            else:
                out[str(k)] = _redact_sensitive(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact_sensitive(v) for v in value]
    # For primitives (str/int/etc.) we keep the value as-is — redaction is key-based
    return value


def _write_audit_log(action: str, path: list[str], old_value: Any, new_value: Any, success: bool, error: Optional[str] = None) -> None:
    """Append an audit record to data/config_audit.log.

    Uses UTC ISO timestamps and attempts to record the acting user and remote
    address. Values are passed through `_json_safe` to ensure JSON-serializable
    output. Any exceptions writing the audit are logged to the console but do
    not raise to callers.
    """
    try:
        base_dir = Path(__file__).parent.parent
        audit_path = base_dir / "data" / "config_audit.log"
        # Determine acting user: session -> Basic auth username -> persisted user -> remote_addr
        persisted = auth_mod.load_user()
        user = _session_get("username") or (request.authorization.username if request.authorization else None) or (persisted.get("username") if persisted else None) or request.remote_addr
        # Redact sensitive fields from values before serializing to the audit log.
        audit = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user,
            "remote_addr": request.remote_addr,
            "action": action,
            "path": path,
            "old_value": _json_safe(_redact_sensitive(old_value)),
            "new_value": _json_safe(_redact_sensitive(new_value)),
            "success": bool(success),
            "error": error,
        }
        with open(audit_path, "a", encoding="utf-8") as af:
            af.write(json.dumps(audit, ensure_ascii=False) + "\n")
    except Exception as ae:
        with contextlib.suppress(Exception):
            console.print(f"Failed to write config audit record: {ae}", markup=False)


def _get_nested_value(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _coerce_config_value(raw: Any, example_value: Any) -> Any:
    if isinstance(example_value, bool):
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(raw)

    if isinstance(example_value, int) and not isinstance(example_value, bool):
        if isinstance(raw, (int, float)):
            return int(raw)
        if isinstance(raw, str) and raw.strip():
            return int(raw.strip())
        return 0

    if isinstance(example_value, float):
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, str) and raw.strip():
            return float(raw.strip())
        return 0.0

    if example_value is None:
        if isinstance(raw, str) and raw.strip().lower() in {"", "none", "null"}:
            return None
        return raw

    if isinstance(example_value, (list, dict)):
        if isinstance(raw, (list, dict)):
            return raw
        if isinstance(raw, str):
            raw_str = raw.strip()
            if not raw_str:
                return [] if isinstance(example_value, list) else {}
            try:
                parsed = json.loads(raw_str)
                return parsed
            except json.JSONDecodeError:
                return raw
        return raw

    if isinstance(raw, str):
        return raw

    return str(raw)


def _python_literal(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    return repr(value)


def _format_config_tree(tree: ast.AST) -> str:
    """Format an AST tree in the same style as example-config.py"""
    lines = []

    # Cast to Module to access body attribute
    if not isinstance(tree, ast.Module):
        return ast.unparse(tree)

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "config":
                    if isinstance(node.value, ast.Dict):
                        lines.append("config = {")
                        lines.extend(_format_dict(node.value, 1))
                        lines.append("}")
                    else:
                        lines.append(ast.unparse(node))
                    break
        else:
            # Keep other statements as-is
            lines.append(ast.unparse(node))

    return "\n".join(lines)


def _format_dict(dict_node: ast.Dict, indent_level: int) -> list[str]:
    """Format a dictionary node with proper indentation"""
    lines = []
    indent = "    " * indent_level

    for _i, (key_node, value_node) in enumerate(zip(dict_node.keys, dict_node.values)):
        key_str = repr(key_node.value) if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str) else ast.unparse(key_node) if key_node is not None else "None"

        if isinstance(value_node, ast.Dict):
            lines.append(f"{indent}{key_str}: {{")
            lines.extend(_format_dict(value_node, indent_level + 1))
            lines.append(f"{indent}}},")
        else:
            value_str = ast.unparse(value_node)
            lines.append(f"{indent}{key_str}: {value_str},")

    return lines


def _replace_config_value_in_source(source: str, key_path: list[str], new_value: str) -> str:
    tree = ast.parse(source)
    config_assign = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "config":
                    config_assign = node
                    break
        if config_assign:
            break

    if config_assign is None or not isinstance(config_assign.value, ast.Dict):
        raise ValueError("Config assignment not found")

    current_dict = config_assign.value
    target_node: Optional[ast.AST] = None

    for i, key in enumerate(key_path):
        found = False
        for k_node, v_node in zip(current_dict.keys, current_dict.values):
            if isinstance(k_node, ast.Constant) and isinstance(k_node.value, str) and k_node.value == key:
                if isinstance(v_node, ast.Dict):
                    if i < len(key_path) - 1:  # Not the final key
                        current_dict = v_node
                        found = True
                        break
                    else:  # Final key - update existing value
                        target_node = v_node
                        found = True
                        break
                target_node = v_node
                found = True
                break

        if not found:
            if i == len(key_path) - 1:  # Final key doesn't exist - need to add it
                # Add new key-value pair to current_dict
                new_key_node = ast.Constant(value=key)
                new_value_node = ast.parse(new_value, mode="eval").body

                current_dict.keys.append(new_key_node)
                current_dict.values.append(new_value_node)

                # Reconstruct the source with the new key using proper formatting
                return _format_config_tree(tree)
            else:
                raise ValueError(f"Key not found in config: {key}")

        if target_node is not None and i < len(key_path) - 1:
            raise ValueError("Invalid path for config update")

    if target_node is None:
        raise ValueError("Target node not found")

    if not hasattr(target_node, "lineno") or not hasattr(target_node, "end_lineno"):
        raise ValueError("Unable to locate config value position")

    lineno = cast(Optional[int], getattr(target_node, "lineno", None))
    end_lineno = cast(Optional[int], getattr(target_node, "end_lineno", None))
    col_offset = cast(int, getattr(target_node, "col_offset", 0))
    end_col_offset = cast(int, getattr(target_node, "end_col_offset", 0))
    if lineno is None or end_lineno is None:
        raise ValueError("Unable to locate config value position")

    lines = source.splitlines(keepends=True)
    start = sum(len(line) for line in lines[: lineno - 1]) + col_offset
    end = sum(len(line) for line in lines[: end_lineno - 1]) + end_col_offset

    updated_source = f"{source[:start]}{new_value}{source[end:]}"

    # Reformat the entire config to ensure consistent styling
    updated_tree = ast.parse(updated_source)
    return _format_config_tree(updated_tree)


def _remove_config_key_in_source(source: str, key_path: list[str]) -> str:
    """Remove a key from the config source if it exists"""
    tree = ast.parse(source)
    config_assign = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "config":
                    config_assign = node
                    break
        if config_assign:
            break

    if config_assign is None or not isinstance(config_assign.value, ast.Dict):
        return source  # No config found, return as-is

    current_dict = config_assign.value

    for i, key in enumerate(key_path):
        found = False
        for j, (k_node, v_node) in enumerate(zip(current_dict.keys, current_dict.values)):
            if isinstance(k_node, ast.Constant) and isinstance(k_node.value, str) and k_node.value == key:
                if isinstance(v_node, ast.Dict):
                    if i < len(key_path) - 1:  # Not the final key
                        current_dict = v_node
                        found = True
                        break
                    else:  # Final key - remove it
                        # Remove the key-value pair
                        del current_dict.keys[j]
                        del current_dict.values[j]
                        # Reconstruct the source
                        return _format_config_tree(tree)
                else:
                    if i == len(key_path) - 1:  # Final key - remove it
                        del current_dict.keys[j]
                        del current_dict.values[j]
                        return _format_config_tree(tree)
                found = True
                break

        if not found:
            return source  # Key not found, return as-is

    return source  # Should not reach here


def _build_config_items(
    example_section: dict[str, Any],
    user_section: Any,
    comments_map: dict[str, list[str]],
    subsection_map: dict[str, str],
    path: list[str],
) -> list[ConfigItem]:
    items: list[ConfigItem] = []
    user_dict = user_section if isinstance(user_section, dict) else {}

    merged_keys = list(example_section.keys())
    if isinstance(user_section, dict):
        merged_keys.extend([key for key in user_section if key not in example_section])

    current_subsection: Optional[str] = None
    subsection_items: list[ConfigItem] = []

    def flush_subsection() -> None:
        nonlocal subsection_items, current_subsection
        if current_subsection and subsection_items:
            items.append(
                {
                    "key": current_subsection,
                    "children": subsection_items,
                    "source": "example",
                    "help": [],
                    "subsection": True,
                }
            )
        subsection_items = []

    for key in merged_keys:
        example_value = example_section.get(key)
        user_value = user_dict.get(key)
        key_path = path + [str(key)]
        help_text = comments_map.get("/".join(key_path), [])
        subsection_label = subsection_map.get("/".join(key_path))
        if subsection_label != current_subsection:
            flush_subsection()
            current_subsection = subsection_label
        if isinstance(example_value, dict) or isinstance(user_value, dict):
            example_value = example_value if isinstance(example_value, dict) else {}
            user_value = user_value if isinstance(user_value, dict) else {}
            children = _build_config_items(example_value, user_value, comments_map, subsection_map, key_path)
            source: Literal["config", "example"] = "config" if key in user_dict else "example"
            item: ConfigItem = {
                "key": str(key),
                "source": source,
                "children": children,
                "help": help_text,
            }
        else:
            if key in user_dict:
                value = user_value
                source = "config"
            else:
                value = example_value
                source = "example"
            item = {
                "key": str(key),
                "value": _json_safe(value),
                "source": source,
                "help": help_text,
            }

        if current_subsection:
            subsection_items.append(item)
        else:
            items.append(item)

    flush_subsection()

    return items


def _extract_example_metadata(example_path: Path) -> tuple[dict[str, list[str]], dict[str, str]]:
    if not example_path.exists():
        return {}, {}

    source = example_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)

    config_assign: Optional[ast.Assign] = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "config":
                    config_assign = node
                    break
        if config_assign:
            break

    if config_assign is None or not isinstance(config_assign.value, ast.Dict):
        return {}, {}

    comment_map: dict[str, list[str]] = {}
    subsection_map: dict[str, str] = {}

    def collect_comments(lineno: int) -> list[str]:
        idx = lineno - 2
        comments: list[str] = []
        while idx >= 0:
            line = lines[idx]
            stripped = line.strip()
            if not stripped:
                if comments:
                    break
                idx -= 1
                continue
            if stripped.startswith("#"):
                comments.insert(0, stripped.lstrip("#").strip())
                idx -= 1
                continue
            break
        return comments

    def find_headers(
        start_line: int,
        end_line: int,
        child_ranges: list[tuple[int, int]],
    ) -> list[tuple[int, str]]:
        headers: list[tuple[int, str]] = []
        for idx in range(start_line - 1, end_line):
            if idx <= 0 or idx + 1 >= len(lines):
                continue
            stripped = lines[idx].strip()
            if not stripped.startswith("#"):
                continue
            title = stripped.lstrip("#").strip()
            if not title:
                continue
            if title != title.upper():
                continue
            if not any(char.isalpha() for char in title):
                continue
            if lines[idx - 1].strip() or lines[idx + 1].strip():
                continue
            line_no = idx + 1
            if any(start <= line_no <= end for start, end in child_ranges):
                continue
            headers.append((line_no, title))
        return headers

    def walk_dict(node: ast.Dict, path: list[str]) -> None:
        key_entries: list[tuple[str, int, ast.AST]] = []
        child_ranges: list[tuple[int, int]] = []
        for key_node, value_node in zip(node.keys, node.values):
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                continue
            key = key_node.value
            lineno = getattr(key_node, "lineno", None)
            if isinstance(lineno, int):
                comment_map["/".join(path + [key])] = collect_comments(lineno)
                key_entries.append((key, lineno, value_node))

            if isinstance(value_node, ast.Dict):
                start = getattr(value_node, "lineno", None)
                end = getattr(value_node, "end_lineno", None)
                if isinstance(start, int) and isinstance(end, int):
                    child_ranges.append((start, end))

            if isinstance(value_node, ast.Dict):
                walk_dict(value_node, path + [key])

        start_line = getattr(node, "lineno", None)
        end_line = getattr(node, "end_lineno", None)
        if isinstance(start_line, int) and isinstance(end_line, int) and key_entries:
            headers = sorted(find_headers(start_line, end_line, child_ranges), key=lambda h: h[0])
            key_entries.sort(key=lambda entry: entry[1])
            header_idx = 0
            current_header: Optional[str] = None
            for key, lineno, _ in key_entries:
                while header_idx < len(headers) and headers[header_idx][0] < lineno:
                    current_header = headers[header_idx][1]
                    header_idx += 1
                if current_header:
                    subsection_map["/".join(path + [key])] = current_header

    walk_dict(config_assign.value, [])
    return comment_map, subsection_map


def _resolve_user_path(
    user_path: Optional[Any],
    *,
    require_exists: bool = True,
    require_dir: bool = False,
) -> str:
    roots = _get_browse_roots()
    if not roots:
        raise ValueError("Browsing is not configured")

    default_root = roots[0]

    if user_path is None or user_path == "":
        expanded = ""
    else:
        if not isinstance(user_path, str):
            raise ValueError("Path must be a string")
        if len(user_path) > 4096:
            raise ValueError("Invalid path")
        if "\x00" in user_path or "\n" in user_path or "\r" in user_path:
            raise ValueError("Invalid characters in path")

        expanded = os.path.expandvars(os.path.expanduser(user_path))

    # Build a normalized path and validate it against allowlisted roots.
    # Use werkzeug.security.safe_join as the primary path sanitizer, with a
    # Windows fallback since safe_join uses posixpath internally.
    # Enforce a realpath+commonpath constraint to prevent symlink escapes.
    matched_root: Union[str, None] = None
    candidate_norm: Union[str, None] = None

    if expanded and os.path.isabs(expanded):
        # If a user supplies an absolute path, only allow it if it is under
        # one of the configured browse roots (or their realpath equivalents,
        # since the browse API returns realpath-resolved paths to the frontend).
        for root in roots:
            root_abs = os.path.abspath(root)
            root_real = os.path.realpath(root_abs)

            # Check against both the configured root and its realpath.
            # This handles the case where the frontend sends back a realpath
            # (e.g., /mnt/storage/torrents) that was returned by a previous
            # browse call, but the configured root is a symlink (e.g., /data/torrents).
            for check_root in (root_abs, root_real):
                try:
                    rel = os.path.relpath(expanded, check_root)
                except ValueError:
                    # Different drive on Windows.
                    continue

                # Sanitize the relative path components to defend against
                # path-injection (e.g. ../../../, absolute segments, nulls).
                # We reject components that resolve to '.' or '..' and use
                # Werkzeug's `secure_filename` to normalize each path segment.
                try:
                    rel = _sanitize_relpath(rel)
                except ValueError:
                    continue

                if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
                    continue

                # Handle the case where the path equals the root exactly.
                # safe_join may return None for '.' in some Werkzeug versions.
                if rel == ".":
                    matched_root = check_root
                    candidate_norm = os.path.normpath(check_root)
                    break

                joined = safe_join(check_root, rel)

                # Windows fallback: safe_join uses posixpath internally and returns
                # None for Windows backslash paths. Fall back to os.path.join on
                # Windows since we already validated rel above and commonpath check
                # below provides additional symlink-escape protection.
                if joined is None and sys.platform == 'win32':
                    joined = os.path.join(check_root, rel)

                if joined is None:
                    continue

                matched_root = check_root
                candidate_norm = os.path.normpath(joined)
                break

            if matched_root:
                break
    else:
        matched_root = os.path.abspath(default_root)
        # Handle empty path (initial browse request) - use the root directly.
        # safe_join may return None for empty strings in some Werkzeug versions.
        if not expanded:
            candidate_norm = os.path.normpath(matched_root)
        else:
            # Sanitize the incoming expanded path before joining.
            try:
                sanitized_expanded = _sanitize_relpath(expanded)
            except ValueError as err:
                raise ValueError('Browsing this path is not allowed') from err

            joined = safe_join(matched_root, sanitized_expanded)

            # Windows fallback: safe_join uses posixpath internally and returns
            # None for Windows backslash paths. Fall back to manual validation
            # and os.path.join. The commonpath check below provides additional security.
            if joined is None and sys.platform == 'win32':
                expanded_norm = os.path.normpath(sanitized_expanded)
                if expanded_norm == os.pardir or expanded_norm.startswith(os.pardir + os.sep) or os.path.isabs(expanded_norm):
                    raise ValueError('Browsing this path is not allowed')
                joined = os.path.join(matched_root, expanded_norm)

            if joined is None:
                raise ValueError("Browsing this path is not allowed")
            candidate_norm = os.path.normpath(joined)

    if not matched_root or not candidate_norm:
        raise ValueError("Browsing this path is not allowed")

    candidate_real = os.path.realpath(candidate_norm)
    root_real = os.path.realpath(matched_root)
    try:
        if os.path.commonpath([candidate_real, root_real]) != root_real:
            raise ValueError("Browsing this path is not allowed")
    except ValueError as e:
        # ValueError can happen on Windows if drives differ.
        raise ValueError("Browsing this path is not allowed") from e

    candidate = candidate_real

    # Additional explicit validation before using `candidate` in filesystem
    # operations. This defends against accidental use of unvalidated
    # user-controlled data (helps static analysis tools and provides a
    # clear guard at the call site).
    if '\x00' in candidate:
        raise ValueError("Browsing this path is not allowed")

    # Ensure the resolved candidate path is within the resolved root path.
    safe_root_prefix = root_real if root_real.endswith(os.sep) else (root_real + os.sep)
    if not (candidate == root_real or candidate.startswith(safe_root_prefix)):
        raise ValueError("Browsing this path is not allowed")

    # Extra explicit assertion for static analysis and defense-in-depth:
    # ensure the resolved candidate is within allowed browse roots.
    try:
        _assert_safe_resolved_path(candidate)
    except ValueError as err:
        raise ValueError("Browsing this path is not allowed") from err

    # Use an explicitly-named, normalized `safe_candidate` for filesystem
    # operations so static analyzers can see the sanitized value being used.
    safe_candidate = os.path.realpath(candidate)

    if require_exists and not os.path.exists(safe_candidate):
        raise ValueError("Path does not exist")

    if require_dir and not os.path.isdir(safe_candidate):
        raise ValueError("Not a directory")

    return safe_candidate


def _resolve_browse_path(user_path: Union[str, None]) -> str:
    return _resolve_user_path(user_path, require_exists=True, require_dir=True)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text"""
    return ANSI_ESCAPE.sub("", text)


@app.route("/")
def index():
    """Serve the main UI"""
    try:
        return render_template("index.html")
    except Exception as e:
        console.print(f"Error loading template: {e}", markup=False)
        console.print(traceback.format_exc(), markup=False)
        return "<pre>Internal server error</pre>", 500


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute;100 per day", key_func=get_remote_address, error_message="Too many attempts, please try again later.")
def login_page():
    if request.method == "POST":
        # Quick IP block check: short-circuit heavy work for known-bad IPs.
        if not _is_ip_allowed(get_remote_address()):
            return Response("Too many requests", status=429, mimetype="text/plain")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        totp_code = (request.form.get("totp_code") or "").strip()
        remember = request.form.get("remember") == "1"

        persisted = auth_mod.load_user()
        if persisted:
            # Persisted user exists: require matching credentials
            if auth_mod.verify_user(username, password):
                if _totp_enabled() and not (totp_code and _verify_totp_code(totp_code)):
                    _handle_failed_auth(get_remote_address())
                    return render_template("login.html", error="Credentials did not match", show_2fa=_totp_enabled())

                _session_set("authenticated", True)
                with contextlib.suppress(Exception):
                    _session_set("username", username)
                with contextlib.suppress(Exception):
                    _session_set("csrf_token", secrets.token_urlsafe(32))
                if remember:
                    session.permanent = True
                resp = redirect(url_for("config_page"))
                if remember:
                    try:
                        token = _create_remember_token(username)
                        if token:
                            resp.set_cookie("ua_remember", token, max_age=30 * 86400, httponly=True, secure=True, samesite="Lax")
                    except Exception:
                        pass
                with suppress(Exception):
                    _cleanup_duplicate_sessions(username)
                return resp
            else:
                # Credentials don't match persisted user
                _handle_failed_auth(get_remote_address())
                return render_template("login.html", error="Credentials did not match")
        else:
            # No persisted user: allow UI-driven creation (first-run setup)
            if username and password:
                if _totp_enabled() and not (totp_code and _verify_totp_code(totp_code)):
                    _handle_failed_auth(get_remote_address())
                    return render_template("login.html", error="Credentials did not match", show_2fa=_totp_enabled())
                try:
                    auth_mod.create_user(username, password)
                except ValueError as exc:
                    return render_template("login.html", error=str(exc), show_2fa=_totp_enabled())
                except Exception:
                    # Non-fatal persistence error; continue without persisting.
                    pass

                _session_set("authenticated", True)
                with contextlib.suppress(Exception):
                    _session_set("username", username)
                with contextlib.suppress(Exception):
                    _session_set("csrf_token", secrets.token_urlsafe(32))
                if remember:
                    session.permanent = True
                    try:
                        token = _create_remember_token(username)
                        if token:
                            resp = redirect(url_for("config_page"))
                            resp.set_cookie("ua_remember", token, max_age=30 * 86400, httponly=True, secure=True, samesite="Lax")
                            with suppress(Exception):
                                _cleanup_duplicate_sessions(username)
                            return resp
                    except Exception:
                        pass

                with suppress(Exception):
                    _cleanup_duplicate_sessions(username)
                return redirect(url_for("config_page"))
            else:
                # No username/password provided
                _handle_failed_auth(get_remote_address())
                return render_template("login.html", error="Credentials did not match")

    # Show 2FA field if enabled
    show_2fa = _totp_enabled()
    return render_template("login.html", show_2fa=show_2fa)


@app.errorhandler(429)
def _rate_limit_exceeded(_e):
    # Return a minimal plain-text 429 response to avoid heavy template rendering.
    return Response("Too many requests", status=429, mimetype="text/plain")


@app.route("/logout", methods=["GET", "POST"])  # prefer POST from the UI
def logout():
    # Accept both GET and POST for compatibility, but UI should use POST.
    # Remove encrypted session payload
    # Clear all server-side session data
    try:
        session.clear()
    except Exception:
        # Fallback: remove encrypted payload if clear fails
        session.pop("enc", None)

    resp = redirect(url_for("login_page"))
    # Remove remember cookie if present
    resp.delete_cookie("ua_remember")
    # Also remove the browser session cookie (Flask's session cookie name)
    try:
        resp.delete_cookie(app.session_cookie_name)
    except Exception:
        # Fallback to common cookie name
        resp.delete_cookie("session")
    return resp


@app.route("/login/recovery", methods=["GET", "POST"])
@limiter.limit("10 per minute;100 per day", key_func=get_remote_address, error_message="Too many attempts, please try again later.")
def login_recovery():
    """Handle login using a recovery code. This is a separate endpoint to
    keep recovery-code input distinct from strict 2FA inputs so password
    managers treat the 2FA input as a one-time code field.
    """
    # If GET, render the dedicated recovery page (minimal inputs)
    if request.method == "GET":
        return render_template("login_recovery.html", show_2fa=_totp_enabled())

    # POST: process recovery code login
    # Quick IP block check: short-circuit heavy work for known-bad IPs.
    if not _is_ip_allowed(get_remote_address()):
        return Response("Too many requests", status=429, mimetype="text/plain")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    recovery_code = request.form.get("recovery_code", "").strip()
    remember = request.form.get("remember") == "1"

    if not _totp_enabled():
        return render_template("login_recovery.html", error="Recovery codes are not enabled", show_2fa=False)

    persisted = auth_mod.load_user()
    # If a persisted user exists, require those credentials + recovery code
    if persisted:
        if username and password and recovery_code and _consume_recovery_code(recovery_code) and auth_mod.verify_user(username, password):
            _session_set("authenticated", True)
            with contextlib.suppress(Exception):
                _session_set("username", username)
            with contextlib.suppress(Exception):
                _session_set("csrf_token", secrets.token_urlsafe(32))
            if remember:
                session.permanent = True
                try:
                    token = _create_remember_token(username)
                    if token:
                        resp = redirect(url_for("config_page"))
                        resp.set_cookie("ua_remember", token, max_age=30 * 86400, httponly=True, secure=True, samesite="Lax")
                        return resp
                except Exception:
                    pass
            return redirect(url_for("config_page"))
        # Failed recovery attempt -> record and show recovery page
        _handle_failed_auth(get_remote_address())
        return render_template("login_recovery.html", error="Recovery code invalid", show_2fa=_totp_enabled())

    # No persisted user: allow first-run creation with recovery-code flow
    if username and password and recovery_code and _consume_recovery_code(recovery_code):
        try:
            auth_mod.create_user(username, password)
        except ValueError as exc:
            return render_template("login_recovery.html", error=str(exc), show_2fa=_totp_enabled())
        except Exception:
            pass

        _session_set("authenticated", True)
        with contextlib.suppress(Exception):
            _session_set("username", username)
        with contextlib.suppress(Exception):
            _session_set("csrf_token", secrets.token_urlsafe(32))
        if remember:
            session.permanent = True
            try:
                token = _create_remember_token(username)
                if token:
                    resp = redirect(url_for("config_page"))
                    resp.set_cookie("ua_remember", token, max_age=30 * 86400, httponly=True, secure=True, samesite="Lax")
                    with suppress(Exception):
                        _cleanup_duplicate_sessions(username)
                    return resp
            except Exception:
                pass

        with suppress(Exception):
            _cleanup_duplicate_sessions(username)
        return redirect(url_for("config_page"))

    _handle_failed_auth(get_remote_address())
    return render_template("login_recovery.html", error="Recovery code invalid", show_2fa=_totp_enabled())


@app.route("/config")
def config_page():
    """Serve the config UI"""
    # Require a CSRF token or same-origin Referer for the config page when
    # the user is authenticated to reduce cross-site information leakage.
    if _is_authenticated() and not _verify_csrf_header():
        referer = request.headers.get("Referer", "")
        # Compute an "effective" scheme taking into account common proxies
        # that may not set X-Forwarded-Proto but do set Cloudflare headers.
        effective_scheme = None
        try:
            xf_proto = request.headers.get("X-Forwarded-Proto")
            if xf_proto:
                effective_scheme = xf_proto.split(",", 1)[0].strip()
            else:
                cf_visitor = request.headers.get("Cf-Visitor") or request.headers.get("Cf-Visitor", None)
                if cf_visitor:
                    try:
                        import json as _json

                        cfv = _json.loads(cf_visitor)
                        effective_scheme = str(cfv.get("scheme")) if cfv.get("scheme") else None
                    except Exception:
                        effective_scheme = None
        except Exception:
            effective_scheme = None

        if not effective_scheme:
            try:
                effective_scheme = request.scheme
            except Exception:
                effective_scheme = "http"

        effective_host_url = f"{effective_scheme}://{request.host}/"

        # Parse the Referer and compare host:port (netloc) with the request host.
        try:
            from urllib.parse import urlparse

            parsed = urlparse(referer or "")
            referer_netloc = parsed.netloc
        except Exception:
            referer_netloc = ""

        # Accept same-origin when referer host matches request.host
        if referer_netloc != request.host:
            # Log diagnostic info to help debug reverse-proxy header mismatches
            console.print(f"[yellow]CSRF check failed for /config: host_url={effective_host_url}, Referer={referer}")
            # Return a helpful error including the observed host_url and referer
            return (
                jsonify({
                    "error": "CSRF token missing or invalid",
                    "success": False,
                    "debug": {"host_url": effective_host_url, "referer": referer, "request_host": request.host},
                }),
                403,
            )

    try:
        # Ensure a session CSRF token exists and expose it to the template so
        # client-side JS can read it without an extra round-trip if desired.
        with contextlib.suppress(Exception):
            if _is_authenticated() and not _session_get("csrf_token"):
                _session_set("csrf_token", secrets.token_urlsafe(32))
        return render_template("config.html", csrf_token=_session_get("csrf_token", ""))
    except Exception as e:
        console.print(f"Error loading config template: {e}", markup=False)
        console.print(traceback.format_exc(), markup=False)
        return "<pre>Internal server error</pre>", 500


@app.route("/api/health")
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "success": True, "message": "Upload Assistant Web UI is running"})


@app.route("/api/csrf_token")
def csrf_token():
    """Return the per-session CSRF token for use by the frontend."""
    # Require authenticated web session for CSRF token access
    if not _is_authenticated():
        return jsonify({"success": False, "error": "Authentication required (web session)"}), 401

    try:
        token = _session_get("csrf_token") or ""
        return jsonify({"csrf_token": token, "success": True})
    except Exception:
        # Returning an empty CSRF token on error is an explicit non-secret
        # failure response; suppress Bandit's B105 false positive here.
        return jsonify({"csrf_token": "", "success": False}), 500  # nosec: B105 - not a hardcoded password


@app.route("/api/2fa/status")
def twofa_status():
    """Check 2FA status"""
    # Require authenticated web session for 2FA status
    if not _is_authenticated():
        return jsonify({"success": False, "error": "Authentication required (web session)"}), 401

    # Require CSRF and same-origin for reads of auth/2fa state
    if not _verify_csrf_header() or not _verify_same_origin():
        return jsonify({"success": False, "error": "CSRF/Origin validation failed"}), 403

    return jsonify({"enabled": _totp_enabled(), "success": True})


@app.route("/api/access_log/level", methods=["GET", "POST"])
def access_log_level_api():
    """Get or set the access logging level.

    GET: returns current level (no auth required for read).
    POST: set level (requires web session + CSRF).

    Valid levels: access_denied (default), access, disabled
    """
    if request.method == "GET":
        # Require authenticated web session and CSRF + same-origin for reads
        if not _is_authenticated():
            return jsonify({"success": False, "error": "Authentication required (web session)"}), 401
        if not _verify_csrf_header() or not _verify_same_origin():
            return jsonify({"success": False, "error": "CSRF/Origin validation failed"}), 403

        if access_logger is None:
            return jsonify({"success": False, "error": "Access logging unavailable"}), 500
        try:
            lvl = access_logger.get_level()
            return jsonify({"success": True, "level": lvl})
        except Exception:
            return jsonify({"success": False, "error": "Failed to read level"}), 500

    # POST: require authenticated web session and CSRF
    if not _is_authenticated():
        return jsonify({"success": False, "error": "Authentication required (web session)"}), 401
    if not _verify_csrf_header():
        return jsonify({"success": False, "error": "CSRF validation failed"}), 403
    # Require same-origin for token management actions
    if not _verify_same_origin():
        return jsonify({"success": False, "error": "Origin validation failed"}), 403

    if access_logger is None:
        return jsonify({"success": False, "error": "Access logging unavailable"}), 500

    data = request.json or {}
    level = data.get("level")
    if not isinstance(level, str) or level not in ("access_denied", "access", "disabled"):
        return jsonify({"success": False, "error": "Invalid level"}), 400

    ok = access_logger.set_level(level)
    if ok:
        return jsonify({"success": True, "level": level})
    return jsonify({"success": False, "error": "Failed to persist level"}), 500


@app.route("/api/access_log/entries", methods=["GET"])
def access_log_entries_api():
    """Get recent access log entries.

    GET: returns recent log entries (requires web session).
    Query params: n (number of entries, default 50, max 200)
    """
    # Require authenticated web session
    if not _is_authenticated():
        return jsonify({"success": False, "error": "Authentication required (web session)"}), 401

    # Require CSRF + same-origin for reads of access-log entries
    if not _verify_csrf_header() or not _verify_same_origin():
        return jsonify({"success": False, "error": "CSRF/Origin validation failed"}), 403

    if access_logger is None:
        return jsonify({"success": False, "error": "Access logging unavailable"}), 500

    try:
        n = request.args.get('n', '50')
        n = int(n)
        if n < 1 or n > 200:
            n = 50
    except (ValueError, TypeError):
        n = 50

    try:
        entries = access_logger.tail(n)
        return jsonify({"success": True, "entries": entries})
    except Exception:
        return jsonify({"success": False, "error": "Failed to read log entries"}), 500


@app.route("/api/ip_control", methods=["GET", "POST"])
def ip_control_api():
    """Get or set IP whitelist/blacklist.

    GET: returns current whitelist and blacklist (requires web session).
    POST: updates whitelist/blacklist. Body: {"whitelist": [...], "blacklist": [...]}
    (requires web session + CSRF).
    """
    # Require authenticated web session
    if not _is_authenticated():
        return jsonify({"success": False, "error": "Authentication required (web session)"}), 401

    if request.method == "GET":
        # Require CSRF + same-origin for reads of IP control settings
        if not _verify_csrf_header() or not _verify_same_origin():
            return jsonify({"success": False, "error": "CSRF/Origin validation failed"}), 403
        try:
            whitelist = _get_ip_whitelist()
            blacklist = _get_ip_blacklist()
            return jsonify({"success": True, "whitelist": whitelist, "blacklist": blacklist})
        except Exception:
            return jsonify({"success": False, "error": "Failed to read IP control settings"}), 500

    elif request.method == "POST":
        # Require CSRF and same-origin for POST
        if not _verify_csrf_header() or not _verify_same_origin():
            return jsonify({"success": False, "error": "CSRF/Origin validation failed"}), 403
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "Invalid JSON"}), 400

            whitelist = data.get("whitelist", [])
            blacklist = data.get("blacklist", [])

            if not isinstance(whitelist, list) or not isinstance(blacklist, list):
                return jsonify({"success": False, "error": "whitelist and blacklist must be arrays"}), 400

            # Validate IP addresses
            import ipaddress
            for ip in whitelist + blacklist:
                if not isinstance(ip, str):
                    return jsonify({"success": False, "error": f"Invalid IP format: {ip}"}), 400
                try:
                    ipaddress.ip_address(ip)
                except ValueError:
                    return jsonify({"success": False, "error": f"Invalid IP address: {ip}"}), 400

            _set_ip_whitelist(whitelist)
            _set_ip_blacklist(blacklist)
            return jsonify({"success": True})
        except Exception as e:
            console.print(f"Error updating IP control: {e}", markup=False)
            return jsonify({"success": False, "error": "Failed to update IP control settings"}), 500



@app.route("/api/2fa/setup", methods=["POST"])
def twofa_setup():
    """Setup 2FA - generate secret and return QR code URI"""
    # Require an authenticated web session (disallow API token / basic auth)
    if not _is_authenticated():
        return jsonify({"error": "Authentication required (web session)", "success": False}), 401
    # Require CSRF + same-origin for 2FA setup (sensitive auth action)
    if not _verify_csrf_header() or not _verify_same_origin():
        return jsonify({"error": "CSRF/Origin validation failed", "success": False}), 403
    if _totp_enabled():
        return jsonify({"error": "2FA already enabled", "success": False}), 400

    # Get username for QR code: prefer session, then persisted user, else generic
    persisted = auth_mod.load_user()
    username = _session_get("username") or (persisted.get("username") if persisted else "user")

    # Generate secret and provisioning URI using pyotp
    secret = pyotp.random_base32()
    try:
        uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="Upload Assistant")
    except Exception:
        uri = ""
    # Generate one-time recovery codes and store temporarily in session
    recovery_codes = _generate_recovery_codes()
    _session_set("temp_totp_secret", secret)
    _session_set("temp_recovery_codes", recovery_codes)

    return jsonify({"secret": secret, "uri": uri, "recovery_codes": recovery_codes, "success": True})


@app.route("/api/2fa/enable", methods=["POST"])
def twofa_enable():
    """Enable 2FA after verification"""
    # Require an authenticated web session (disallow API token / basic auth)
    if not _is_authenticated():
        return jsonify({"error": "Authentication required (web session)", "success": False}), 401
    # Require CSRF + same-origin for enabling 2FA
    if not _verify_csrf_header() or not _verify_same_origin():
        return jsonify({"error": "CSRF/Origin validation failed", "success": False}), 403
    data = request.json or {}
    code = data.get("code", "").strip()

    if not code:
        return jsonify({"error": "Code required", "success": False}), 400

    temp_secret = _session_get("temp_totp_secret")
    if not temp_secret:
        return jsonify({"error": "No setup in progress", "success": False}), 400

    # Verify the code with the temporary secret
    totp = pyotp.TOTP(temp_secret)
    if not totp.verify(code):
        return jsonify({"error": "Invalid code", "success": False}), 400

    # Save the secret permanently to encrypted user record
    with suppress(Exception):
        auth_mod.set_totp_secret(temp_secret)

    # Persist recovery codes (hashes) if provided
    temp_codes = _session_get("temp_recovery_codes") or []
    hashes = [_hash_code(c) for c in temp_codes]
    _persist_recovery_hashes(hashes)

    # Update global variable
    global saved_totp_secret
    saved_totp_secret = temp_secret

    # Clear temp session
    _session_pop("temp_totp_secret", None)
    _session_pop("temp_recovery_codes", None)

    return jsonify({"success": True, "recovery_codes": temp_codes})


@app.route("/api/2fa/disable", methods=["POST"])
def twofa_disable():
    """Disable 2FA"""
    # Require an authenticated web session (disallow API token / basic auth)
    if not _is_authenticated():
        return jsonify({"error": "Authentication required (web session)", "success": False}), 401
    # Require CSRF + same-origin for disabling 2FA
    if not _verify_csrf_header() or not _verify_same_origin():
        return jsonify({"error": "CSRF/Origin validation failed", "success": False}), 403
    if not _totp_enabled():
        return jsonify({"error": "2FA not enabled", "success": False}), 400

    with contextlib.suppress(Exception):
        # Remove TOTP secret and recovery hashes from the encrypted user record
        with suppress(Exception):
            auth_mod.set_totp_secret(None)
        with suppress(Exception):
            auth_mod.set_recovery_hashes([])

    # Update global variable
    global saved_totp_secret
    saved_totp_secret = None

    return jsonify({"success": True})


@app.route("/api/browse_roots")
def browse_roots():
    """Return configured browse roots"""
    roots = _get_browse_roots()
    if not roots:
        return jsonify({"error": "Browsing is not configured", "success": False}), 400

    # First pass: collect all display names to detect duplicates
    name_to_roots: dict[str, list[str]] = {}
    for root in roots:
        display_name = os.path.basename(root.rstrip(os.sep)) or root
        if display_name not in name_to_roots:
            name_to_roots[display_name] = []
        name_to_roots[display_name].append(root)

    # Second pass: build items with subtitles when needed
    items: list[BrowseItem] = []
    for root in roots:
        display_name = os.path.basename(root.rstrip(os.sep)) or root
        item: BrowseItem = {"name": display_name, "path": root, "type": "folder", "children": []}

        # Add subtitle if multiple roots share the same folder name
        if len(name_to_roots.get(display_name, [])) > 1:
            # Show parent path or drive letter
            parent = os.path.dirname(root.rstrip(os.sep))
            if parent:
                # On Windows, show drive letter + parent; on Unix, show parent path
                item["subtitle"] = parent
            else:
                # Fallback to full path if no parent (e.g., drive root)
                item["subtitle"] = root

        items.append(item)

    # If caller used a bearer token, require it to be valid.
    bearer = _get_bearer_from_header()
    if bearer and not _token_is_valid(bearer):
        return jsonify({"success": False, "error": "Forbidden (invalid token)"}), 403

    return jsonify({"items": items, "success": True})


@app.route("/api/config_options")
def config_options():
    """Return config options based on example-config.py with overrides from config.py"""
    # Require an authenticated web session; disallow bearer/basic API auth for config access
    if not _is_authenticated():
        return jsonify({"success": False, "error": "Authentication required (web session)"}), 401

    # Require CSRF and same-origin for reading configuration options
    if not _verify_csrf_header() or not _verify_same_origin():
        return jsonify({"success": False, "error": "CSRF/Origin validation failed"}), 403

    base_dir = Path(__file__).parent.parent
    example_path = base_dir / "data" / "example-config.py"
    config_path = base_dir / "data" / "config.py"

    example_config = _load_config_from_file(example_path)
    user_config = _load_config_from_file(config_path)
    comments_map, subsection_map = _extract_example_metadata(example_path)

    sections: list[ConfigSection] = []

    for section_name, example_section in example_config.items():
        if not isinstance(example_section, dict):
            continue

        user_section = user_config.get(section_name, {})
        items = _build_config_items(example_section, user_section, comments_map, subsection_map, [str(section_name)])

        # Add special client list items to DEFAULT section
        if section_name == "DEFAULT":
            # Check if they already exist in items
            existing_keys = {item.get("key", "") for item in items if item.get("key")}
            if "injecting_client_list" not in existing_keys:
                items.append(
                    {
                        "key": "injecting_client_list",
                        "value": user_section.get("injecting_client_list", []),
                        "source": "config" if "injecting_client_list" in user_section else "example",
                        "help": [
                            "A list of clients to use for injection (aka actually adding the torrent for uploading)",
                            'eg: ["qbittorrent", "rtorrent"]',
                        ],
                        "subsection": "CLIENT SETUP",
                    }
                )
            if "searching_client_list" not in existing_keys:
                items.append(
                    {
                        "key": "searching_client_list",
                        "value": user_section.get("searching_client_list", []),
                        "source": "config" if "searching_client_list" in user_section else "example",
                        "help": [
                            "A list of clients to search for torrents.",
                            'eg: ["qbittorrent", "qbittorrent_searching"]',
                            "will fallback to default_torrent_client if empty",
                        ],
                        "subsection": "CLIENT SETUP",
                    }
                )
            # Update subsection_map for these items
            subsection_map["DEFAULT/injecting_client_list"] = "CLIENT SETUP"
            subsection_map["DEFAULT/searching_client_list"] = "CLIENT SETUP"

        sections.append({"section": str(section_name), "items": items})

        if section_name == "TORRENT_CLIENTS":
            client_types = set()
            for item in items:
                if "children" in item and item["children"]:
                    client_type_item = next((c for c in item["children"] if c.get("key") == "torrent_client"), None)
                    if client_type_item:
                        client_types.add(client_type_item.get("value", "unknown"))
            sections[-1]["client_types"] = sorted(client_types, key=lambda x: (x != "qbit", x))

    return jsonify({"success": True, "sections": sections})


@app.route("/api/torrent_clients")
def torrent_clients():
    """Return list of available torrent client names from TORRENT_CLIENTS section"""
    # Require web session for config listing (disallow bearer token access)
    if not _is_authenticated():
        return jsonify({"success": False, "error": "Authentication required (web session)"}), 401

    # Require CSRF + same-origin for config-related reads
    if not _verify_csrf_header() or not _verify_same_origin():
        return jsonify({"success": False, "error": "CSRF/Origin validation failed"}), 403

    base_dir = Path(__file__).parent.parent
    config_path = base_dir / "data" / "config.py"

    user_config = _load_config_from_file(config_path)

    # Get clients only from user config
    user_clients = user_config.get("TORRENT_CLIENTS", {})

    # Include all configured clients in the dropdown
    client_names = list(user_clients.keys())

    return jsonify({"success": True, "clients": sorted(client_names)})


@app.route("/api/config_update", methods=["POST"])
def config_update():
    """Update a config value in data/config.py"""
    # Require authenticated web session and CSRF protection; disallow bearer/basic API auth
    if not _is_authenticated():
        return jsonify({"success": False, "error": "Authentication required (web session)"}), 401
    # Require CSRF + same-origin for config updates
    if not _verify_csrf_header() or not _verify_same_origin():
        return jsonify({"success": False, "error": "CSRF/Origin validation failed"}), 403
    data = request.json or {}
    path = data.get("path")
    raw_value = data.get("value")

    if not isinstance(path, list) or not all(isinstance(p, str) and p for p in path):
        return jsonify({"success": False, "error": "Invalid path"}), 400

    base_dir = Path(__file__).parent.parent
    example_path = base_dir / "data" / "example-config.py"
    config_path = base_dir / "data" / "config.py"

    example_config = _load_config_from_file(example_path)
    example_value = _get_nested_value(example_config, path)

    # Special handling for client lists that don't exist in example config
    key = path[-1] if path else ""
    if key in ["injecting_client_list", "searching_client_list"]:
        example_value = []  # Default to empty list
    elif example_value is None:
        return jsonify({"success": False, "error": "Path not found in example config"}), 400

    coerced_value = _coerce_config_value(raw_value, example_value)
    new_value_literal = _python_literal(coerced_value)

    # Special handling for client lists that should remain commented unless user provides values
    key = path[-1] if path else ""
    if key in ["injecting_client_list", "searching_client_list"] and coerced_value == []:
        # Remove the key from config if it exists
        try:
            # Load prior value for audit
            prior_config = _load_config_from_file(config_path)
            prior_value = _get_nested_value(prior_config, path)

            source = config_path.read_text(encoding="utf-8")
            updated_source = _remove_config_key_in_source(source, path)
            config_path.write_text(updated_source, encoding="utf-8")
            # Audit record for removal
            try:
                _write_audit_log("remove_key", path, prior_value, None, True)
            except Exception as ae:
                console.print(f"Failed to write config audit record: {ae}", markup=False)
        except Exception:
            return jsonify({"success": False, "error": "An error occurred while updating the configuration"}), 500
        return jsonify({"success": True, "value": _json_safe(coerced_value)})
    # Else proceed with normal update

    # Ensure prior_value is defined for the exception path below
    prior_value = None
    try:
        # Load prior value for audit
        prior_config = _load_config_from_file(config_path)
        prior_value = _get_nested_value(prior_config, path)

        source = config_path.read_text(encoding="utf-8")
        updated_source = _replace_config_value_in_source(source, path, new_value_literal)
        config_path.write_text(updated_source, encoding="utf-8")
        # Audit record for update
        try:
            _write_audit_log("update_value", path, prior_value, coerced_value, True)
        except Exception as ae:
            console.print(f"Failed to write config audit record: {ae}", markup=False)
    except Exception as e:
        # Attempt to log failed update attempt
        try:
            _write_audit_log("update_value", path, prior_value if prior_value is not None else None, coerced_value, False, str(e))
        except Exception as ae:
            console.print(f"Failed to write config audit failure record: {ae}", markup=False)
        return jsonify({"success": False, "error": "An error occurred while updating the configuration"}), 500

    return jsonify({"success": True, "value": _json_safe(coerced_value)})


@app.route("/api/config_remove_subsection", methods=["POST"])
def config_remove_subsection():
    """Remove a subsection (top-level key) from the user's config.py if present"""
    # Require authenticated web session and CSRF protection; disallow bearer/basic API auth
    if not _is_authenticated():
        return jsonify({"success": False, "error": "Authentication required (web session)"}), 401
    # Require CSRF + same-origin for config removal
    if not _verify_csrf_header() or not _verify_same_origin():
        return jsonify({"success": False, "error": "CSRF/Origin validation failed"}), 403

    data = request.json or {}
    path = data.get("path")

    if not isinstance(path, list) or not all(isinstance(p, str) and p for p in path):
        return jsonify({"success": False, "error": "Invalid path"}), 400

    base_dir = Path(__file__).parent.parent
    config_path = base_dir / "data" / "config.py"

    try:
        source = config_path.read_text(encoding="utf-8")
        updated = _remove_config_key_in_source(source, path)
        if updated == source:
            # Nothing changed
            return jsonify({"success": True, "value": None})
        config_path.write_text(updated, encoding="utf-8")
        return jsonify({"success": True})
    except Exception:
        return jsonify({"success": False, "error": "An error occurred while removing the configuration subsection"}), 500


@app.route("/api/tokens", methods=["GET", "POST", "DELETE"])
def api_tokens():
    """Manage API bearer tokens (create/list/revoke).

    Protected: requires a logged-in session or basic auth. Tokens themselves
    can be used as Bearer auth for API calls.
    """
    # Require a browser session (remember-me or login) and a valid CSRF token.
    # Disallow managing tokens via Basic or Bearer API auth to ensure token
    # lifecycle actions are only possible from the web UI with CSRF protection.
    # Use the encrypted-session helpers so we read values stored inside the
    # encrypted `enc` payload rather than top-level Flask session keys.
    if not _is_authenticated():
        return jsonify({"success": False, "error": "Authentication required (web session)"}), 401
    if not _verify_csrf_header():
        return jsonify({"success": False, "error": "CSRF validation failed"}), 403

    if request.method == "GET":
        store = _list_api_tokens()
        # Return metadata only (do not leak token values)
        tokens = [
            {"id": tid, "user": info.get("user"), "label": info.get("label"), "created": info.get("created"), "expiry": info.get("expiry")}
            for tid, info in store.items()
        ]
        read_only = False
        return jsonify({"success": True, "tokens": tokens, "read_only": read_only})

    if request.method == "POST":
        data = request.json or {}
        action = data.get("action")
        label = data.get("label", "")
        # No expiry: tokens are non-expiring by default;
        persisted = auth_mod.load_user()
        username = _session_get("username") or (request.authorization.username if request.authorization else None) or (persisted.get("username") if persisted else None)
        if not username:
            return jsonify({"success": False, "error": "Unable to determine username for token"}), 400

        # Two-step flow supported:
        # - action == 'generate' (or persist=false): generate a token and do NOT persist it.
        # - action == 'store': persist an externally-provided token string (token field required).
        if action == "store":
            token_value = data.get("token")
            if not token_value:
                return jsonify({"success": False, "error": "Token value required for store action"}), 400
            # Persist tokens to the config store
            ok = _persist_existing_api_token(token_value, username, label=label)
            if ok:
                return jsonify({"success": True, "persisted": True})
            return jsonify({"success": False, "error": "Failed to persist token (already exists?)"}), 400

        # default/generate
        persist_flag = bool(data.get("persist", True))
        token = _create_api_token(username, label=label, persist=persist_flag)
        persisted = persist_flag
        return jsonify({"success": True, "token": token, "persisted": persisted})

    if request.method == "DELETE":
        data = request.json or {}
        tid = data.get("id")
        if not tid:
            return jsonify({"success": False, "error": "Token id required"}), 400
        ok = _revoke_api_token(tid)
        if ok:
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Failed to revoke token"}), 500


@app.route("/api/browse")
def browse_path():
    """Browse filesystem paths"""
    requested = request.args.get("path", "")
    file_filter = request.args.get("filter", "video")  # 'video' or 'desc'
    try:
        path = _resolve_browse_path(requested)
    except ValueError as e:
        # Log details server-side, but avoid leaking paths/internal details to clients.
        console.print(f"Path resolution error for requested {requested!r}: {e}", markup=False)
        return jsonify({"error": "Invalid path specified", "success": False}), 400

    # Explicitly assert the resolved path is within allowed browse roots.
    try:
        _assert_safe_resolved_path(path)
    except ValueError:
        console.print(f"Path failed safety check: {requested!r}", markup=False)
        return jsonify({"error": "Invalid path specified", "success": False}), 400

    # Defensive sanity checks before using `path` in filesystem operations.
    safe_path = os.path.abspath(path)
    if '\x00' in safe_path:
        console.print("Path contains invalid characters", markup=False)
        return jsonify({"error": "Invalid path specified", "success": False}), 400
    if not os.path.isdir(safe_path):
        console.print("Requested path is not a directory", markup=False)
        return jsonify({"error": "Invalid path specified", "success": False}), 400

    console.print("Browsing path allowed", markup=False)

    try:
        items: list[BrowseItem] = []
        try:
            # `safe_path` was computed above; perform an explicit realpath
            # containment check using stdlib functions so static analyzers
            # can reason about the safety of the listing operation.
            real_safe = os.path.realpath(safe_path)
            allowed = False
            for root in _get_browse_roots():
                root_real = os.path.realpath(os.path.abspath(root))
                try:
                    if os.path.commonpath([real_safe, root_real]) == root_real:
                        allowed = True
                        break
                except ValueError:
                    # Different drives on Windows - not allowed
                    continue
            if not allowed:
                console.print(f"Path failed containment check before listing: {safe_path!r}", markup=False)
                return jsonify({"error": "Invalid path specified", "success": False}), 400

            for item in sorted(os.listdir(safe_path)):
                # Skip hidden files
                if item.startswith("."):
                    continue
                full_path = os.path.join(safe_path, item)
                # Explicitly assert each resolved child path is safe. If the
                # assertion fails for a specific entry, skip it rather than
                # failing the whole browse operation.
                try:
                    _assert_safe_resolved_path(full_path)
                except ValueError:
                    continue
                try:
                    is_dir = os.path.isdir(full_path)

                    # Skip files based on filter type
                    if not is_dir:
                        _, ext = os.path.splitext(item.lower())
                        if file_filter == "desc":
                            if ext not in SUPPORTED_DESC_EXTS:
                                continue
                        else:
                            # Default to video filter
                            if ext not in SUPPORTED_VIDEO_EXTS:
                                continue

                    items.append({"name": item, "path": full_path, "type": "folder" if is_dir else "file", "children": [] if is_dir else None})
                except (PermissionError, OSError):
                    continue

            console.print(f"Found {len(items)} items in {path}", markup=False)

        except PermissionError:
            console.print(f"Error: Permission denied: {path}", markup=False)
            return jsonify({"error": "Permission denied", "success": False}), 403

        # If caller used a bearer token, require it to be valid. Valid bearer
        # tokens are allowed without CSRF since they are intended for programmatic
        # access. Otherwise require an authenticated web session + CSRF + same-origin.
        bearer = _get_bearer_from_header()
        if bearer:
            if not _token_is_valid(bearer):
                return jsonify({"success": False, "error": "Forbidden (invalid token)"}), 403
        else:
            # Require session-based callers to be authenticated and provide CSRF + Origin
            if not _is_authenticated():
                return jsonify({"success": False, "error": "Authentication required (web session)"}), 401
            if not _verify_csrf_header() or not _verify_same_origin():
                return jsonify({"success": False, "error": "CSRF/Origin validation failed"}), 403

        return jsonify({"items": items, "success": True, "path": path, "count": len(items)})

    except Exception as e:
        console.print(f"Error browsing {path}: {e}", markup=False)
        console.print(traceback.format_exc(), markup=False)
        return jsonify({"error": "Error browsing path", "success": False}), 500


@app.route("/api/execute", methods=["POST", "OPTIONS"])
@limiter.limit("100 per hour", key_func=_rate_limit_key_func)
def execute_command():
    """Execute upload.py with interactive terminal support"""

    if request.method == "OPTIONS":
        return "", 204

    # Require CSRF token for execute POST requests
    if request.method == "POST" and not _verify_csrf_header():
        return jsonify({"error": "CSRF token missing or invalid", "success": False}), 403

    # If caller used a bearer token, ensure it is valid
    bearer = _get_bearer_from_header()
    if bearer and not _token_is_valid(bearer):
        return jsonify({"error": "Forbidden (invalid token)", "success": False}), 403

    try:
        # Prefer a silent JSON parse to avoid Werkzeug raising on malformed
        # payloads. If parsing fails, try form data or a few tolerant
        # fallbacks to extract common fields (path, args, session_id).
        data = None
        try:
            data = request.get_json(silent=True)
        except Exception:
            data = None

        if not data:
            # Try standard form-encoded body first
            try:
                if request.form:
                    data = request.form.to_dict()
            except Exception:
                data = None

        if not data:
            # As a last resort attempt to parse raw body text that may be
            # produced by shells which strip quoting or backslashes. We
            # attempt a few conservative transforms rather than executing
            # arbitrary code: 1) normalize single quotes to double quotes,
            # 2) quote unquoted object keys, then try json.loads. If that
            # fails, fall back to simple regex extraction of `path` and
            # `session_id` values.
            try:
                raw = (request.get_data(as_text=True) or "").strip()
                if raw:
                    # Quick normalization: single -> double quotes
                    candidate = raw.replace("'", '"')
                    # Quote unquoted keys like: {path:...} -> {"path":...}
                    candidate = re.sub(r'([\{\s,])([A-Za-z0-9_]+)\s*:', r'\1"\2":', candidate)
                    try:
                        data = json.loads(candidate)
                    except Exception:
                        # Regex extraction fallback for minimal fields
                        d: dict[str, str] = {}
                        m_path = re.search(r'path\s*[:=]\s*["\']?([^"\'\},]+)', raw)
                        m_sess = re.search(r'session_id\s*[:=]\s*["\']?([^"\'\},]+)', raw)
                        m_args = re.search(r'args\s*[:=]\s*["\']?([^"\'\}]+)', raw)
                        if m_path:
                            d['path'] = m_path.group(1)
                        if m_sess:
                            d['session_id'] = m_sess.group(1)
                        if m_args:
                            # Trim any trailing quote/comma characters and preserve spacing
                            raw_args = m_args.group(1).strip()
                            # Defensive: some shells or quoting can produce a
                            # concatenated fragment like `--debug,session_id:...`.
                            # Strip any trailing `,session_id` fragment or any
                            # comma followed by a session_id key so args remain
                            # clean.
                            raw_args = re.split(r',\s*(?:"?session_id|session_id)\b', raw_args)[0]
                            raw_args = raw_args.rstrip(',').strip().strip('"').strip("'")
                            d['args'] = raw_args
                        if d:
                            data = d
            except Exception:
                data = None

        if not data:
            return jsonify({"error": "No JSON data received", "success": False}), 400

        path = data.get("path")
        args = data.get("args", "")
        session_id = data.get("session_id", "default")
        # If a previous run for this session left state behind, attempt to
        # terminate/cleanup it so the new execution starts with a clean slate.
        with contextlib.suppress(Exception):
            existing = active_processes.pop(session_id, None)
            if existing:
                proc = existing.get("process")
                if proc and getattr(proc, "poll", None) is None:
                    with contextlib.suppress(Exception):
                        proc.kill()

        console.print(f"Execute request - Path: {path}, Args: {args}, Session: {session_id}", markup=False)

        if not path:
            return jsonify({"error": "Missing path", "success": False}), 400

        def generate():
            try:
                # Build command to run upload.py directly
                validated_path = _resolve_user_path(path, require_exists=True, require_dir=False)

                # Additional explicit assertion for static analysis: ensure the
                # resolved path is within allowed browse roots and contains no
                # invalid characters before using it in commands/subprocesses.
                try:
                    _assert_safe_resolved_path(validated_path)
                except ValueError:
                    yield f"data: {json.dumps({'type': 'error', 'data': 'Invalid execution path'})}\n\n"
                    return

                base_dir = Path(__file__).parent.parent
                upload_script = str(base_dir / "upload.py")
                command = [sys.executable, "-u", upload_script, validated_path]

                # Add arguments if provided
                if args:
                    import shlex

                    parsed_args = shlex.split(args)
                    try:
                        validated_args = _validate_upload_assistant_args(parsed_args)
                    except ValueError as err:
                        console.print(f"Invalid execution arguments: {err}", markup=False)
                        yield f"data: {json.dumps({'type': 'error', 'data': 'Invalid execution arguments'})}\n\n"
                        return
                    command.extend(validated_args)

                command_str = subprocess.list2cmdline(command)
                console.print(f"Running: {command_str}", markup=False)

                yield f"data: {json.dumps({'type': 'system', 'data': f'Executing: {command_str}'})}\n\n"

                # Decide whether to run as a subprocess or in-process. In-process
                # preserves Rich output and allows capturing console.input / cli_ui prompts.
                use_subprocess = bool(os.environ.get("UA_WEBUI_USE_SUBPROCESS", "").strip())

                if not use_subprocess:
                    # In-process execution path
                    import cli_ui as _cli_ui

                    from src import console as src_console

                    console.print("Running in-process (rich-captured) mode", markup=False)

                    # Prepare input queue for prompts
                    input_queue: queue.Queue[str] = queue.Queue()

                    # Import upload.main on the main thread to avoid thread-unsafe imports
                    # inside the worker thread. Importing here ensures any module-level
                    # side-effects run on the request/main thread rather than inside
                    # the worker thread.
                    try:
                        import upload as _upload

                        upload_main = _upload.main
                    except Exception as _e:
                        upload_main = None

                    # Prepare a recording Console to capture rich output
                    import io

                    from rich.console import Console as RichConsole

                    # Use an in-memory file for the recorder to avoid duplicating
                    # output to the real stdout. record=True still records renderables.
                    record_console = RichConsole(record=True, force_terminal=True, width=120, file=io.StringIO())

                    # Queue to serialize print actions from the worker thread
                    render_queue: queue.Queue[tuple[Any, dict[str, Any]]] = queue.Queue()

                    # Cancellation event for cooperative shutdown
                    cancel_event = threading.Event()

                    # Monkeypatch the existing shared console to record prints and intercept input
                    orig_console = src_console.console

                    # Avoid double-wrapping the console if already patched by a previous run
                    console_key = id(orig_console)
                    if console_key not in _ua_console_store:
                        # Store originals so we can restore later
                        _ua_console_store[console_key] = {
                            "orig_print": orig_console.print,
                            "orig_input": getattr(orig_console, "input", None),
                            "orig_ask_yes_no": None,
                            "orig_ask_string": None,
                        }

                        # Wrap print to duplicate into the recorder
                        orig_print = orig_console.print

                        def wrapped_print(*p_args: Any, **p_kwargs: Any) -> Any:
                            # Enqueue print calls to be applied from the SSE thread
                            with contextlib.suppress(Exception):
                                render_queue.put((p_args, p_kwargs))
                            return orig_print(*p_args, **p_kwargs)

                        orig_console.print = cast(Any, wrapped_print)

                        # Intercept console.input to send prompt to client and wait for queue
                        orig_input = getattr(orig_console, "input", None)

                        def wrapped_input(prompt: str = "") -> str:
                            # Print the prompt so it appears in the recorded output
                            with contextlib.suppress(Exception):
                                wrapped_print(prompt)
                            # Wait for input while respecting cancellation
                            while True:
                                if cancel_event.is_set():
                                    raise EOFError()
                                try:
                                    return input_queue.get(timeout=0.5)
                                except queue.Empty:
                                    continue
                                except Exception:
                                    raise

                        orig_console.input = cast(Any, wrapped_input)
                    else:
                        # Already wrapped; retrieve stored originals so restoration works
                        stored = _ua_console_store.get(console_key, {})
                        orig_print = stored.get("orig_print", orig_console.print)
                        orig_input = stored.get("orig_input", getattr(orig_console, "input", None))

                    # Monkeypatch cli_ui.ask_yes_no and ask_string similarly
                    orig_ask_yes_no = None
                    orig_ask_string = None
                    try:
                        orig_ask_yes_no = _cli_ui.ask_yes_no

                        def wrapped_ask_yes_no(*args, default: bool = False, **kwargs) -> bool:
                                # Support both signatures used across the codebase:
                                #   ask_yes_no(question, default=...)
                                #   ask_yes_no(color, question, default=...)
                                # Extract the question and default value from args/kwargs.
                                if len(args) >= 2:
                                    question = args[1]
                                elif len(args) == 1:
                                    question = args[0]
                                else:
                                    question = kwargs.get('question', '')

                                # If default was passed positionally (third arg), use it.
                                default_val = args[2] if len(args) >= 3 else kwargs.get('default', default)

                                with contextlib.suppress(Exception):
                                    wrapped_print(str(question))
                                # Wait for a response or cancellation
                                while True:
                                    if cancel_event.is_set():
                                        raise EOFError()
                                    try:
                                        resp = input_queue.get(timeout=0.5)
                                    except queue.Empty:
                                        continue
                                    except Exception:
                                        raise
                                    resp = (resp or "").strip().lower()
                                    if resp in ("y", "yes"):
                                        return True
                                    if resp in ("n", "no"):
                                        return False
                                    return default_val

                        _cli_ui.ask_yes_no = wrapped_ask_yes_no
                        # Save original ask_yes_no so external cleaners (eg. /api/kill)
                        # can restore it if the inproc run is terminated early.
                        try:
                            if console_key in _ua_console_store:
                                _ua_console_store[console_key]["orig_ask_yes_no"] = orig_ask_yes_no
                        except Exception:
                            pass

                        # ask_string: prompt user for an arbitrary string
                        try:
                            orig_ask_string = _cli_ui.ask_string

                            def wrapped_ask_string(prompt: str, _default: Optional[str] = None) -> str:
                                with contextlib.suppress(Exception):
                                    wrapped_print(prompt)
                                # Wait for input or cancellation
                                while True:
                                    if cancel_event.is_set():
                                        raise EOFError()
                                    try:
                                        resp = input_queue.get(timeout=0.5)
                                        return resp
                                    except queue.Empty:
                                        continue
                                    except Exception:
                                        raise

                            _cli_ui.ask_string = wrapped_ask_string
                            # Save original ask_string for external cleanup
                            try:
                                if console_key in _ua_console_store:
                                    _ua_console_store[console_key]["orig_ask_string"] = orig_ask_string
                            except Exception:
                                pass
                        except Exception:
                            orig_ask_string = None
                    except Exception:
                        orig_ask_yes_no = None

                    # Prepare sys.argv for upload.py to parse
                    old_argv = list(sys.argv)
                    try:
                        import shlex

                        parsed_args = []
                        if args:
                            parsed_args = shlex.split(args)
                            parsed_args = _validate_upload_assistant_args(parsed_args)

                        sys.argv = [str(upload_script), validated_path] + parsed_args

                        # Store in active_processes so /api/input can post into the queue
                        cast(Any, active_processes)[session_id] = {
                            "mode": "inproc",
                            "input_queue": input_queue,
                            "record_console": record_console,
                            "cancel_event": cancel_event,
                        }

                        # Run the upload main loop in a separate thread to avoid blocking SSE generator
                        def run_upload():
                            try:
                                # Run the async main() entry point of upload.py
                                import asyncio

                                # Use the pre-imported upload_main from the outer scope.
                                # If it wasn't available, attempt a safe import here as fallback.
                                nonlocal_upload = upload_main
                                if nonlocal_upload is None:
                                    try:
                                        import upload as _upload_fallback

                                        nonlocal_upload = _upload_fallback.main
                                    except Exception:
                                        nonlocal_upload = None

                                # Ensure Windows event loop policy when needed
                                if sys.platform == "win32":
                                    with contextlib.suppress(Exception):
                                        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                                if nonlocal_upload is None:
                                    raise RuntimeError("upload.main not available for in-process execution")
                                asyncio.run(nonlocal_upload())
                            except Exception as e:
                                # If the exception is the cooperative cancellation marker,
                                # print a short, non-alarming message and avoid printing
                                # the full traceback which can confuse the operator.
                                try:
                                    if isinstance(e, EOFError):
                                        console.print("In-process run cancelled (Ctrl+C)", markup=False)
                                    else:
                                        console.print(f"In-process execution error: {e}", markup=False)
                                        console.print(traceback.format_exc(), markup=False)
                                except Exception:
                                    with contextlib.suppress(Exception):
                                        console.print("In-process run ended", markup=False)
                            finally:
                                # Restore sys.argv in finally block
                                # Restore patched console
                                console_key = id(src_console.console)
                                if console_key in _ua_console_store:
                                    origs = _ua_console_store[console_key]
                                    src_console.console.print = origs["orig_print"]
                                    if "orig_input" in origs and origs["orig_input"] is not None:
                                        src_console.console.input = origs["orig_input"]
                                    # Restore cli_ui patched functions if present
                                    try:
                                        if "orig_ask_yes_no" in origs and origs["orig_ask_yes_no"] is not None:
                                            _cli_ui.ask_yes_no = origs["orig_ask_yes_no"]
                                    except Exception:
                                        pass
                                    try:
                                        if "orig_ask_string" in origs and origs["orig_ask_string"] is not None:
                                            _cli_ui.ask_string = origs["orig_ask_string"]
                                    except Exception:
                                        pass
                                    del _ua_console_store[console_key]
                                # Release lock to allow next inproc run
                                inproc_lock.release()

                        worker = threading.Thread(target=run_upload, daemon=True)
                        # Acquire lock to prevent concurrent inproc runs (avoids cross-session interference)
                        # Use a timed acquire so we don't block indefinitely; if we fail
                        # to acquire the lock, return an error to the client.
                        try:
                            acquired = inproc_lock.acquire(timeout=2)
                        except TypeError:
                            # Some older Python runtimes may not support timeout parameter
                            acquired = inproc_lock.acquire(blocking=False)

                        if not acquired:
                            console.print(f"Failed to acquire inproc lock for session {session_id}; another inproc run may be active", markup=False)
                            yield f"data: {json.dumps({'type': 'error', 'data': 'Another in-process run is active'})}\n\n"
                            return

                        worker.start()

                        # Record worker thread for debugging/cleanup
                        try:
                            if session_id in active_processes:
                                cast(Any, active_processes[session_id])["worker"] = worker
                        except Exception:
                            pass

                        console.print(f"Started inproc worker for session {session_id}: {worker.name}", markup=False)

                        # Stream full HTML snapshots from the recorder while the worker runs.
                        # To avoid spinning the SSE thread and growing the server task queue
                        # when the uploader prints heavily, block waiting for print events
                        # with a short timeout and coalesce multiple prints into a
                        # single exported snapshot.
                        last_body = ""
                        try:
                            while worker.is_alive():
                                try:
                                    # Wait for the next print event (blocks briefly). This
                                    # prevents the generator from busy-waiting and tying up
                                    # Waitress worker threads.
                                    r_args, r_kwargs = render_queue.get(timeout=0.5)
                                    with contextlib.suppress(Exception):
                                        record_console.print(*r_args, **r_kwargs)

                                    # Drain any additional queued prints so we can coalesce
                                    # them into a single exported snapshot.
                                    while not render_queue.empty():
                                        try:
                                            r_args, r_kwargs = render_queue.get_nowait()
                                        except queue.Empty:
                                            break
                                        with contextlib.suppress(Exception):
                                            record_console.print(*r_args, **r_kwargs)

                                    # Export and yield a full HTML snapshot only when the
                                    # rendered body has changed.
                                    html_doc = record_console.export_html(inline_styles=True)
                                    m = re.search(r"<body[^>]*>(.*?)</body>", html_doc, re.S | re.I)
                                    body = m.group(1).strip() if m else html_doc
                                    if body != last_body:
                                        last_body = body
                                        yield f"data: {json.dumps({'type': 'html_full', 'data': body})}\n\n"
                                except queue.Empty:
                                    # No print activity within the timeout — send a keepalive
                                    # to keep the SSE connection alive without busy-waiting.
                                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
                                except Exception:
                                    # Swallow per-iteration errors to keep the stream alive.
                                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"

                            # Worker finished; drain any remaining prints and send final snapshot
                            while not render_queue.empty():
                                try:
                                    r_args, r_kwargs = render_queue.get_nowait()
                                except queue.Empty:
                                    break
                                with contextlib.suppress(Exception):
                                    record_console.print(*r_args, **r_kwargs)

                            try:
                                html_doc = record_console.export_html(inline_styles=True)
                                m = re.search(r"<body[^>]*>(.*?)</body>", html_doc, re.S | re.I)
                                body = m.group(1).strip() if m else html_doc
                                if body != last_body:
                                    yield f"data: {json.dumps({'type': 'html_full', 'data': body})}\n\n"
                            except Exception:
                                pass
                        except Exception:
                            # Ensure generator continues and yields a final keepalive on error
                            yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"

                    finally:
                        # restore patched functions and argv
                        try:
                            # Prefer restoring originals from the module-level store
                            console_key = id(orig_console)
                            if console_key in _ua_console_store:
                                stored = _ua_console_store.pop(console_key, {})
                                with contextlib.suppress(Exception):
                                    orig_console.print = stored.get("orig_print", orig_console.print)
                                with contextlib.suppress(Exception):
                                    orig_in = stored.get("orig_input", None)
                                    if orig_in is not None:
                                        orig_console.input = orig_in
                        except Exception:
                            # best-effort restore using locals
                            with contextlib.suppress(Exception):
                                orig_console.print = orig_print
                            with contextlib.suppress(Exception):
                                if orig_input is not None:
                                    orig_console.input = orig_input

                        with contextlib.suppress(Exception):
                            if orig_ask_yes_no is not None:
                                _cli_ui.ask_yes_no = orig_ask_yes_no
                        with contextlib.suppress(Exception):
                            if orig_ask_string is not None:
                                _cli_ui.ask_string = orig_ask_string

                        sys.argv = old_argv

                        # Remove process tracking for this session
                        with contextlib.suppress(Exception):
                            active_processes.pop(session_id, None)

                    return

                else:
                    # Set environment to unbuffered and force line buffering
                    env = os.environ.copy()
                    env["PYTHONUNBUFFERED"] = "1"
                    env["PYTHONIOENCODING"] = "utf-8"
                    # Disable Python output buffering

                    # Sanity-check the working directory used for the subprocess.
                    # `base_dir` is computed from the application `__file__`, but
                    # perform lightweight validation to satisfy static analysis
                    # tools and ensure we do not pass uncontrolled input here.
                    if '\x00' in str(base_dir) or not str(base_dir):
                        raise ValueError("Invalid execution directory")
                    if not os.path.isabs(str(base_dir)):
                        base_dir = os.path.abspath(str(base_dir))

                    # Extra validation for the constructed command to guard
                    # against command-injection and to make validation explicit
                    # for static analysis tools.
                    try:
                        # Ensure command is a list of strings
                        if not isinstance(command, list) or not all(isinstance(a, str) for a in command):
                            raise ValueError("Invalid command")

                        # Re-assert the execution path is safe
                        try:
                            _assert_safe_resolved_path(command[3] if len(command) > 3 else command[-1])
                        except Exception:
                            # Fallback: validated_path is expected at position 3 for subprocess
                            try:
                                _assert_safe_resolved_path(validated_path)
                            except Exception as err:
                                raise ValueError("Invalid execution path") from err

                        # Ensure the upload_script is the expected script under the repo
                        try:
                            expected_script = os.path.realpath(str(Path(base_dir) / "upload.py"))
                            script_real = os.path.realpath(str(command[2]))
                            if script_real != expected_script:
                                raise ValueError("Invalid script path")
                        except IndexError as err:
                            raise ValueError("Invalid command structure") from err

                        # Disallow shell metacharacters in any argument
                        forbidden = set(";&|$`><*?~!\n\r\x00")
                        for a in command:
                            if any(ch in a for ch in forbidden):
                                raise ValueError("Invalid characters in command argument")
                    except Exception as err:
                        console.print(f"Refusing to run unsafe command: {err}", markup=False)
                        yield f"data: {json.dumps({'type': 'error', 'data': 'Unsafe execution request'})}\n\n"
                        return

                    process = subprocess.Popen(  # lgtm[py/command-line-injection]
                        command,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=0,  # Completely unbuffered
                        cwd=str(base_dir),
                        env=env,
                        universal_newlines=True,
                    )

                    # Store process for input handling (no queue needed)
                    active_processes[session_id] = {"process": process}

                    # Wrap subprocess handling in try/finally to guarantee cleanup
                    try:
                        # Thread to read stdout - stream raw output with ANSI codes
                        def read_stdout():
                            try:
                                if process.stdout is None:
                                    return
                                while True:
                                    # Read in small chunks for real-time streaming
                                    chunk = process.stdout.read(1)
                                    if not chunk:
                                        break
                                    output_queue.put(("stdout", chunk))
                            except Exception as e:
                                console.print(f"stdout read error: {e}", markup=False)

                        # Thread to read stderr - stream raw output
                        def read_stderr():
                            try:
                                if process.stderr is None:
                                    return
                                while True:
                                    chunk = process.stderr.read(1)
                                    if not chunk:
                                        break
                                    output_queue.put(("stderr", chunk))
                            except Exception as e:
                                console.print(f"stderr read error: {e}", markup=False)

                        output_queue: queue.Queue[tuple[str, str]] = queue.Queue()

                        # Start threads (no input thread needed - we write directly)
                        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
                        stderr_thread = threading.Thread(target=read_stderr, daemon=True)

                        stdout_thread.start()
                        stderr_thread.start()

                        # Record threads and output queue for debugging/cleanup
                        try:
                            if session_id in active_processes:
                                info = cast(Any, active_processes[session_id])
                                info["stdout_thread"] = stdout_thread
                                info["stderr_thread"] = stderr_thread
                                info["output_queue"] = output_queue
                        except Exception:
                            pass

                        console.print(f"Started subprocess reader threads for session {session_id}: stdout={stdout_thread.name}, stderr={stderr_thread.name}", markup=False)

                        def _read_output(q: queue.Queue[tuple[str, str]]) -> tuple[bool, Union[tuple[str, str], None]]:
                            try:
                                return True, q.get(timeout=0.1)
                            except queue.Empty:
                                return False, None

                        # Stream output as buffered chunks and always emit HTML fragments
                        # If we are running the upload as a subprocess, stream ANSI->HTML as before.
                        buffers: dict[str, str] = {"stdout": "", "stderr": ""}

                        while process.poll() is None or not output_queue.empty():
                            has_output, output = _read_output(output_queue)
                            if has_output and output is not None:
                                output_type, char = output
                                if output_type not in buffers:
                                    buffers[output_type] = ""
                                buffers[output_type] += char

                                # Flush on newline or when buffer grows large
                                if char == "\n" or len(buffers[output_type]) > 512:
                                    chunk = buffers[output_type]
                                    buffers[output_type] = ""

                                    # Convert to HTML fragment. If helper missing, escape and wrap in <pre>
                                    try:
                                        if ansi_to_html:
                                            html_fragment = ansi_to_html(chunk)
                                        else:
                                            import html as _html

                                            html_fragment = f"<pre>{_html.escape(chunk)}</pre>"

                                        yield f"data: {json.dumps({'type': 'html', 'data': html_fragment, 'origin': output_type})}\n\n"
                                    except Exception as e:
                                        console.print(f"HTML conversion error: {e}", markup=False)
                                        import html as _html

                                        html_fragment = f"<pre>{_html.escape(chunk)}</pre>"
                                        yield f"data: {json.dumps({'type': 'html', 'data': html_fragment, 'origin': output_type})}\n\n"
                            else:
                                # keepalive to keep the SSE connection alive
                                yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"

                        # Flush remaining buffers as HTML
                        for t, remaining in list(buffers.items()):
                            if remaining:
                                try:
                                    if ansi_to_html:
                                        html_fragment = ansi_to_html(remaining)
                                    else:
                                        import html as _html

                                        html_fragment = f"<pre>{_html.escape(remaining)}</pre>"

                                    yield f"data: {json.dumps({'type': 'html', 'data': html_fragment, 'origin': t})}\n\n"

                                except Exception as e:
                                    console.print(f"HTML flush error: {e}", markup=False)
                                    import html as _html

                                    html_fragment = f"<pre>{_html.escape(remaining)}</pre>"
                                    yield f"data: {json.dumps({'type': 'html', 'data': html_fragment, 'origin': t})}\n\n"

                        # Wait for process to finish
                        process.wait()

                        # Clean up (normal path)
                        if session_id in active_processes:
                            del active_processes[session_id]

                        yield f"data: {json.dumps({'type': 'exit', 'code': process.returncode})}\n\n"
                    finally:
                        # Ensure subprocess pipes are closed to avoid leaking file handles
                        with contextlib.suppress(Exception):
                            if process.stdin is not None:
                                process.stdin.close()
                        with contextlib.suppress(Exception):
                            if process.stdout is not None:
                                process.stdout.close()
                        with contextlib.suppress(Exception):
                            if process.stderr is not None:
                                process.stderr.close()
                        # Ensure we remove tracking entry if still present
                        with contextlib.suppress(Exception):
                            if session_id in active_processes:
                                del active_processes[session_id]

            except Exception as e:
                console.print(f"Execution error for session {session_id}: {e}", markup=False)
                console.print(traceback.format_exc(), markup=False)
                yield f"data: {json.dumps({'type': 'error', 'data': 'Execution error'})}\n\n"

                # Clean up on error
                if session_id in active_processes:
                    del active_processes[session_id]

        return Response(generate(), mimetype="text/event-stream")

    except Exception as e:
        console.print(f"Request error: {e}", markup=False)
        console.print(traceback.format_exc(), markup=False)
        return jsonify({"error": "Request error", "success": False}), 500


@app.route("/api/input", methods=["POST"])
@limiter.limit("200 per hour", key_func=_rate_limit_key_func)
def send_input():
    """Send user input to running process"""
    try:
        data = request.json
        session_id = data.get("session_id", "default")
        user_input = data.get("input", "")

        # Received input for session (logged at debug level previously) - keep minimal output

        # Authorization: allow either a valid bearer token (programmatic clients)
        # or an authenticated web session. Bearer tokens are validated by
        # `_token_is_valid` (valid token grants access).
        bearer = _get_bearer_from_header()
        if bearer:
            if not _token_is_valid(bearer):
                return jsonify({"error": "Forbidden (invalid token)", "success": False}), 403
        else:
            # Require a web session for non-token callers
            if not _is_authenticated():
                return jsonify({"error": "Authentication required (web session)" , "success": False}), 401

        if session_id not in active_processes:
            return jsonify({"error": "No active process", "success": False}), 404

        # If this session is an in-process run, push to its input queue
        try:
            process_info = active_processes[session_id]
            if process_info.get("mode") == "inproc":
                raw_q = process_info.get("input_queue")
                if raw_q is None:
                    return jsonify({"error": "No input queue", "success": False}), 500
                q = raw_q
                q.put(user_input)
                return jsonify({"success": True})

            # Otherwise write to subprocess stdin
            # Always add newline to send the input
            input_with_newline = user_input + "\n"

            process = process_info.get("process")
            if process is None:
                return jsonify({"error": "No process found", "success": False}), 500

            if process.poll() is None:  # Process still running
                if process.stdin is not None:
                    process.stdin.write(input_with_newline)
                    process.stdin.flush()
                    console.print(f"Sent to stdin: '{input_with_newline.strip()}'", markup=False)
            else:
                console.print(f"Process already terminated for session {session_id}", markup=False)
                return jsonify({"error": "Process not running", "success": False}), 400

        except Exception as e:
            console.print(f"Error handling input for session {session_id}: {e}", markup=False)
            console.print(traceback.format_exc(), markup=False)
            return jsonify({"error": "Failed to handle input", "success": False}), 500

        return jsonify({"success": True})

    except Exception as e:
        console.print(f"Input error: {e}", markup=False)
        console.print(traceback.format_exc(), markup=False)
        return jsonify({"error": "Input error", "success": False}), 500


@app.route("/api/kill", methods=["POST"])
@limiter.limit("50 per hour", key_func=_rate_limit_key_func)
def kill_process():
    """Kill a running process"""
    try:
        data = request.json
        session_id = data.get("session_id")

        console.print(f"Kill request for session {session_id}", markup=False)

        # Authorization: allow either a valid bearer token or an authenticated web session
        bearer = _get_bearer_from_header()
        if bearer:
            if not _token_is_valid(bearer):
                return jsonify({"error": "Forbidden (invalid token)", "success": False}), 403
        else:
            if not _is_authenticated():
                return jsonify({"error": "Authentication required (web session)" , "success": False}), 401

        if session_id not in active_processes:
            return jsonify({"error": "No active process", "success": False}), 404

        process_info = active_processes[session_id]
        mode = process_info.get('mode')

        # If this is an in-process run, perform best-effort cleanup of patched
        # console state and release the inproc lock so future inproc runs can start.
        if mode == 'inproc':
            # Signal cancellation to the inproc worker and attempt to join it
            try:
                cancel_event = process_info.get("cancel_event")
                if isinstance(cancel_event, threading.Event):
                    cancel_event.set()
                worker = process_info.get("worker")
                if isinstance(worker, threading.Thread):
                    worker.join(timeout=2)
            except Exception:
                pass

            # Attempt to restore any patched console/cli state from the
            # module-level store so future runs have working print/input.
            try:
                with contextlib.suppress(Exception):
                    # Prefer restoring originals tied to the current src.console
                    try:
                        from src import console as _src_console
                        ck = id(_src_console.console)
                        if ck in _ua_console_store:
                            origs = _ua_console_store.pop(ck)
                            with contextlib.suppress(Exception):
                                _src_console.console.print = origs.get("orig_print", _src_console.console.print)
                            with contextlib.suppress(Exception):
                                orig_in = origs.get("orig_input", None)
                                if orig_in is not None:
                                    _src_console.console.input = orig_in
                            # Restore any cli_ui wrappers if we have originals
                            try:
                                import cli_ui as _cli_ui
                                with contextlib.suppress(Exception):
                                    if "orig_ask_yes_no" in origs and origs["orig_ask_yes_no"] is not None:
                                        _cli_ui.ask_yes_no = origs["orig_ask_yes_no"]
                                with contextlib.suppress(Exception):
                                    if "orig_ask_string" in origs and origs["orig_ask_string"] is not None:
                                        _cli_ui.ask_string = origs["orig_ask_string"]
                            except Exception:
                                pass
                    except Exception:
                        # Best-effort: if we can't import src.console, fall back to
                        # restoring any stored callables into the module-level
                        # `console` we imported at module import time.
                        try:
                            ck = id(console)
                            if ck in _ua_console_store:
                                origs = _ua_console_store.pop(ck)
                                with contextlib.suppress(Exception):
                                    console.print = origs.get("orig_print", console.print)
                                with contextlib.suppress(Exception):
                                    orig_in = origs.get("orig_input", None)
                                    if orig_in is not None:
                                        console.input = orig_in
                        except Exception:
                            pass

                    # If any other entries remain in the store, drop them to avoid
                    # leaking references — they are unlikely to be useful now.
                    _ua_console_store.clear()
            except Exception:
                pass

            # Release inproc lock if held; best-effort only.
            with contextlib.suppress(Exception):
                if inproc_lock.locked():
                    inproc_lock.release()

            # Remove tracking entry
            with contextlib.suppress(Exception):
                if session_id in active_processes:
                    del active_processes[session_id]

            console.print(f"In-process run terminated for session {session_id}", markup=False)
            return jsonify({"success": True, "message": "In-process run terminated and console state wiped"})

        # Otherwise assume subprocess.Popen case
        # Retrieve subprocess handle
        process = process_info.get("process")
        if process is None:
            return jsonify({"error": "No process found", "success": False}), 500

        try:
            # Terminate the process
            process.terminate()

            # Give it a moment to terminate gracefully
            try:
                process.wait(timeout=2)
            except Exception:
                # Force kill if it doesn't terminate
                process.kill()

            # Close any pipes to avoid leaking handles
            with contextlib.suppress(Exception):
                if process.stdin is not None:
                    process.stdin.close()
            with contextlib.suppress(Exception):
                if process.stdout is not None:
                    process.stdout.close()
            with contextlib.suppress(Exception):
                if process.stderr is not None:
                    process.stderr.close()

        finally:
            # Clean up tracking entry regardless
            # Attempt to join reader threads if present
            try:
                info = active_processes.get(session_id, {})
                stdout_t = info.get("stdout_thread")
                stderr_t = info.get("stderr_thread")
                if isinstance(stdout_t, threading.Thread):
                    console.print(f"Joining stdout thread for session {session_id}", markup=False)
                    stdout_t.join(timeout=1)
                if isinstance(stderr_t, threading.Thread):
                    console.print(f"Joining stderr thread for session {session_id}", markup=False)
                    stderr_t.join(timeout=1)
            except Exception:
                pass

            with contextlib.suppress(Exception):
                if session_id in active_processes:
                    del active_processes[session_id]

        console.print(f"Process killed for session {session_id}", markup=False)
        console.print(f"Post-kill snapshot: {_debug_process_snapshot(session_id)}", markup=False)
        return jsonify({"success": True, "message": "Process terminated"})

    except Exception as e:
        console.print(f"Kill error: {e}", markup=False)
        console.print(traceback.format_exc(), markup=False)
        return jsonify({"error": "Kill error", "success": False}), 500


@app.errorhandler(404)
def not_found(_e: Exception):
    return jsonify({"error": "Not found", "success": False}), 404


@app.errorhandler(500)
def internal_error(e: Exception):
    console.print(f"500 error: {str(e)}", markup=False)
    console.print(traceback.format_exc(), markup=False)
    return jsonify({"error": "Internal server error", "success": False}), 500
