# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
import json

SENSITIVE_KEYS = {
    "token", "passkey", "password", "auth", "cookie", "csrf", "email", "username", "user", "key", "info_hash", "AntiCsrfToken", "torrent_pass"
}


def redact_value(val):
    """Redact sensitive values, including passkeys in URLs."""
    if isinstance(val, str):
        # Redact passkeys in announce URLs (e.g. /<passkey>/announce)
        val = re.sub(r'(?<=/)[a-zA-Z0-9]{10,}(?=/announce)', '[REDACTED]', val)
        # Redact content between /proxy/ and /api (e.g. /proxy/<secret>/api)
        val = re.sub(r'(?<=/proxy/)[^/]+(?=/api)', '[REDACTED]', val)
        # Redact query params like ?passkey=... or &token=...
        val = re.sub(r'([?&](passkey|key|token|auth|info_hash|torrent_pass)=)[^&]+', r'\1[REDACTED]', val, flags=re.I)
        # Redact long hex or base64-like strings (common for tokens)
        val = re.sub(r'\b[a-fA-F0-9]{32,}\b', '[REDACTED]', val)
    return val


def redact_private_info(data, sensitive_keys=SENSITIVE_KEYS):
    """Recursively redact sensitive info in dicts/lists."""
    if isinstance(data, dict):
        return {
            k: (
                "[REDACTED]" if any(s in k.lower() for s in sensitive_keys)
                else redact_private_info(v, sensitive_keys)
            )
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [redact_private_info(item, sensitive_keys) for item in data]
    elif isinstance(data, str):
        return redact_value(data)
    else:
        return data


async def clean_meta_for_export(meta):
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

    with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
        json.dump(meta, f, indent=4)

    return meta
