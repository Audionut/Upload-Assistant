# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false
import ast
import contextlib
import hashlib
import hmac
import json
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
import traceback
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict, Union, cast

import keyring
import pyotp
from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for  # pyright: ignore[reportMissingImports]
from flask_cors import CORS  # pyright: ignore[reportMissingModuleSource]
from werkzeug.security import safe_join  # pyright: ignore[reportMissingImports]

sys.path.insert(0, str(Path(__file__).parent.parent))

# Helper to convert ANSI -> HTML using Rich (optional)
try:
    from src.console import ansi_to_html
except Exception:
    ansi_to_html = None

from src.console import console

Flask = cast(Any, Flask)
Response = cast(Any, Response)
jsonify = cast(Any, jsonify)
render_template = cast(Any, render_template)
request = cast(Any, request)
CORS_fn = cast(Any, CORS)
safe_join = cast(Any, safe_join)

app: Any = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Supported video file extensions for WebUI file browser
SUPPORTED_VIDEO_EXTS = {'.mkv', '.mp4', '.ts'}

# Lock to prevent concurrent in-process uploads (avoids cross-session interference)
inproc_lock = threading.Lock()

# Runtime browse roots (set by upload.py when starting web UI)
_runtime_browse_roots: Optional[str] = None

# Runtime flags and stored auth/totp
saved_auth: Optional[tuple[str, str]] = None
saved_totp_secret: Optional[str] = None

# Detect docker mode (allow operator to set DOCKER_CONTAINER env explicitly)
DOCKER_MODE = bool(os.environ.get("DOCKER_CONTAINER") or os.path.exists("/.dockerenv"))


def _read_docker_secret_file(*names: str) -> Optional[str]:
    """Return the first secret file content found for any of the provided names.
    Docker secrets are usually mounted at /run/secrets/<name>.
    """
    base = "/run/secrets"
    for name in names:
        path = os.path.join(base, name)
        try:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return f.read().strip()
        except Exception:
            continue
    return None


# Load credentials: prefer Docker secrets when running in Docker; otherwise use OS keyring
if DOCKER_MODE:
    # Try separate username/password secrets first, then combined auth secret
    docker_user = _read_docker_secret_file("UA_WEBUI_USERNAME", "ua_webui_username")
    docker_pass = _read_docker_secret_file("UA_WEBUI_PASSWORD", "ua_webui_password")
    if docker_user and docker_pass:
        saved_auth = (docker_user, docker_pass)
    else:
        combined = _read_docker_secret_file("upload-assistant-auth", "upload_assistant_auth", "ua_webui_auth")
        if combined and ":" in combined:
            u, p = combined.split(":", 1)
            saved_auth = (u, p)

    # TOTP secret via Docker secret
    docker_totp = _read_docker_secret_file("UA_TOTP_SECRET", "ua_totp_secret", "upload-assistant-totp")
    if docker_totp:
        saved_totp_secret = docker_totp
else:
    # Try keyring for persisted credentials when not in Docker
    # Read persisted credentials from keyring. Historically we stored credentials
    # as a simple "username:password" string which fails when the username
    # itself contains a colon. Switch to a JSON encoding to make the round-trip
    # safe. Keep backwards-compatibility by attempting to parse JSON first,
    # then falling back to the legacy colon-separated format.
    with contextlib.suppress(Exception):
        auth_data = keyring.get_password("upload-assistant", "auth")
        if auth_data:
            try:
                parsed = json.loads(auth_data)
                if isinstance(parsed, dict) and "username" in parsed and "password" in parsed:
                    saved_auth = (parsed["username"], parsed["password"])
                else:
                    # Not the expected JSON shape; fall back to legacy parsing below
                    raise ValueError("unexpected json shape")
            except Exception:
                # Legacy format: username:password (note this may mis-handle
                # usernames that contain ':' — new code saves JSON to avoid
                # that limitation)
                if ":" in auth_data:
                    u, p = auth_data.split(":", 1)
                    saved_auth = (u, p)

        totp_secret = keyring.get_password("upload-assistant", "totp_secret")
        if totp_secret:
            saved_totp_secret = totp_secret


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _generate_recovery_codes(n: int = 10, length: int = 10) -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Crockford-like, avoid ambiguous chars
    return ["".join(secrets.choice(alphabet) for _ in range(length)) for _ in range(n)]


