"""Authentication and credential encryption helpers.

Provides:
- Argon2 password hashing/verification for a single local user
- Session secret loading (env/file) and AES-GCM key derivation
- AES-GCM encrypt/decrypt helpers that return base64 payloads
- File-backed user and credential storage under XDG config dir
"""
from __future__ import annotations

import base64
import json
import logging
import math
import os
import string
from contextlib import suppress
from pathlib import Path
from typing import Optional

from argon2 import PasswordHasher
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

log = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption or key derivation fails."""
    pass

# Defaults and env var names
ENV_SESSION_SECRET = "SESSION_SECRET"
ENV_SESSION_SECRET_FILE = "SESSION_SECRET_FILE"


def get_config_dir() -> Path:
    # Detect container runtime: prefer repository `data/` when running in Docker
    def _running_in_docker() -> bool:
        # Allow explicit override via env var
        v = os.environ.get("IN_DOCKER") or os.environ.get("RUNNING_IN_CONTAINER")
        if v and v.lower() in ("1", "true", "yes"):
            return True
        # Common Docker indicator file
        try:
            if Path("/.dockerenv").exists():
                return True
        except Exception:
            pass
        # Check cgroup for container hints
        try:
            with open("/proc/1/cgroup") as f:
                txt = f.read()
                if any(k in txt for k in ("docker", "kubepods", "containerd")):
                    return True
        except Exception:
            pass
        return False

    # Repository data dir
    repo_dir = Path(__file__).resolve().parent.parent / "data"
    # If running in Docker, prefer the repository `data/` directory.
    if _running_in_docker():
        return repo_dir

    # Windows: prefer roaming AppData (per-user persistent config)
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Upload_Assistant"
    # Unix-like: prefer XDG_CONFIG_HOME, fall back to repo data/config or ~/.config/upload-assistant
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "upload-assistant"
    # fallback to repository data/config when available (developer mode)
    if repo_dir.exists():
        return repo_dir
    return Path.home() / ".config" / "upload-assistant"


def load_session_secret() -> bytes:
    """Load or generate a session secret used for session signing and key derivation.

    Priority:
    - `SECRET_KEY` env var (compat fallback)
    - Otherwise generate new random 64-byte secret
    """
    def _ensure_min_length(b: bytes) -> bytes:
        if not b or len(b) < 32:
            raise ValueError("session secret must be at least 32 bytes")
        return b

    # Priority: explicit env var
    s = os.environ.get(ENV_SESSION_SECRET)
    if s:
        return _ensure_min_length(s.encode("utf-8"))

    # Config-file path env override (explicit file path)
    f = os.environ.get(ENV_SESSION_SECRET_FILE)
    if f and Path(f).exists():
        try:
            txt = Path(f).read_text(encoding="utf-8").splitlines()[0].strip()
            # Support hex-encoded and raw strings
            try:
                return _ensure_min_length(bytes.fromhex(txt))
            except Exception:
                return _ensure_min_length(txt.encode("utf-8"))
        except Exception:
            pass

    # Compatibility fallback
    s2 = os.environ.get("SECRET_KEY")
    if s2:
        return _ensure_min_length(s2.encode("utf-8"))

    # Otherwise, persist a generated secret in the config dir so it remains
    # stable across restarts. Use 64 bytes and store as hex.
    from secrets import token_bytes

    cfg = get_config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    secret_file = cfg / "session_secret"
    if secret_file.exists():
        try:
            txt = secret_file.read_text(encoding="utf-8").splitlines()[0].strip()
            try:
                return _ensure_min_length(bytes.fromhex(txt))
            except Exception:
                return _ensure_min_length(txt.encode("utf-8"))
        except Exception:
            pass

    # Generate and persist
    try:
        b = token_bytes(64)
        with open(secret_file, "w", encoding="utf-8") as fobj:
            fobj.write(b.hex())
        with suppress(Exception):
            # Tighten permissions when possible
            os.chmod(secret_file, 0o600)
        return b
    except Exception:
        # Last-resort ephemeral
        return token_bytes(64)


def derive_aes_key(session_secret: bytes) -> bytes:
    """Derive a 32-byte AES key from the session secret (first 32 bytes).

    Warning: If the session secret changes, previously encrypted credentials cannot be decrypted.
    """
    if not session_secret:
        raise ValueError("missing session secret")
    # Ensure length >=32
    b = bytes(session_secret)
    if len(b) < 32:
        b = b.ljust(32, b"0")
    return b[:32]


ph = PasswordHasher()


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(hash: str, password: str) -> bool:
    try:
        return ph.verify(hash, password)
    except Exception:
        return False


def _get_user_file() -> Path:
    cfg = get_config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    return cfg / "webui_auth.json"


def _get_master_key() -> bytes:
    """Return the derived AES key used to encrypt per-field keys."""
    return derive_aes_key(load_session_secret())


def _generate_field_key() -> bytes:
    from secrets import token_bytes

    return token_bytes(32)


def _pack_field(extras: dict, field: str, plaintext: Optional[str]) -> None:
    """Store a field under `extras['fields'][field]` with its own random key.

    Structure:
    extras['fields'][field] = {
        'enc': <encrypt_text(field_key, plaintext)>,
        'key_enc': <encrypt_text(master_key, field_key_hex)>
    }
    """
    if extras is None:
        return
    fields = extras.get("fields") or {}
    if plaintext is None:
        fields.pop(field, None)
        extras["fields"] = fields
        return

    # Obtain master key; fail loudly if unavailable
    try:
        master = _get_master_key()
    except Exception as e:
        log.error("failed to derive master key for field '%s': %s", field, e)
        raise EncryptionError(f"failed to derive master key for field '{field}'") from e

    if not master:
        msg = f"master key is falsy when packing field '{field}'"
        log.error(msg)
        raise EncryptionError(msg)

    # Generate a random per-field key
    try:
        fk = _generate_field_key()
    except Exception as e:
        log.error("failed to generate field key for '%s': %s", field, e)
        raise EncryptionError(f"failed to generate field key for '{field}'") from e

    # Encrypt the plaintext with the field key
    try:
        enc = encrypt_text(fk, plaintext)
    except Exception as e:
        log.error("encryption failed for field '%s': %s", field, e)
        raise EncryptionError(f"encryption failed for field '{field}'") from e

    # Encrypt the field key with the master key
    try:
        key_enc = encrypt_text(master, fk.hex())
    except Exception as e:
        log.error("failed to encrypt field key for '%s': %s", field, e)
        raise EncryptionError(f"failed to encrypt field key for '{field}'") from e

    fields[field] = {"enc": enc, "key_enc": key_enc}
    extras["fields"] = fields


def _unpack_field(extras: dict, field: str) -> Optional[str]:
    if not extras:
        return None
    fields = extras.get("fields") or {}
    info = fields.get(field)
    if not info:
        return None
    enc = info.get("enc")
    key_enc = info.get("key_enc")
    # Try to decrypt key_enc with master key
    try:
        master = _get_master_key()
    except Exception:
        master = None

    if key_enc and master:
        try:
            fk_hex = decrypt_text(master, key_enc)
            if fk_hex:
                fk = bytes.fromhex(fk_hex)
                val = decrypt_text(fk, enc) if enc else None
                return val
        except Exception:
            pass

    return None


def create_user(username: str, password: str) -> None:
    path = _get_user_file()
    # Prevent creating a new user if one already exists. Persisted user is authoritative.
    if path.exists():
        raise ValueError("a user account already exists")
    # Enforce minimum password entropy to ensure user-chosen secrets are strong.
    # Estimate entropy by character-class pool size heuristic: lowercase, uppercase,
    # digits, punctuation. This provides a conservative approximation of bits.
    def _password_entropy(pw: str) -> float:
        pool = 0
        if any(c.islower() for c in pw):
            pool += 26
        if any(c.isupper() for c in pw):
            pool += 26
        if any(c.isdigit() for c in pw):
            pool += 10
        if any(c in string.punctuation for c in pw):
            pool += len(string.punctuation)
        # If no recognized classes, fall back to unique character count
        if pool == 0:
            pool = max(1, len(set(pw)))
        return math.log2(pool) * len(pw)

    if _password_entropy(password) < 48:
        raise ValueError("password must have at least 48 bits of entropy")

    extras = {}
    # Pack username into per-field encrypted storage. Fail loudly on error.
    _pack_field(extras, "username", username)

    key = _get_master_key()
    extras_enc = encrypt_text(key, json.dumps(extras, separators=(",",":"), ensure_ascii=False))
    username_enc = encrypt_text(key, username)

    data = {"username_enc": username_enc, "password_hash": hash_password(password), "extras_enc": extras_enc}
    path.write_text(json.dumps(data), encoding="utf-8")


def load_user() -> Optional[dict]:
    path = _get_user_file()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    # Attempt to decrypt extras blob (contains per-field encrypted values)
    try:
        key = _get_master_key()
        extras = {}
        extras_enc = data.get("extras_enc")
        if extras_enc:
            dec = decrypt_text(key, extras_enc)
            if dec:
                extras = json.loads(dec)
                if isinstance(extras, dict):
                    data["extras"] = extras
        # Decrypt username
        username_enc = data.get("username_enc")
        if username_enc:
            username = decrypt_text(key, username_enc)
            if username:
                data["username"] = username
        # For backwards compatibility, if username not decrypted, try plain or unpack from extras
        if "username" not in data:
            # Try plain
            plain_username = data.get("username")
            if plain_username:
                data["username"] = plain_username
            else:
                # Try unpack from extras
                try:
                    username = _unpack_field(extras, "username")
                    if username:
                        data["username"] = username
                except Exception:
                    pass
    except Exception:
        pass

    return data


def get_totp_secret() -> Optional[str]:
    u = load_user()
    if not u:
        return None
    extras = u.get("extras") or {}
    # Use per-field unpack
    val = _unpack_field(extras, "totp_secret")
    if val is not None:
        return val
    # Backwards compat: older code may have totp_secret in extras dict directly
    return extras.get("totp_secret")


def set_totp_secret(secret: Optional[str]) -> None:
    # Read raw file, update extras, re-encrypt
    path = _get_user_file()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    extras = {}
    try:
        extras_enc = raw.get("extras_enc")
        if extras_enc:
            key = _get_master_key()
            dec = decrypt_text(key, extras_enc)
            if dec:
                extras = json.loads(dec)
    except Exception:
        extras = {}

    # Pack/unpack with per-field keys
    # Pack/unpack with per-field keys; let encryption errors propagate
    _pack_field(extras, "totp_secret", secret)

    key = _get_master_key()
    raw["extras_enc"] = encrypt_text(key, json.dumps(extras, separators=(",",":"), ensure_ascii=False))

    path.write_text(json.dumps(raw), encoding="utf-8")


def get_recovery_hashes() -> list[str]:
    u = load_user()
    if not u:
        return []
    extras = u.get("extras") or {}
    val = _unpack_field(extras, "recovery_hashes")
    if val is not None:
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    # Backwards compat
    return extras.get("recovery_hashes") or []


def set_recovery_hashes(hashes: list[str]) -> None:
    path = _get_user_file()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    extras = {}
    try:
        extras_enc = raw.get("extras_enc")
        if extras_enc:
            key = derive_aes_key(load_session_secret())
            dec = decrypt_text(key, extras_enc)
            if dec:
                extras = json.loads(dec)
    except Exception:
        extras = {}

    _pack_field(extras, "recovery_hashes", json.dumps(hashes, separators=(",",":"), ensure_ascii=False))

    key = _get_master_key()
    raw["extras_enc"] = encrypt_text(key, json.dumps(extras, separators=(",",":"), ensure_ascii=False))
    path.write_text(json.dumps(raw), encoding="utf-8")


def get_api_tokens() -> dict:
    u = load_user()
    if not u:
        return {}
    extras = u.get("extras") or {}
    val = _unpack_field(extras, "api_tokens")
    if val is not None:
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return extras.get("api_tokens") or {}


def set_api_tokens(store: dict) -> None:
    path = _get_user_file()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    extras = {}
    try:
        extras_enc = raw.get("extras_enc")
        if extras_enc:
            key = derive_aes_key(load_session_secret())
            dec = decrypt_text(key, extras_enc)
            if dec:
                extras = json.loads(dec)
    except Exception:
        extras = {}

    _pack_field(extras, "api_tokens", json.dumps(store, separators=(",",":"), ensure_ascii=False))

    key = _get_master_key()
    raw["extras_enc"] = encrypt_text(key, json.dumps(extras, separators=(",",":"), ensure_ascii=False))
    path.write_text(json.dumps(raw), encoding="utf-8")


def verify_user(username: str, password: str) -> bool:
    u = load_user()
    if not u:
        return False
    # If the stored username could not be decrypted, treat as mismatch.
    stored_username = u.get("username")
    if stored_username is None or stored_username != username:
        return False
    return verify_password(u.get("password_hash", ""), password)


def encrypt_bytes(aes_key: bytes, plaintext: bytes) -> str:
    """Encrypt bytes with AES-GCM and return base64 payload (nonce + ciphertext + tag)."""
    aes = AESGCM(aes_key)
    # 12-byte nonce
    from secrets import token_bytes

    nonce = token_bytes(12)
    ct = aes.encrypt(nonce, plaintext, None)
    payload = nonce + ct
    return base64.b64encode(payload).decode("utf-8")


def decrypt_bytes(aes_key: bytes, payload_b64: str) -> Optional[bytes]:
    try:
        aes = AESGCM(aes_key)
        payload = base64.b64decode(payload_b64)
        nonce = payload[:12]
        ct = payload[12:]
        return aes.decrypt(nonce, ct, None)
    except Exception:
        return None


def encrypt_text(aes_key: bytes, text: str) -> str:
    return encrypt_bytes(aes_key, text.encode("utf-8"))


def decrypt_text(aes_key: bytes, payload_b64: str) -> Optional[str]:
    b = decrypt_bytes(aes_key, payload_b64)
    if b is None:
        return None
    try:
        return b.decode("utf-8")
    except Exception:
        return None
