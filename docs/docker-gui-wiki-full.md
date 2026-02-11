# Upload Assistant — WebUI: Docker & Unraid Setup

This guide explains how to run the Upload Assistant WebUI inside Docker (including Unraid). It focuses only on container-specific setup for the WebUI: environment variables, persistent mounts (config, sessions, tmp), session secrets, permissions, and minimal security guidance.

--

## Quick summary

- Persist the WebUI configuration and session data by mounting a host `data` folder into `/Upload-Assistant/data` inside the container, or mount a directory to the container XDG config location.
- Provide a stable session secret via `SESSION_SECRET` or `SESSION_SECRET_FILE` so encrypted credentials remain decryptable after restarts.
- Ensure `UA_BROWSE_ROOTS` lists the container-side mount paths the WebUI may browse (must match your `volumes` mounts).

--

## Recommended environment variables (WebUI)

| Variable | Required | Description |
|----------|----------|-------------|
| `UA_BROWSE_ROOTS` | **Yes** | Comma-separated list of allowed container-side browse roots. Example: `/data/torrents,/Upload-Assistant/tmp`. Must match the container-side paths in your `volumes:` mounts. |
| `SESSION_SECRET` | No | Raw session secret string (minimum 32 bytes). Keeps encrypted WebUI credentials valid across container recreates. |
| `SESSION_SECRET_FILE` | No | Path to a file containing the session secret (minimum 32 bytes, hex-encoded or plain text). Example: `/Upload-Assistant/data/session_secret`. The file must be readable by the container. |
| `IN_DOCKER` | No | Force container detection (`1`, `true`, or `yes`). Auto-detected in most cases via `/.dockerenv` and cgroup inspection. `RUNNING_IN_CONTAINER` is accepted as an alias. |
| `UA_WEBUI_CORS_ORIGINS` | No | Comma-separated CORS origins. Only needed if you serve the UI from a different origin than the API. |
| `XDG_CONFIG_HOME` | No | Override the XDG config directory. Default inside the container is `/root/.config`. The app stores `session_secret` and `webui_auth.json` under `$XDG_CONFIG_HOME/upload-assistant/`. |
| `UA_WEBUI_USE_SUBPROCESS` | No | When set (any non-empty value), forces the WebUI to run upload jobs as subprocesses instead of in-process. |

Notes:
- Provide **either** `SESSION_SECRET` or `SESSION_SECRET_FILE`, not both. If neither is set the app auto-generates a secret on first run and persists it to the config directory.
- When running inside a container the WebUI prefers the per-user XDG config directory for storing `session_secret` and `webui_auth.json`. By default that will be `/root/.config/upload-assistant` inside the container. If you prefer the repository `data/` path, set `SESSION_SECRET_FILE` to a path you mount into the container (for example `/Upload-Assistant/data/session_secret`).

--

## Recommended volume mounts

Mount a host directory for the app `data` (recommended). On the first WebUI start, the app will automatically create a default `config.py` from the built-in example if one is not already present:

- `/host/path/Upload-Assistant/data:/Upload-Assistant/data:rw`

> **Tip:** Mounting the whole `data/` directory is preferred over mounting a single `config.py` file. If you mount a single file and it doesn't exist on the host, Docker silently creates an empty *directory* at the mount point, which breaks the application.

Optional mounts (recommended for persistence and predictable behavior):

- `/host/path/Upload-Assistant/tmp:/Upload-Assistant/tmp:rw` — temp files used by the app; ensure permissions allow container to create/touch files.
- Map your download directories so the WebUI can browse them, e.g. `/host/torrents:/data/torrents:rw` and include `/data/torrents` in `UA_BROWSE_ROOTS`.

Note: container-side paths are important — `UA_BROWSE_ROOTS` must reference the container-side mount points.

--

## Docker Compose snippet (recommended)

Include the following in your `docker-compose.yml` as a starting point (adjust host paths and network).

> **Note:** The image entrypoint is `python /Upload-Assistant/upload.py`. The venv is already on `PATH` — no shell wrapper or `source activate` is needed. Just pass arguments via `command:`.

```yaml
services:
  upload-assistant:
    image: ghcr.io/audionut/upload-assistant:latest
    container_name: upload-assistant
    restart: unless-stopped
    command: ["--webui", "0.0.0.0:5000"]
    environment:
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
      # WebUI start.  You can also mount a single config.py file, but it MUST
      # exist on the host first (Docker creates an empty dir if missing).
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
- When editing the Compose file in Unraid, ensure `UA_BROWSE_ROOTS` is set to container-side paths matching your mounts.
- If running in Unraid's `br0` network, use that in the compose `networks` section to allow LAN access.

Example Unraid-specific compose snippet:

```yaml
services:
  upload-assistant:
    image: ghcr.io/audionut/upload-assistant:latest
    container_name: upload-assistant
    restart: unless-stopped
    user: "99:100"  # optionally run as Unraid nobody:users
    command: ["--webui", "0.0.0.0:5000"]
    environment:
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

- If you run the container as non-root (recommended), ensure mounted directories are owned by the container's UID:GID or readable/writable by it. Example commands on host:

```bash
# For standard systems (UID 1000)
sudo chown -R 1000:1000 /host/path/Upload-Assistant/data
sudo chown -R 1000:1000 /host/path/Upload-Assistant/tmp
sudo chmod 700 /host/path/Upload-Assistant/tmp

# For Unraid (UID 99:100)
chown -R 99:100 /mnt/user/appdata/Upload-Assistant
chmod 700 /mnt/user/appdata/Upload-Assistant/tmp
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
- The WebUI will use `UA_BROWSE_ROOTS` (environment) if set; otherwise it will derive browse roots from command-line paths you pass to `upload.py`.
- Use the `--webui=HOST:PORT` form when you want the WebUI to run exclusively (the process will not continue with uploads).

--

## Troubleshooting

- "Browse roots not configured": ensure `UA_BROWSE_ROOTS` is defined and includes container-side mount paths.
- Session/auth lost after restart: make sure `SESSION_SECRET` or `SESSION_SECRET_FILE` is persistent and mounted inside the container.
- Permission errors: check UID/GID ownership of mounted directories and adjust with `chown` and `chmod` as above.

--

## Security notes

- If exposing the WebUI to your LAN/WAN, run behind a reverse proxy with TLS is recommended.
- Limit `UA_BROWSE_ROOTS` to only the directories the WebUI requires to operate.
