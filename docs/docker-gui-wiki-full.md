# Upload Assistant — WebUI: Docker & Unraid Setup

This guide explains how to run the Upload Assistant WebUI inside Docker (including Unraid). It focuses only on container-specific setup for the WebUI: environment variables, persistent mounts (config, sessions, tmp), session secrets, permissions, and minimal security guidance.

--

## Quick summary

- Persist the WebUI configuration and session data by mounting a host `data` folder into `/Upload-Assistant/data` inside the container, or mount a directory to the container XDG config location.
- Provide a stable session secret via `SESSION_SECRET` or `SESSION_SECRET_FILE` so encrypted credentials remain decryptable after restarts.
- Ensure `UA_BROWSE_ROOTS` lists the container-side mount paths the WebUI may browse (must match your `volumes` mounts).

--

## Recommended environment variables (WebUI)

- `UA_BROWSE_ROOTS` — comma-separated list of allowed container-side browse roots (required). Example: `/data,/Upload-Assistant/tmp`.
- `SESSION_SECRET` or `SESSION_SECRET_FILE` — stable session secret. Example: `SESSION_SECRET_FILE=/Upload-Assistant/data/session_secret`. Must have permissions sets correctly. Don't use this unless by default.
- `IN_DOCKER=1` — force container detection if necessary (the app auto-detects Docker in most cases).
- `UA_WEBUI_CORS_ORIGINS` — optional CORS origins, comma-separated.

Note: When running inside a container the WebUI prefers the per-user XDG/AppData config directory for storing `session_secret` and `webui_auth.json` (it respects `XDG_CONFIG_HOME` on Unix-like systems or `APPDATA` on Windows). By default that will be `/root/.config/upload-assistant` inside the container. If you prefer the repository `data/` path, set `SESSION_SECRET_FILE` to a path you mount into the container (for example `/Upload-Assistant/data/session_secret`).

- The `session_secret` if specified, should be a 64 byte string.

--

## Recommended volume mounts

Mount a host directory for the app `data` (this stores `webui_auth.json`, `session_secret`, and other persisted state):

- `/host/path/Upload-Assistant/data:/Upload-Assistant/data:rw`

Optional mounts (recommended for persistence and predictable behavior):

- `/host/path/Upload-Assistant/data/sessions:/Upload-Assistant/data/sessions:rw` — persist session files when CacheLib unavailable.
- `/host/path/Upload-Assistant/tmp:/Upload-Assistant/tmp:rw` — temp files used by the app; ensure permissions allow container to create/touch files.
- Map your download directories so the WebUI can browse them, e.g. `/host/torrents:/data/torrents:rw` and include `/data/torrents` in `UA_BROWSE_ROOTS`.

Note: container-side paths are important — `UA_BROWSE_ROOTS` must reference the container-side mount points.

--

## Docker Compose snippet (recommended)

Include the following in your `docker-compose.yml` as a starting point (adjust host paths and network):

```yaml
services:
  upload-assistant:
    image: ghcr.io/audionut/upload-assistant:latest
    container_name: upload-assistant
    restart: unless-stopped
    environment:
      # - SESSION_SECRET_FILE=/Upload-Assistant/data/session_secret
      - IN_DOCKER=1
      # - UA_BROWSE_ROOTS=/data/torrents,/Upload-Assistant/tmp
    ports:
      # Map host port to container port (change for host-only binding if desired)
      - "5000:5000"
    volumes:
      - /path/to/torrents/:/data/torrents/:rw #map this to qbit download location, map exactly as qbittorent template on both sides.
      - /mnt/user/appdata/Upload-Assistant/data/config.py:/Upload-Assistant/data/config.py:rw # Optional: will be created automatically if missing
      - /mnt/user/appdata/qBittorrent/data/BT_backup/:/torrent_storage_dir:rw #map this to your qbittorrent bt_backup
      - /mnt/user/appdata/Upload-Assistant/tmp/:/Upload-Assistant/tmp:rw #map this to your /tmp folder.
      - /mnt/user/appdata/Upload-Assistant/webui-auth:/root/.config/upload-assistant:rw # persist web UI session auth config
    networks:
      - appnet

networks:
  appnet:
    driver: bridge
```

Notes:
- If you want host-only binding on a Linux host, change to `127.0.0.1:5000:5000` in `ports` to restrict access to the host machine.
- For Unraid users who prefer `br0` or a custom network, set `networks` accordingly.

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
    environment:
      - SESSION_SECRET_FILE=/Upload-Assistant/data/session_secret
      - IN_DOCKER=1
      - UA_BROWSE_ROOTS=/data/torrents,/Upload-Assistant/tmp
    ports:
      - "5000:5000"
    volumes:
      - /mnt/user/appdata/Upload-Assistant/data:/Upload-Assistant/data:rw
      - /mnt/user/appdata/Upload-Assistant/tmp:/Upload-Assistant/tmp:rw
      - /mnt/user/Data/torrents:/data/torrents:rw
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