def _load_recovery_hashes() -> list[str]:
    # Prefer Docker secret file if in Docker
    if DOCKER_MODE:
        raw = _read_docker_secret_file("UA_2FA_RECOVERY", "ua_2fa_recovery", "upload-assistant-2fa-recovery")
        if not raw:
            return []
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        # If lines look like hex hashes, return as-is; otherwise hash them
        if all(re.fullmatch(r"[0-9a-fA-F]{64}", ln) for ln in lines):
            return [ln.lower() for ln in lines]
        return [_hash_code(ln) for ln in lines]

    # Non-docker: load from keyring
    with contextlib.suppress(Exception):
        raw = keyring.get_password("upload-assistant", "2fa_recovery")
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    return [str(x) for x in data]
            except Exception:
                # Fallback: treat as single-line code
                return [_hash_code(raw)]
    return []


def _persist_recovery_hashes(hashes: list[str]) -> None:
    if DOCKER_MODE:
        # Not allowed to persist from inside container
        return
    with contextlib.suppress(Exception):
        keyring.set_password("upload-assistant", "2fa_recovery", json.dumps(hashes))


def _consume_recovery_code(code: str) -> bool:
    """Return True if code matches an unused recovery code and mark it used (persist)."""
    if not code:
        return False
    if DOCKER_MODE:
        # Cannot reliably consume codes in Docker mode (secrets immutable)
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
    CORS_fn(app, resources={r"/api/*": {"origins": cors_origins}}, allow_headers=["Content-Type", "Authorization"])

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


class BrowseItem(TypedDict):
    """Serialized representation of an entry returned by the browse API."""

    name: str
    path: str
    type: Literal["folder", "file"]
    children: Union[list["BrowseItem"], None]


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
    return bool(saved_auth) or bool(os.environ.get("UA_WEBUI_USERNAME")) or bool(os.environ.get("UA_WEBUI_PASSWORD"))


def _webui_auth_ok() -> bool:
    expected_username = os.environ.get("UA_WEBUI_USERNAME") or (saved_auth[0] if saved_auth else "")
    expected_password = os.environ.get("UA_WEBUI_PASSWORD") or (saved_auth[1] if saved_auth else "")

    auth = request.authorization
    if not auth or auth.type != "basic":
        return False

    has_expected_username = bool(expected_username)
    has_expected_password = bool(expected_password)

    # If auth is configured (env or saved), require exact match.
    if has_expected_username or has_expected_password:
        # Constant-time compare to avoid leaking timing info.
        if has_expected_username and not hmac.compare_digest(auth.username or "", expected_username):
            return False
        if has_expected_password and not hmac.compare_digest(auth.password or "", expected_password):
            return False
        # For any unset value, still require a non-empty value to avoid blank auth.
        if not has_expected_username and not (auth.username or ""):
            return False
        return has_expected_password or bool(auth.password or "")

    # If auth is not configured, still require non-empty basic auth.
    return bool(auth.username) and bool(auth.password)


@app.before_request
def _require_auth_for_webui():  # pyright: ignore[reportUnusedFunction]
    # Health endpoint can be used for orchestration checks.
    if request.path == "/api/health":
        return None

    if request.path.startswith("/api/"):
        # For API, allow basic auth
        if _webui_auth_ok():
            return None
        # Or session auth
        if session.get("authenticated"):
            return None
        # If request accepts HTML (browser), redirect to login; else 401 for API clients
        if "text/html" in request.headers.get("Accept", ""):
            return redirect(url_for("login_page"))
        return jsonify({"error": "Authentication required", "success": False}), 401

    # For web routes
    if session.get("authenticated"):
        return None
    if _webui_auth_configured() and _webui_auth_ok():
        return None
    if request.path == "/config" or request.path in ("/", "/index.html"):
        return redirect(url_for("login_page"))

    return None


