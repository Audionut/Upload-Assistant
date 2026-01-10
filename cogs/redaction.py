# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
import json
from typing import Any, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from upload import Meta

SENSITIVE_KEYS: set[str] = {
    "token", "passkey", "password", "auth", "cookie", "csrf", "email", "username", "user", "key", "info_hash", "AntiCsrfToken", "torrent_pass", "Popcron"
}


def extract_json_blocks(text: str):
    """Extract JSON-like blocks from a string using bracket counting.

    Returns a list of (start, end) slices where `text[start:end]` is a candidate JSON
    object (`{...}`) or array (`[...]`). This supports *nested* JSON by tracking a
    bracket stack, and ignores brackets that occur inside quoted strings.

    Notes / limitations:
    - This is a best-effort extractor for embedded JSON substrings.
    - It does not attempt to support non-standard JSON (JSON5, trailing commas, etc.).
    - Blocks are only redacted if `json.loads` successfully parses them.
    """
    blocks: List[Tuple[int, int]] = []
    stack: list[str] = []
    start: Optional[int] = None
    in_string = False
    string_char: str | None = None
    escape = False

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue

        if in_string:
            if ch == "\\":
                escape = True
            elif ch == string_char:
                in_string = False
                string_char = None
            continue

        if ch in ("\"", "'"):
            in_string = True
            string_char = ch
            continue

        if ch in ("{", "["):
            if not stack:
                start = i
            stack.append(ch)
            continue

        if ch in ("}", "]") and stack:
            top = stack[-1]
            if (ch == "}" and top == "{") or (ch == "]" and top == "["):
                stack.pop()
                if not stack and start is not None:
                    blocks.append((start, i + 1))
                    start = None

    return blocks


def redact_value(val):
    """Redact sensitive values, including passkeys in URLs and JSON substrings."""
    if isinstance(val, str):
        # First, try to find and redact embedded JSON substrings within the string.
        # This uses bracket counting (not regex) so it can handle nested JSON.
        blocks = extract_json_blocks(val)
        for start, end in reversed(blocks):
            json_str = val[start:end]
            try:
                parsed = json.loads(json_str)
            except (json.JSONDecodeError, TypeError):
                continue

            try:
                redacted = redact_private_info(parsed)
                redacted_str = json.dumps(redacted)
            except (TypeError, ValueError):
                continue

            val = val[:start] + redacted_str + val[end:]

        # Redact passkeys in announce URLs (e.g. /<passkey>/announce)
        val = re.sub(r'(?<=/)[a-zA-Z0-9]{10,}(?=/announce)', '[REDACTED]', val)
        # Redact content between /proxy/ and /api (e.g. /proxy/<secret>/api)
        val = re.sub(r'(?<=/proxy/)[^/]+(?=/api)', '[REDACTED]', val)
        # Redact query params like ?passkey=... or &token=...
        val = re.sub(r'([?&](passkey|key|token|auth|info_hash|torrent_pass)=)[^&]+', r'\1[REDACTED]', val, flags=re.I)
        # Redact long hex or base64-like strings (common for tokens)
        val = re.sub(r'\b[a-fA-F0-9]{32,}\b', '[REDACTED]', val)
    return val


def redact_private_info(data: Any, sensitive_keys: set[str] = SENSITIVE_KEYS):
    """Recursively redact sensitive info in dicts/lists/strings containing JSON."""
    if isinstance(data, dict):
        return {
            k: (
                "[REDACTED]" if any(s.lower() in k.lower() for s in sensitive_keys)
                else redact_private_info(v, sensitive_keys)
            )
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [redact_private_info(item, sensitive_keys) for item in data]
    elif isinstance(data, str):
        # Try to parse as JSON first
        try:
            parsed_json = json.loads(data)
            redacted_json = redact_private_info(parsed_json, sensitive_keys)
            return json.dumps(redacted_json)
        except (json.JSONDecodeError, TypeError):
            # Not valid JSON, treat as regular string
            return redact_value(data)
    else:
        return data


async def clean_meta_for_export(meta: "Meta") -> "Meta":
    """
    Removes all 'status_message' keys from meta['tracker_status'] and
    removes or clears 'torrent_comments' from meta.
    """
    # tracker status is not in the saved meta file, but adding the catch here
    # in case the meta file is updated in the future
    if 'tracker_status' in meta and isinstance(meta['tracker_status'], dict):
        for tracker in list(meta['tracker_status']):  # list() to avoid RuntimeError if deleting keys
            if 'status_message' in meta['tracker_status'][tracker]:
                del meta['tracker_status'][tracker]['status_message']

    if 'torrent_comments' in meta:
        del meta['torrent_comments']

    if 'matched_episode_ids' in meta:
        del meta['matched_episode_ids']

    with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
        json.dump(meta, f, indent=4)

    return meta
