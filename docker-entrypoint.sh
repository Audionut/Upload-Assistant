#!/bin/sh
set -e

# ── Docker entrypoint ─────────────────────────────────────────────────
# Handles directory ownership so that fresh volume mounts (created as
# root by Docker) are writable by the runtime user.
#
# Supports two modes:
#   1. PUID/PGID env vars (recommended) — container starts as root,
#      fixes permissions, then drops to the requested UID/GID.
#   2. No PUID/PGID — runs as whatever user Docker started (root or
#      the UID from `user:` in compose / --user on CLI).
# ──────────────────────────────────────────────────────────────────────

TARGET_UID="${PUID:-}"
TARGET_GID="${PGID:-}"

# ── Fix directory ownership (only possible when running as root) ──────
if [ "$(id -u)" = "0" ]; then
    # Directories the app needs write access to
    for dir in /Upload-Assistant/data /Upload-Assistant/tmp; do
        mkdir -p "$dir"
        if [ -n "$TARGET_UID" ]; then
            chown "$TARGET_UID:${TARGET_GID:-$TARGET_UID}" "$dir" 2>/dev/null || true
        fi
    done

    # Drop privileges if PUID was set
    if [ -n "$TARGET_UID" ] && [ "$TARGET_UID" != "0" ]; then
        exec gosu "$TARGET_UID:${TARGET_GID:-$TARGET_UID}" python /Upload-Assistant/upload.py "$@"
    fi
fi

# Fallback: run as current user (root, or whatever `user:` specified)
exec python /Upload-Assistant/upload.py "$@"
