# Upload Assistant Web UI

This document describes the current Web UI interface and configuration for Upload Assistant.

The Web UI is a small HTTP server that exposes a browser-based frontend and a JSON API used by the frontend and integrations. It is not a generic Flask tutorial — the instructions below focus on the calling method, authentication handling, and runtime configuration used by this project.

## How the UI is called

The Web UI exposes a compact JSON API consumed by the frontend. The primary flow is:

- Client requests CSRF token from `GET /api/csrf_token` and includes that token in subsequent state-changing requests.
- The frontend calls `POST /api/execute` with JSON `{ path, args, session_id }` to start an execution. The server responds with a streaming body (chunked SSE-style) the client reads with `response.body.getReader()`.
- While streaming, the frontend may send interactive input with `POST /api/input` and may terminate the run with `POST /api/kill`.

Client-side helper `uaApiFetch` (or the local `apiFetch` fallback) automatically fetches and injects the CSRF token, retries once on 401/403, and accepts an optional `signal` (AbortController) so callers can abort long-running fetches. When integrating, call the API the same way the web UI does: include JSON payloads, send CSRF tokens, and support streaming responses on `/api/execute`.

Example start request (JSON):

POST /api/execute
{
  "path": "/path/to/content",
  "args": "--some-flag",
  "session_id": "session_1600000000000"
}

The server streams events prefixed with `data: ` lines containing JSON objects. The frontend is responsible for parsing lines, rendering HTML fragments, and handling `exit` events.

## Authentication & token handling

The Web UI now uses an encrypted, file-backed auth store under the per-user config directory returned by the application. This unifies behavior across container and non-container deployments.

- Stored files and meaning:
  - `webui_auth.json` — contains the persisted user record with `password_hash` (Argon2) and an encrypted `username_enc` field.
  - `api_tokens` — encrypted JSON payload of issued API tokens (stored under the config dir). Encrypted with an AES key derived from the session secret.
  - `totp_secret` — raw TOTP secret stored under the config dir when 2FA is enabled.
  - `session_key` — persistent HMAC key (hex) used to sign the remember-me cookie.
  - `sessions/` — directory containing server-side session files (when created); sessions are stored as a single encrypted payload in the session store.

- Auth modes supported:
  - Static bearer token: set `UA_TOKEN` (or provide tokens via the token API). Bearer tokens are verified normally.
  - Interactive session-based login and UI-first creation: users create a local account via the UI; passwords are Argon2-hashed and usernames are encrypted before being persisted. A minimum entropy requirement (48 bits) is enforced for user-chosen passwords.

- Remember-me cookie:
  - The remember token is stored in a browser cookie named `ua_remember`. It contains a base64 payload and an HMAC-SHA256 signature keyed with `session_key`. The cookie lifetime is 30 days.
  - To invalidate existing remember tokens, rotate or delete `session_key` from the config directory.

- Encryption & session secret:
  - Encrypted usernames, API token store, and encrypted session payloads are protected with an AES key derived from the session secret. The server looks for the session secret in this order:
    - `QUI__SESSION_SECRET` (env)
    - `QUI__SESSION_SECRET_FILE` (path to a file, first line read)
    - `SECRET_KEY` (compat fallback)
    - otherwise a random ephemeral secret is used (not recommended for persistent deployments)
  - Rotating or losing the session secret will render previously encrypted data (usernames, tokens, sessions) unrecoverable.

Security notes:

- Do not expose the UI to the public internet without a reverse proxy and proper authentication. When exposing beyond localhost, provision a static bearer token (`UA_TOKEN`) or create a local UI account and enable TOTP where appropriate.
- The server will never write plaintext passwords to disk. Usernames are encrypted when a stable session secret is available.
- The AES key used for encryption is derived from the session secret; make sure the secret is stored persistently (use `QUI__SESSION_SECRET_FILE`) and protected by your container orchestration or host OS.

## Configuration (important environment variables)