def _totp_enabled() -> bool:
    """Check if TOTP 2FA is enabled"""
    return saved_totp_secret is not None


def _verify_totp_code(code: str) -> bool:
    """Verify a TOTP code against the stored secret"""
    if not saved_totp_secret:
        return False
    totp = pyotp.TOTP(saved_totp_secret)
    return totp.verify(code)


def _generate_totp_secret() -> str:
    """Generate a new TOTP secret"""
    return pyotp.random_base32()


def _get_totp_uri(username: str, secret: str) -> str:
    """Generate TOTP URI for QR code"""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name="Upload Assistant")


def _validate_upload_assistant_args(tokens: Sequence[Any]) -> list[str]:
    # These are passed to upload.py (not the Python interpreter) and are executed
    # with shell=False. Still validate to avoid control characters and abuse.
    safe: list[str] = []
    for tok in tokens:
        if not isinstance(tok, str):
            raise TypeError("Invalid argument")
        if not tok or len(tok) > 1024:
            raise ValueError("Invalid argument")
        if "\x00" in tok or "\n" in tok or "\r" in tok:
            raise ValueError("Invalid characters in argument")
        safe.append(tok)
    return safe


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
        user = (
            session.get("username")
            or (request.authorization.username if request.authorization else None)
            or os.environ.get("UA_WEBUI_USERNAME")
            or request.remote_addr
        )
        audit = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user,
            "remote_addr": request.remote_addr,
            "action": action,
            "path": path,
            "old_value": _json_safe(old_value),
            "new_value": _json_safe(new_value),
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
    # Use werkzeug.utils.safe_join as the initial join/sanitizer, then also
    # enforce a realpath+commonpath constraint to prevent symlink escapes.
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

                if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
                    continue

                # Handle the case where the path equals the root exactly.
                # safe_join may return None for '.' in some Werkzeug versions.
                if rel == ".":
                    matched_root = check_root
                    candidate_norm = os.path.normpath(check_root)
                    break

                joined = safe_join(check_root, rel)
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
            joined = safe_join(matched_root, expanded)
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

    if require_exists and not os.path.exists(candidate):
        raise ValueError("Path does not exist")

    if require_dir and not os.path.isdir(candidate):
        raise ValueError("Not a directory")

    return candidate


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
def login_page():
    global saved_auth
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        totp_code = request.form.get("totp_code", "").strip()
        remember = request.form.get("remember") == "1"

        if _webui_auth_configured():
            # Validate against env vars or saved_auth
            expected_username = os.environ.get("UA_WEBUI_USERNAME") or (saved_auth[0] if saved_auth else "")
            expected_password = os.environ.get("UA_WEBUI_PASSWORD") or (saved_auth[1] if saved_auth else "")
            if username == expected_username and password == expected_password:
                # Check 2FA if enabled
                if _totp_enabled():
                    totp_ok = bool(totp_code and _verify_totp_code(totp_code))
                    if not totp_ok:
                        # Try one-time recovery codes (consumes code when used)
                        if totp_code and _consume_recovery_code(totp_code):
                            console.print(f"Recovery code used for user {username}", markup=False)
                        else:
                            return render_template("login.html", error="Invalid 2FA code or recovery code", show_2fa=True)

                session["authenticated"] = True
                if remember:
                    session.permanent = True
                return redirect(url_for("config_page"))
            else:
                return render_template("login.html", error="Invalid credentials")
        else:
            # No env, accept any non-empty
            if username and password:
                # Check 2FA if enabled
                if _totp_enabled():
                    totp_ok = bool(totp_code and _verify_totp_code(totp_code))
                    if not totp_ok:
                        # Try one-time recovery codes (consumes code when used)
                        if totp_code and _consume_recovery_code(totp_code):
                            console.print(f"Recovery code used for user {username}", markup=False)
                        else:
                            return render_template("login.html", error="Invalid 2FA code or recovery code", show_2fa=True)

                session["authenticated"] = True
                if remember:
                    session.permanent = True
                # Save auth to keyring (only when not running in Docker).
                # Store as JSON to avoid ambiguities with ':' in usernames.
                if not DOCKER_MODE:
                    with contextlib.suppress(Exception):
                        keyring.set_password("upload-assistant", "auth", json.dumps({"username": username, "password": password}))
                    # Update saved_auth
                    saved_auth = (username, password)
                else:
                    # In Docker, persistent secrets must be provided via Docker secrets
                    console.print("Running in Docker: skipping persistent save of credentials. Provide credentials via Docker secrets.", markup=False)
                return redirect(url_for("config_page"))
            else:
                return render_template("login.html", error="Invalid credentials")

    # Show 2FA field if enabled
    show_2fa = _totp_enabled()
    return render_template("login.html", show_2fa=show_2fa)


