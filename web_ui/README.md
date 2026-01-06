# Upload Assistant Web UI

This folder contains the optional Web UI for Upload Assistant.

The Web UI is a small Flask app that:
- Serves a browser UI (`/`) for selecting content and running Upload Assistant.
- Exposes a JSON API under `/api/*`.

## Requirements

### Python
- Python 3.9+
- The main Upload Assistant dependencies (see the repo root `requirements.txt`)
- Web UI Python dependencies:
  - `flask`
  - `flask-cors`

Note: `werkzeug` is installed automatically as a dependency of `flask`.

### Docker image
If you use the `-webui` Docker image / Dockerfile that installs Flask, you do **not** need to install extra Python packages manually.

## Quick start (Docker)

1. Use an image that includes the Web UI dependencies (the `-webui` tagged image, or build from the Web UI Dockerfile).
2. Set `ENABLE_WEB_UI=true`.
3. Configure **browse roots** (required): set `UA_BROWSE_ROOTS` to a comma-separated list of directories inside the container that you want the UI to be able to browse and execute against.

Example (compose-style env vars):

```yaml
environment:
  - ENABLE_WEB_UI=true
  - UA_WEBUI_HOST=0.0.0.0
  - UA_WEBUI_PORT=5000
  - UA_BROWSE_ROOTS=/data/torrents,/Upload-Assistant/tmp
  # Optional but strongly recommended if exposed beyond localhost/LAN:
  # - UA_WEBUI_USERNAME=admin
  # - UA_WEBUI_PASSWORD=change-me
  # Optional: only needed if you serve the UI from a different origin/domain.
  # - UA_WEBUI_CORS_ORIGINS=https://your-ui-host
```

Make sure your volume mounts align with `UA_BROWSE_ROOTS`.
For example, if you mount your torrent directory as `/data/torrents`, include `/data/torrents` in `UA_BROWSE_ROOTS`.

## Quick start (local / bare metal)

From the repo root:

```bash
python -m pip install -r requirements.txt
python -m pip install flask flask-cors
python web_ui/server.py
```

Then open the URL printed at startup (by default: `http://127.0.0.1:5000`).

To enable browsing/execution you must also set `UA_BROWSE_ROOTS` (see below).

## Configuration (environment variables)

### `UA_BROWSE_ROOTS` (required)
Comma-separated list of directories that the Web UI is allowed to browse and use for execution.

- If unset/empty, the Web UI will **deny browsing/execution** (fails closed).
- Each entry is trimmed and converted to an absolute path.
- Requests are restricted to paths under one of these roots (including symlink-escape protection).

Examples:

Linux:
```bash
export UA_BROWSE_ROOTS=/data/torrents,/mnt/media
```

Windows (PowerShell):
```powershell
$env:UA_BROWSE_ROOTS = "D:\torrents,D:\media"
```

### `UA_WEBUI_HOST` / `UA_WEBUI_PORT`
Controls where the server listens.

- `UA_WEBUI_HOST` default: `127.0.0.1` (localhost only)
- `UA_WEBUI_PORT` default: `5000`

### `UA_WEBUI_USERNAME` / `UA_WEBUI_PASSWORD`
Enables HTTP Basic Auth.

- If either variable is set, **both** must be set or authentication will fail.
- When configured, auth is applied to **all** routes (including `/` and static files), except `/api/health`.

### `UA_WEBUI_CORS_ORIGINS`
Optional comma-separated allowlist of origins for `/api/*` routes.

- If unset/empty, CORS is not configured.
- Example: `UA_WEBUI_CORS_ORIGINS=https://your-ui-host,https://another-host`

## API endpoints (high level)

- `GET /api/health` — health check.
- `GET /api/browse?path=...` — list directory contents under `UA_BROWSE_ROOTS`.
- `POST /api/execute` — runs `upload.py` against a validated path and streams output (Server-Sent Events).
- `POST /api/input` — sends input to a running session.
- `POST /api/kill` — terminates a running session.

## Security notes

- Do not expose the Web UI to the public internet.
- If binding to `0.0.0.0` (LAN/remote access), set `UA_WEBUI_USERNAME` and `UA_WEBUI_PASSWORD`.
- Keep `UA_BROWSE_ROOTS` as narrow as possible (only the directories you need).

## Troubleshooting

- Browsing returns “Invalid path specified”: ensure `UA_BROWSE_ROOTS` is set and includes the directory you’re trying to access.
- Can’t reach the UI from another machine: set `UA_WEBUI_HOST=0.0.0.0` and publish/map the port.