- `UA_WEBUI_HOST`: address to bind to (default `127.0.0.1`). Use `0.0.0.0` to listen on all interfaces.
- `UA_WEBUI_PORT`: port to listen on (default `5000`).
- `UA_BROWSE_ROOTS` (required for browsing/execution): comma-separated list of absolute paths the UI is allowed to browse and execute against. If unset, browsing/execution is denied.
- `UA_TOKEN`: static opaque bearer token; when set the server treats token store as read-only and removes any persisted token store on startup.
- `UA_TEST_BEARER_TOKEN`: used by tests to inject a temporary token into the keyring (testing only).
- `UA_WEBUI_TOTP_SECRET`: base32 TOTP secret for enabling TOTP 2FA via env variable (highest priority).
- `UA_WEBUI_CORS_ORIGINS`: optional comma-separated list of allowed origins for `/api/*` CORS.

## Running in Docker

Use an image that includes the web UI runtime (the project's `-webui` images). Example `docker-compose` snippet:

```yaml
services:
  upload-assistant:
    image: your/image:webui
    environment:
      - UA_WEBUI_HOST=0.0.0.0
      - UA_WEBUI_PORT=5000
      - UA_BROWSE_ROOTS=/data/torrents,/Upload-Assistant/tmp
    ports:
      - "127.0.0.1:5000:5000"
    volumes:
      - /host/path/torrents:/data/torrents:ro
      - /host/path/upload-assistant:/Upload-Assistant
```

Notes:

- Prefer binding the UI only to localhost (`127.0.0.1`) on Docker hosts unless you intentionally want LAN access.
- If providing `UA_TOKEN` or TOTP secrets via environment variables, make sure your container runtime protects environment values or use Docker secrets when possible.

## API summary

- `GET /api/csrf_token` — returns `{ csrf_token, success }` for CSRF protection.
- `POST /api/execute` — start execution; accepts JSON `{ path, args, session_id }` and returns an SSE-style streaming response body.
- `POST /api/input` — send stdin/input to a running session.
- `POST /api/kill` — request termination of a running session by `session_id`.
- Additional management endpoints exist for authentication, config, and token management via the Web UI.


## Security and best practices

- Keep `UA_BROWSE_ROOTS` minimal and only mount the directories required for uploads.
- Do not rely on session-based interactive login in container deployments; prefer a static bearer token (`UA_TOKEN`) or create a local account via the UI and use appropriate secret management.
- When using TOTP via `UA_WEBUI_TOTP_SECRET`, treat the secret as sensitive and manage it with your platform's secret manager or Docker secrets.

### Security checklist
Use this checklist when deploying the Web UI to reduce risk and harden the runtime:

- **Bind to localhost by default:** set `UA_WEBUI_HOST=127.0.0.1` unless you intentionally need network access; expose via an authenticated reverse proxy when remote access is required.
- **Prefer managed secrets:** provide `UA_TOKEN`, `UA_WEBUI_TOTP_SECRET`, or credentials via Docker/Kubernetes secrets or your platform's secret manager rather than plaintext environment variables when possible.
- **Require authentication for non-local access:** provision a static bearer token (`UA_TOKEN`) or create a local UI account (and enable TOTP) when the UI is reachable from other hosts.
- **Restrict `UA_BROWSE_ROOTS`:** list only the absolute paths required for upload/browse operations and mount volumes read-only where feasible.
- **Run unprivileged:** do not run the Web UI as root; restrict filesystem permissions so the server user cannot write to unrelated user data or system locations.
- **Harden token/keyring storage:** ensure keyring backends and config paths are permissible and not writable by untrusted users; avoid leaving test tokens or temporary keyring entries in production.
- **Network controls:** firewall host ports, avoid automatic UPnP/port-forwarding, and publish ports only on necessary interfaces.
- **Rotate and revoke credentials:** have a process to rotate `UA_TOKEN` / TOTP secrets and remove persisted tokens when changing auth methods.
- **Monitor and alert:** collect server logs and monitor for unexpected config changes, token writes, or repeated failed auth attempts.
