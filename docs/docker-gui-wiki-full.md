# Upload Assistant — WebUI: Docker & Unraid Setup

This guide explains how to run the Upload Assistant WebUI inside Docker (including Unraid). It focuses only on container-specific setup for the WebUI: environment variables, persistent mounts (config, sessions, tmp), session secrets, permissions, and minimal security guidance.

--

## Quick summary

- Persist the WebUI configuration and session data by mounting a host `data` folder into `/Upload-Assistant/data` inside the container, or mount a directory to the container XDG config location.
- Provide a stable session secret via `SESSION_SECRET` or `SESSION_SECRET_FILE` so encrypted credentials remain decryptable after restarts.
- Set `UA_BROWSE_ROOTS` — **required** when running in Docker. The Docker command typically uses `--webui` only (no paths), so without this the app would use a dummy path and the file browser would not work. When running as a script, you can instead pass paths on the command line (e.g. `python upload.py /path/to/folder --webui 127.0.0.1:5000`).

--

## Recommended environment variables (WebUI)

| Variable | Required | Description |
|----------|----------|-------------|
| `PUID` | No | UID to run the app as (e.g. `1000`). The entrypoint starts as root, fixes directory ownership, then drops to this UID. If omitted the app runs as root. |
| `PGID` | No | GID to run the app as (e.g. `1000`). Used together with `PUID`. |
| `UA_BROWSE_ROOTS` | **Yes** (Docker) | Comma-separated list of allowed container-side browse roots. **Required in Docker** because the command uses `--webui` only (no paths); without it the app would use a dummy path and the file browser would not work. When running as a script, you can instead pass paths on the command line. Use the **right side** (container path) of each `volumes:` entry (`host:container`). Enables granular access: mount a volume but only expose selected paths to the WebUI (e.g. omit `/torrent_storage_dir`). |
| `SESSION_SECRET` | No | Raw session secret string (minimum 32 bytes). Keeps encrypted WebUI credentials valid across container recreates. |
| `SESSION_SECRET_FILE` | No | Path to a file containing the session secret (minimum 32 bytes, hex-encoded or plain text). Example: `/Upload-Assistant/data/session_secret`. The file must be readable by the container. |
| `IN_DOCKER` | No | Force container detection (`1`, `true`, or `yes`). Auto-detected in most cases via `/.dockerenv` and cgroup inspection. `RUNNING_IN_CONTAINER` is accepted as an alias. |
| `UA_WEBUI_CORS_ORIGINS` | No | Comma-separated CORS origins. Only needed if you serve the UI from a different origin than the API. |
| `XDG_CONFIG_HOME` | No | Override the XDG config directory. Default inside the container is `/root/.config`. The app stores `session_secret` and `webui_auth.json` under `$XDG_CONFIG_HOME/upload-assistant/`. |
| `UA_WEBUI_USE_SUBPROCESS` | No | When set (any non-empty value), forces the WebUI to run upload jobs as subprocesses instead of in-process. |

Notes:
- **PUID/PGID** are the recommended way to run as non-root. Do **not** use Docker's `user:` directive — it starts the process directly as that UID without root access, so the entrypoint cannot fix ownership of freshly-created mount directories.
- Provide **either** `SESSION_SECRET` or `SESSION_SECRET_FILE`, not both. If neither is set the app auto-generates a secret on first run and persists it to the config directory.
- When running inside a container the WebUI prefers the per-user XDG config directory for storing `session_secret` and `webui_auth.json`. By default that will be `/root/.config/upload-assistant` inside the container. If you prefer the repository `data/` path, set `SESSION_SECRET_FILE` to a path you mount into the container (for example `/Upload-Assistant/data/session_secret`).
- **Docker bind-mount pitfall:** If you set `SESSION_SECRET_FILE` and mount a volume to that path, but the host path does not already exist as a **file**, Docker will create it as a **directory**. The app detects this and will auto-generate a `session_secret` file inside that directory. When `PUID`/`PGID` are set, the entrypoint fixes ownership of the `session_secret` directory so the runtime user can write there. The recommended approach for fresh installs is to mount the `webui-auth` volume to the XDG config directory (see below) and let the app manage the secret automatically.

--

## Recommended volume mounts

