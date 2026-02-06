# Upload Assistant — Web UI (Quick Guide)

This short guide explains how to use the built-in Web UI.

### Starting the Web UI & environment variables
- Start the web UI by running `upload.py` with the `--webui HOST:PORT` argument. Example:

```bash
python upload.py "/path/to/folder" "/another/path" --webui 127.0.0.1:8080
```

- Path handling: you may pass one or more paths on the command line; when `--webui` is used and no `UA_BROWSE_ROOTS` env var is set, the supplied positional paths become the web UI browse roots. Multiple paths are accepted and are joined with commas internally (equivalent to the `UA_BROWSE_ROOTS` format).

- `UA_BROWSE_ROOTS` (optional): you can instead configure browse roots via the environment variable `UA_BROWSE_ROOTS` as a comma-separated list of directories. If `UA_BROWSE_ROOTS` is present it takes precedence over the command-line paths.

- Other optional environment variables used by the Web UI:
	- `UA_WEBUI_USE_SUBPROCESS` — if set (non-empty) the server will run uploads in a subprocess rather than in-process (affects interactive behavior and Rich output recording).
	- `UA_WEBUI_CORS_ORIGINS` — comma-separated list of allowed origins for `/api/*` when remote clients need cross-origin access.
	- `SESSION_SECRET` or `SESSION_SECRET_FILE` — provide a stable session secret (permission handling needed). Do not just use this by default.

Notes:
- The server enforces that browse roots only the only configured roots (it will not expose arbitrary filesystem locations). Paths supplied on the command line or via `UA_BROWSE_ROOTS` are normalized and validated by the server before being exposed.
- If you get "No browse roots specified" when starting with `--webui`, set `UA_BROWSE_ROOTS` or pass one or more paths on the command line as in the example above.
- The webui arg uses `127.0.0.1:5000` by default. `HOST:PORT` are only needed if overriding.

### Open the UI
- Point your browser to the host and port where Upload Assistant is running, for example `http://127.0.0.1:5000`, you will be redirect to `login`.

### Login / First run
- If no local user exists, the UI allows a first-run user creation from the login page. Enter a username and a strong password to create the local user. Only one user may be created.
- The login page supports optional 2FA and recovery codes when 2FA is enabled.
- The UI supports a "Remember me" cookie so you can remain logged in across restarts.

### Two-factor authentication (2FA)
- You can enable TOTP 2FA from the Security settings page in the Config UI section. The setup generates a TOTP secret and provisioning URI (QR code) plus one-time recovery codes — scan the QR with your authenticator app, verify a generated code in the UI to enable 2FA, and store recovery codes securely (they are consumed when used). These 2FA operations require a logged-in browser session.

### File browser
- The left panel shows configured browse roots and filesystem folders. The browse roots are provided either by the runtime path (see `upload.py`) or the environment variable `UA_BROWSE_ROOTS` (comma-separated). The browser only shows configured roots — it will not expose the whole filesystem. Supported video extensions shown in the browser are `.mkv`, `.mp4`, and `.ts`, as well as disc based paths. Everything else is filtered.

### Argument list
- The right panel (resizable) shows all of the available arguments that can be used. Click an argument to add that argument to the `additional arguments` list.

### Running an upload (interactive)
- Select a file or folder from the left panel, add optional CLI arguments in the Arguments field, then click "Execute Upload". The UI calls `/api/execute` and streams output back using Server-Sent Events (SSE). The UI renders Rich HTML fragments from the uploader.
- If the running process prompts for input the UI shows an input box — responses are sent via the input box at the bottom of the page (calls `/api/input`) for the active session. You can cancel or kill a running job with the "Kill"/"Clear" control (calls `/api/kill`).
- Execution can run either in-process (preserving Rich output and interactive prompts) or as a subprocess. The runtime mode can be controlled with the environment variable `UA_WEBUI_USE_SUBPROCESS`.

### Config editor
- The "View Config" button opens a config editor served at `/config`. The editor reads options from `data/example-config.py` and applies overrides in `data/config.py`. Users without a config.py file will have a file created from the example-config.py file.
- The editor performs type coercion and writes updates back into the config file `data/config.py`. Changes are audited to `data/config_audit.log`.
- Use the config editor for common changes like adding torrent clients, image hosts, or toggling features.

### Access control
- You can monitor and control access from the UI (Config → Access Log). By default, the webui will log all failed api requests (bad calls, wrong credentials). You can adjust the log level via the Access Log Settings. The access log is stored in the same location as `webui_auth.json`. Recent access log entries are viewable in the UI.
- Repeated failed api endpoint access attempts, will have the associated IP address automatically blacklisted.
- Blacklisted IP's take precedence, and will be blacklisted even if they have been whitelisted.

### API tokens
- You can create API bearer tokens from the UI (Config → Security → API Tokens). Tokens are stored with the user record and can be used as `Authorization: Bearer <token>` for API requests. The UI manages tokens via `/api/tokens`.
- Bearer tokens are accepted for certain API calls (for example `/api/browse` and `/api/execute`). Bearer tokens cannot be used for api endpoints that touch sensitive areas.

### CORS and remote access
- Cross-origin API access for `/api/*` can be configured with the `UA_WEBUI_CORS_ORIGINS` environment variable (comma-separated). Without that, the UI is intended to be used from the same host or a reverse proxy.

### Cloudflare proxy access
- When running through a cloudflare proxy, you likely need to disable `Real User Measurements` from the cloudflare dashboard, then `caching/configuration` and `purge everything`.

### Notes and troubleshooting
- If browsing is not configured (no browse roots), the file browser will be empty — set `UA_BROWSE_ROOTS` or configure `upload.py` to set the runtime browse roots.
- Credentials and recovery storage: the Web UI stores the encrypted local user record (password hash, API tokens, 2FA secret/recovery hashes) in `webui_auth.json` under the application config directory. On Windows this is under `%APPDATA%/upload-assistant` by default; on Unix-like systems it prefers `XDG_CONFIG_HOME` or the repository `data/` directory depending on environment (docker users should correctly map as needed).

- Resetting password / 2FA problems: stopping the web UI and removing the `webui_auth.json` file in the app config dir will remove the persisted user record and allow you to recreate a local user via the login page (this also removes persisted API tokens and recovery codes). If you rely on a persisted session secret, `session_secret` in the config dir may be used to derive encryption keys — removing or changing it will invalidate encrypted fields, so treat that file carefully.

### Security checklist
Use this checklist when deploying the Web UI to reduce risk and harden the runtime:

- **Bind to localhost by default:** set `UA_WEBUI_HOST=127.0.0.1` unless you intentionally need network access; expose via an authenticated reverse proxy when remote access is required.
- **Prefer managed secrets:** provide `SESSION_SECRET`, `SESSION_SECRET_FILE`, via environment variables when possible. Ensure any file/directory has the correct permissions.
- **Restrict `UA_BROWSE_ROOTS`:** list only the absolute paths required for upload/browse operations and mount volumes read-only where feasible.
- **Run unprivileged:** do not run the Web UI as root; restrict filesystem permissions so the server user cannot write to unrelated user data or system locations.
- **Network controls:** firewall host ports, avoid automatic UPnP/port-forwarding, and publish ports only on necessary interfaces.
- **Monitor and alert:** collect server logs and monitor for unexpected config changes, token writes, or repeated failed auth attempts.