@app.route("/logout")
def logout():
    session.pop("authenticated", None)
    return redirect(url_for("login_page"))


@app.route("/config")
def config_page():
    """Serve the config UI"""
    try:
        return render_template("config.html")
    except Exception as e:
        console.print(f"Error loading config template: {e}", markup=False)
        console.print(traceback.format_exc(), markup=False)
        return "<pre>Internal server error</pre>", 500


@app.route("/api/health")
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "success": True, "message": "Upload Assistant Web UI is running"})


@app.route("/api/2fa/status")
def twofa_status():
    """Check 2FA status"""
    return jsonify({"enabled": _totp_enabled(), "success": True})


@app.route("/api/2fa/setup", methods=["POST"])
def twofa_setup():
    """Setup 2FA - generate secret and return QR code URI"""
    if _totp_enabled():
        return jsonify({"error": "2FA already enabled", "success": False}), 400

    # Get username for QR code
    username = os.environ.get("UA_WEBUI_USERNAME") or (saved_auth[0] if saved_auth else "user")

    secret = _generate_totp_secret()
    uri = _get_totp_uri(username, secret)
    # Generate one-time recovery codes and store temporarily in session
    recovery_codes = _generate_recovery_codes()
    session["temp_totp_secret"] = secret
    session["temp_recovery_codes"] = recovery_codes

    return jsonify({"secret": secret, "uri": uri, "recovery_codes": recovery_codes, "success": True})


@app.route("/api/2fa/enable", methods=["POST"])
def twofa_enable():
    """Enable 2FA after verification"""
    data = request.json or {}
    code = data.get("code", "").strip()

    if not code:
        return jsonify({"error": "Code required", "success": False}), 400

    temp_secret = session.get("temp_totp_secret")
    if not temp_secret:
        return jsonify({"error": "No setup in progress", "success": False}), 400

    # Verify the code with the temporary secret
    totp = pyotp.TOTP(temp_secret)
    if not totp.verify(code):
        return jsonify({"error": "Invalid code", "success": False}), 400

    # Save the secret permanently (only when not running in Docker)
    if DOCKER_MODE:
        return jsonify({"error": "Cannot persist 2FA secret when running in Docker. Provide the TOTP secret via Docker secrets (e.g. /run/secrets/UA_TOTP_SECRET).", "success": False}), 400

    with contextlib.suppress(Exception):
        keyring.set_password("upload-assistant", "totp_secret", temp_secret)

    # Persist recovery codes (hashes) if provided
    temp_codes = session.get("temp_recovery_codes") or []
    hashes = [_hash_code(c) for c in temp_codes]
    _persist_recovery_hashes(hashes)

    # Update global variable
    global saved_totp_secret
    saved_totp_secret = temp_secret

    # Clear temp session
    session.pop("temp_totp_secret", None)
    session.pop("temp_recovery_codes", None)

    return jsonify({"success": True, "recovery_codes": temp_codes})


