# Upload Assistant Web UI

This folder contains the optional Web UI for Upload Assistant.

The Web UI is a small Flask app that:
- Serves a browser UI (`/`) for selecting content and running Upload Assistant.
- Exposes a JSON API under `/api/*`.

## Requirements

### Python
- Python 3.9+
- The main Upload Assistant dependencies (see the repo root `requirements.txt`)

Note: `werkzeug` is installed automatically as a dependency of `flask`.

## Quick start (Docker)

1. Use an image that includes the Web UI dependencies (the `-webui` tagged image).
2. Set `ENABLE_WEB_UI=true`.
3. Configure **browse roots** (required): set `UA_BROWSE_ROOTS` to a comma-separated list of directories inside the container that you want the UI to be able to browse and execute against.

Example (compose-style, localhost-only by default):

```yaml
ports:
  # Localhost-only on the Docker host (recommended default).
  # Change to "0.0.0.0:5000:5000" (or "5000:5000") to allow access from other devices.
  # Note: "other devices" typically means LAN, but it can become WAN exposure if you port-forward, enable UPnP,
  # run a reverse proxy, or otherwise expose the host publicly.
  - "127.0.0.1:5000:5000"
environment:
  - ENABLE_WEB_UI=true
  - UA_WEBUI_HOST=0.0.0.0
  - UA_WEBUI_PORT=5000
  - UA_BROWSE_ROOTS=/data/torrents,/Upload-Assistant/tmp
  # Optional but strongly recommended if exposed beyond localhost:
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
- **Docker note**: In containerized environments, use these environment variables instead of the login page to ensure auth settings persist between container restarts.

### `UA_TOKEN`

Set `UA_TOKEN` to an opaque bearer token (raw token string) to provide a static API token to the Web UI in container environments. To apply or change the token, update the container environment and restart the container. When `UA_TOKEN` is set the server treats the token store as read-only at runtime.

### Session-Based Authentication
When `UA_WEBUI_USERNAME` and `UA_WEBUI_PASSWORD` are not set, the Web UI uses session-based authentication with a login page.

- On first access, any username/password combination is accepted and saved to a config file.
- The config file location is platform-dependent:
  - **Windows**: `%APPDATA%\UploadAssistant\config.toml`
  - **Linux/macOS**: `~/.config/UploadAssistant/config.toml`
- **Docker note**: In containers, this is typically `/root/.config/UploadAssistant/config.toml`. Since containers are ephemeral, consider using environment variables for auth instead, or mount a volume to persist the config file:
  ```yaml
  volumes:
    - /host/path/to/webui-config:/root/.config/UploadAssistant
  ```

### Two-Factor Authentication (2FA)
The Web UI supports optional TOTP (Time-based One-Time Password) 2FA for enhanced security.

#### Environment Variables
- `UA_WEBUI_TOTP_SECRET`: Set a base32-encoded TOTP secret directly via environment variable. When set, this takes priority over other storage methods and will clean up any existing secrets from keyring or Docker secrets.

#### Setup Process
1. Access the Web UI configuration page (gear icon in the top-right).
2. Navigate to the "2FA Setup" section.
3. Scan the QR code with your authenticator app (recommended: password managers like Bitwarden, 1Password, or dedicated apps like Google Authenticator).
4. Enter the 6-digit code to verify setup.
5. Save recovery codes in a secure location - these can be used if you lose access to your authenticator.

#### Storage Priority
Secrets are stored in the following priority order:
1. `UA_WEBUI_TOTP_SECRET` environment variable (highest priority)
2. Docker secrets (`/run/secrets/ua_webui_totp_secret`)
3. OS keyring (non-Docker environments)

When an environment variable is set, any existing secrets in keyring or Docker secrets are automatically cleaned up.

#### Login Process
- Enter your username and password as usual.
- If 2FA is enabled, you'll be prompted for a 6-digit TOTP code or recovery code.
- Recovery codes are single-use and should be stored securely.
- The 2FA input accepts both TOTP codes (6 digits) and recovery codes (16 characters).

#### Password Manager Compatibility
The setup process generates standard TOTP secrets compatible with most password managers. The QR code contains all necessary information for automatic setup in apps like Bitwarden, 1Password, LastPass, etc.

### Keyring Backend Configuration
The Web UI uses the `keyring` library for secure storage of authentication data in non-Docker environments when environment variables for authentication are not set. The library automatically detects and uses the most appropriate secure backend for your platform (such as macOS Keychain, Windows Credential Manager, or Linux keyring services).

If keyring initialization fails, the Web UI will exit with an error, as secure credential storage is required for session-based authentication. Ensure your system has a compatible keyring backend installed or use environment variables.

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
- Docker: access scope is controlled by your published port. Using `ports: "5000:5000"` exposes the UI to other devices (typically LAN); adding a router port-forward / UPnP / reverse proxy can expose it to the internet.
- If you allow access from other devices, set `UA_WEBUI_USERNAME` and `UA_WEBUI_PASSWORD`.
- Keep `UA_BROWSE_ROOTS` as narrow as possible (only the directories you need).

## Troubleshooting

- Browsing returns “Invalid path specified”: ensure `UA_BROWSE_ROOTS` is set and includes the directory you’re trying to access.
- Can’t reach the UI from another machine (Docker): ensure `UA_WEBUI_HOST=0.0.0.0` and your compose `ports` publishes on the host LAN interface (e.g. `0.0.0.0:5000:5000` or `5000:5000`).
