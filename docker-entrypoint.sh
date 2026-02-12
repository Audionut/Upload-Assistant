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
    # - data, tmp: config, temp files
    # - session_secret: when SESSION_SECRET_FILE points to a path that Docker
    #   created as a directory (host path didn't exist), the app creates a
    #   session_secret file inside it; the runtime user must be able to write
    # - /root/.config/upload-assistant: webui-auth mount; when PUID is set,
    #   the runtime user must traverse /root and write there
    for dir in /Upload-Assistant/data /Upload-Assistant/tmp /Upload-Assistant/session_secret /root/.config/upload-assistant; do
        # If the path already exists as a non-directory (e.g. a file bind-mount),
        # fix its ownership but don't try mkdir -p (which would fail under set -e).
        if [ -e "$dir" ] && [ ! -d "$dir" ]; then
            if [ -n "$TARGET_UID" ]; then
                chown "$TARGET_UID:${TARGET_GID:-$TARGET_UID}" "$dir" 2>/dev/null || true
            fi
            continue
        fi
        mkdir -p "$dir"
        if [ -n "$TARGET_UID" ]; then
            chown "$TARGET_UID:${TARGET_GID:-$TARGET_UID}" "$dir" 2>/dev/null || true
        fi
    done

    # When dropping to non-root, the runtime user must traverse /root to reach
    # /root/.config/upload-assistant (webui-auth mount). Make /root traversable.
    if [ -n "$TARGET_UID" ] && [ "$TARGET_UID" != "0" ]; then
        chmod 711 /root 2>/dev/null || true
    fi

    # Drop privileges if PUID was set
    if [ -n "$TARGET_UID" ] && [ "$TARGET_UID" != "0" ]; then
        # Ensure XDG_CONFIG_HOME is set so the app resolves the config
        # directory reliably after gosu drops privileges.  When the target
        # UID has no /etc/passwd entry (common in containers), Path.home()
        # returns "/" and the mounted /root/.config/upload-assistant would
        # never be found.
        export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-/root/.config}"

        exec gosu "$TARGET_UID:${TARGET_GID:-$TARGET_UID}" python /Upload-Assistant/upload.py "$@"
    fi
fi

# Fallback: run as current user (root, or whatever `user:` specified)
exec python /Upload-Assistant/upload.py "$@"