@app.route("/api/2fa/disable", methods=["POST"])
def twofa_disable():
    """Disable 2FA"""
    if not _totp_enabled():
        return jsonify({"error": "2FA not enabled", "success": False}), 400

    # Remove from keyring (only when not running in Docker)
    if DOCKER_MODE:
        return jsonify({"error": "Cannot remove TOTP secret when running in Docker. Remove the secret from your Docker secrets on the host.", "success": False}), 400

    with contextlib.suppress(Exception):
        keyring.delete_password("upload-assistant", "totp_secret")
        # Also remove recovery hashes
        with contextlib.suppress(Exception):
            keyring.delete_password("upload-assistant", "2fa_recovery")

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

    items: list[BrowseItem] = []
    for root in roots:
        display_name = os.path.basename(root.rstrip(os.sep)) or root
        items.append({"name": display_name, "path": root, "type": "folder", "children": []})

    return jsonify({"items": items, "success": True})


@app.route("/api/config_options")
def config_options():
    """Return config options based on example-config.py with overrides from config.py"""
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
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
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
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "value": _json_safe(coerced_value)})


@app.route("/api/config_remove_subsection", methods=["POST"])
def config_remove_subsection():
    """Remove a subsection (top-level key) from the user's config.py if present"""
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
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/browse")
def browse_path():
    """Browse filesystem paths"""
    requested = request.args.get("path", "")
    try:
        path = _resolve_browse_path(requested)
    except ValueError as e:
        # Log details server-side, but avoid leaking paths/internal details to clients.
        console.print(f"Path resolution error for requested {requested!r}: {e}", markup=False)
        return jsonify({"error": "Invalid path specified", "success": False}), 400

    console.print(f"Browsing path: {path}", markup=False)

    try:
        items: list[BrowseItem] = []
        try:
            for item in sorted(os.listdir(path)):
                # Skip hidden files
                if item.startswith("."):
                    continue

                full_path = os.path.join(path, item)
                try:
                    is_dir = os.path.isdir(full_path)

                    # Skip files that are not supported video formats
                    if not is_dir:
                        _, ext = os.path.splitext(item.lower())
                        if ext not in SUPPORTED_VIDEO_EXTS:
                            continue

                    items.append({"name": item, "path": full_path, "type": "folder" if is_dir else "file", "children": [] if is_dir else None})
                except (PermissionError, OSError):
                    continue

            console.print(f"Found {len(items)} items in {path}", markup=False)

        except PermissionError:
            console.print(f"Error: Permission denied: {path}", markup=False)
            return jsonify({"error": "Permission denied", "success": False}), 403

        return jsonify({"items": items, "success": True, "path": path, "count": len(items)})

    except Exception as e:
        console.print(f"Error browsing {path}: {e}", markup=False)
        console.print(traceback.format_exc(), markup=False)
        return jsonify({"error": "Error browsing path", "success": False}), 500


@app.route("/api/execute", methods=["POST", "OPTIONS"])
def execute_command():
    """Execute upload.py with interactive terminal support"""

    if request.method == "OPTIONS":
        return "", 204

    try:
        data = request.json
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

                base_dir = Path(__file__).parent.parent
                upload_script = str(base_dir / "upload.py")
                command = [sys.executable, "-u", upload_script, validated_path]

                # Add arguments if provided
                if args:
                    import shlex

                    parsed_args = shlex.split(args)
                    command.extend(_validate_upload_assistant_args(parsed_args))

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

                        def wrapped_ask_yes_no(question: str, default: bool = False) -> bool:
                            with contextlib.suppress(Exception):
                                wrapped_print(question)
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
                                return default

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
def send_input():
    """Send user input to running process"""
    try:
        data = request.json
        session_id = data.get("session_id", "default")
        user_input = data.get("input", "")

        # Received input for session (logged at debug level previously) - keep minimal output

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
def kill_process():
    """Kill a running process"""
    try:
        data = request.json
        session_id = data.get("session_id")

        console.print(f"Kill request for session {session_id}", markup=False)

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