Mount a host directory for the app `data` (recommended). On the first WebUI start, the app will automatically create a default `config.py` from the built-in example if one is not already present. The directory does **not** need to exist on the host — Docker creates it and the entrypoint fixes ownership automatically:

- `/host/path/Upload-Assistant/data:/Upload-Assistant/data:rw`

> **Tip:** Mounting the whole `data/` directory is preferred over mounting a single `config.py` file. If you mount a single file and it doesn't exist on the host, Docker silently creates an empty *directory* at the mount point, which breaks the application.

Optional mounts (recommended for persistence and predictable behavior):

- `/host/path/Upload-Assistant/tmp:/Upload-Assistant/tmp:rw` — temp files used by the app; ensure permissions allow container to create/touch files.
- Map your download directories so the WebUI can browse them, e.g. `/host/torrents:/data/torrents:rw` and include `/data/torrents` in `UA_BROWSE_ROOTS`.

Note: In `volumes:` the format is `host:container` (left = host, right = container). `UA_BROWSE_ROOTS` must use the **container-side** paths (right side). This allows granular access: you can mount e.g. `/torrent_storage_dir` for the app but omit it from `UA_BROWSE_ROOTS` so the WebUI cannot browse it.

--

## Docker Compose snippet (recommended)

Include the following in your `docker-compose.yml` as a starting point (adjust host paths and network).

> **Note:** The image entrypoint handles directory permissions and drops privileges to the UID/GID specified by `PUID`/`PGID`. No manual `chown` on the host is needed.

```yaml
services:
  upload-assistant:
    image: ghcr.io/audionut/upload-assistant:latest
    container_name: upload-assistant
    restart: unless-stopped
    command: ["--webui", "0.0.0.0:5000"]
    environment:
      - PUID=1000
      - PGID=1000
      - UA_BROWSE_ROOTS=/data/torrents,/Upload-Assistant/tmp
      # - SESSION_SECRET_FILE=/Upload-Assistant/data/session_secret
      # - IN_DOCKER=1
      # - UA_WEBUI_CORS_ORIGINS=https://your-ui-host
      # - XDG_CONFIG_HOME=/custom/config/path
    ports:
      # 127.0.0.1 → accessible only from the host machine (recommended)
      # 0.0.0.0   → accessible from any device on the network
      - "127.0.0.1:5000:5000"
    volumes:
      - /path/to/torrents:/data/torrents:rw
      # Mount the whole data directory — config.py is auto-created on first
      # WebUI start.  The directory doesn't need to exist on the host.
      - /path/to/appdata/Upload-Assistant/data:/Upload-Assistant/data:rw
      - /path/to/qBittorrent/BT_backup:/torrent_storage_dir:rw
      - /path/to/appdata/Upload-Assistant/tmp:/Upload-Assistant/tmp:rw
      - /path/to/appdata/Upload-Assistant/webui-auth:/root/.config/upload-assistant:rw
    stop_grace_period: 15s
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:5000/api/health"]
      interval: 30s
      timeout: 5s
      start_period: 10s
      retries: 3
    networks:
      - yournetwork  # change to the network with your torrent client

networks:
  yournetwork:  # change to your network
    external: true
```

Notes:
- **Mounting the data directory** (recommended): mount the whole `data/` folder. On the first WebUI start, the app automatically creates a default `config.py` from the built-in example. You can then edit it via the WebUI config editor.
- **Mounting a single file**: if you prefer to mount just `config.py`, the file **must exist** on the host first. If the host file is missing, Docker creates an empty *directory* at that path instead of a file, which breaks the application.
- If you want LAN access, change `127.0.0.1:5000:5000` to `0.0.0.0:5000:5000` in `ports` (or simply `"5000:5000"`). Consider running behind a reverse proxy with TLS when exposed.
- For Unraid users who prefer `br0` or a custom network, set `networks` accordingly.
- The network must be `external: true` if it already exists (e.g. shared with your torrent client). Use `driver: bridge` if you want Compose to create a new one.

--

## Unraid (Compose plugin / Stack) notes

- Use the Community Applications Compose plugin or add the container via the Docker templates.
- Set the appdata path to a stable appdata folder, e.g. `/mnt/user/appdata/Upload-Assistant/data` and bind it into `/Upload-Assistant/data` inside the container.
- When editing the Compose file in Unraid, ensure `UA_BROWSE_ROOTS` is set to the container-side paths (right side of `host:container` in `volumes:`) matching your mounts.
- If running in Unraid's `br0` network, use that in the compose `networks` section to allow LAN access.

Example Unraid-specific compose snippet:

```yaml
services:
  upload-assistant:
    image: ghcr.io/audionut/upload-assistant:latest
    container_name: upload-assistant
    restart: unless-stopped
    command: ["--webui", "0.0.0.0:5000"]
    environment:
      - PUID=99
      - PGID=100
      - UA_BROWSE_ROOTS=/data/torrents,/Upload-Assistant/tmp
      - SESSION_SECRET_FILE=/Upload-Assistant/data/session_secret
      # - IN_DOCKER=1
    ports:
      - "5000:5000"
    volumes:
      - /mnt/user/appdata/Upload-Assistant/data:/Upload-Assistant/data:rw
      - /mnt/user/appdata/Upload-Assistant/tmp:/Upload-Assistant/tmp:rw
      - /mnt/user/Data/torrents:/data/torrents:rw
    stop_grace_period: 15s
    networks:
      - br0

networks:
  br0:
    external: true
```

## File ownership & permissions

The entrypoint script automatically fixes ownership of `data/`, `tmp/`, `session_secret` (when `SESSION_SECRET_FILE` points to a directory), and `/root/.config/upload-assistant` (webui-auth mount) at startup when `PUID`/`PGID` are set. No manual `chown` is needed for typical setups.

If you need to adjust permissions manually (e.g. for bind mounts with special requirements):

```bash
# For standard systems (UID 1000)
sudo chown -R 1000:1000 /host/path/Upload-Assistant/data
sudo chown -R 1000:1000 /host/path/Upload-Assistant/tmp

# For Unraid (UID 99:100)
chown -R 99:100 /mnt/user/appdata/Upload-Assistant
```

- The WebUI will try to tighten `webui_auth.json` and `session_secret` permissions to `0600` after writing when the platform supports chmod.

--

## Starting and verifying

1. Start the stack:

```bash
docker compose up -d
```

2. Confirm container is running:

```bash
docker ps | grep upload-assistant
```

3. Check logs for WebUI startup messages and any deprecation warnings:

```bash
docker logs upload-assistant --tail 200
```

4. Visit the WebUI in your browser at `http://[host]:5000` (adjust host/port if you changed the mapping).

To start the WebUI from the project entry inside the container, run the project's CLI with the `--webui` argument. Example (from inside the container):

```bash
# start the WebUI on 0.0.0.0:5000
python upload.py --webui 0.0.0.0:5000
```

The CLI starts the same WebUI the packaged container uses (it runs the server via `waitress`).

Notes:
- The WebUI will use `UA_BROWSE_ROOTS` (environment) if set; otherwise it will derive browse roots from command-line paths you pass to `upload.py`. When running in Docker with `--webui` only and no paths, the app would otherwise use a dummy path — the file browser would not work, so `UA_BROWSE_ROOTS` is required.
- Use the `--webui=HOST:PORT` form when you want the WebUI to run exclusively (the process will not continue with uploads).

--

## Troubleshooting

- "Browse roots not configured" or empty file browser: when running in Docker, set `UA_BROWSE_ROOTS` (required — Docker uses `--webui` only, so no paths are passed). When running as a script, either set `UA_BROWSE_ROOTS` or pass paths on the command line (e.g. `python upload.py /path/to/folder --webui 127.0.0.1:5000`).
- Session/auth lost after restart: make sure `SESSION_SECRET` or `SESSION_SECRET_FILE` is persistent and mounted inside the container.
- Permission errors on mounted directories: ensure `PUID`/`PGID` are set in your environment. If you see permission warnings in the logs, the entrypoint could not fix ownership — check that the container starts as root (do **not** use Docker's `user:` directive).

--

## Security notes

- If exposing the WebUI to your LAN/WAN, run behind a reverse proxy with TLS is recommended.
- Limit `UA_BROWSE_ROOTS` to only the directories the WebUI requires to operate. This gives granular access: you can mount volumes the app needs (e.g. `/torrent_storage_dir`) without exposing them to the file browser.
