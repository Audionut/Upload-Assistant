# Upload Assistant — Web UI API Reference

This document summarizes the Web UI HTTP API implemented in web_ui/server.py. For each endpoint: HTTP methods, authentication/CSRF requirements, accepted payload or query parameters, special rules (token rules, rate limits), and example response shapes.

---

### /api/health
- Methods: GET
- Auth: none
- Description: basic health check
- Response: {"status": "healthy", "success": true, "message": "..."}

### /api/execute
- Methods: POST, OPTIONS
- Auth: POST requires CSRF header for web session callers; Bearer tokens (API tokens) are accepted for programmatic use and bypass CSRF. Token must be valid.
- Rate limit: 100 per hour (keyed by _rate_limit_key_func)
- POST payload: {"path": "`<file-or-folder>`", "args": "`<cmdline args>`", "session_id": "`<id>`"}
- Description: start an `upload.py` run (either in a subprocess or in-process). The endpoint returns a Server-Sent Events (SSE) stream — connect using `Accept: text/event-stream` and read events as they arrive. `OPTIONS` responds with 204 for CORS preflight.
- Notes on payload quoting and Windows paths:
  - JSON values must use double quotes. When sending Windows paths from shells that perform quoting/escaping (PowerShell, cmd.exe), backslashes need special handling (escape them or use forward slashes). To avoid brittle quoting, prefer one of the approaches in the examples below.
  - The server attempts tolerant parsing: it accepts JSON, form-encoded bodies, or will attempt conservative normalization of raw bodies to extract `path` and `session_id` if standard JSON parsing fails. However, relying on correct JSON or a file payload is recommended for reliability.
- Response: SSE stream on success. On immediate validation or parse errors the API returns JSON like {"error":"...","success":false} (HTTP 4xx/5xx as appropriate).

Examples

- Simple streaming curl (Unix-like / WSL / Git Bash). Use forward slashes to avoid escaping backslashes in Windows paths:

```bash
curl -N \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -X POST "http://127.0.0.1:5000/api/execute" \
  -d '{"path":"D:/Movies/My Movie.mkv","session_id":"{hash}"}'
```

- curl reading payload from a file (recommended to avoid quoting/escaping issues):

Create `payload.json` containing:

```json
{"path":"D:/Movies/My Movie.mkv","session_id":"{hash}"}
```

Then:

```bash
curl -N -H "Authorization: Bearer <API_TOKEN>" -H "Content-Type: application/json" -H "Accept: text/event-stream" --data-binary @payload.json http://127.0.0.1:5000/api/execute
```

- Windows (PowerShell / cmd) curl example — escape JSON double quotes or use a payload file. Example with escaped quotes:

```powershell
curl.exe -N -H "Authorization: Bearer <API_TOKEN>" -H "Content-Type: application/json" -H "Accept: text/event-stream" -X POST "http://127.0.0.1:5000/api/execute" -d "{\"path\":\"D:/Movies/My Movie.mkv\",\"session_id\":\"{hash}\"}"
```

If you run Qui (or any external program runner) that substitutes placeholders into arguments, prefer writing a small wrapper script on the Qui host that builds the JSON via a language-native serializer (PowerShell `ConvertTo-Json`, `jq`, Python, etc.) — this avoids brittle shell quoting and escaping.

### Arguments and validation

- `args` field: when provided, the endpoint expects `args` to be a single string containing the command-line arguments you want passed to `upload.py`.

```bash
curl -N \
  -H "Authorization: Bearer <API_TOKEN>" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -X POST "http://127.0.0.1:5000/api/execute" \
  -d '{"path":"D:/Movies/My Movie.mkv","args":"--debug -season 01","session_id":"{hash}"}'
```


### Qui-specific PowerShell example

If you plan to run `curl.exe` from Qui on a Windows host using PowerShell, use `powershell.exe` as the program path and pass a single `-Command` string so placeholders are substituted by Qui before PowerShell runs. This example includes the Upload‑Assistant `-ua` argument via the `args` payload key and shows quoting that avoids PowerShell parsing issues:

Program Path (Qui):

```
powershell.exe
```

Arguments Template (Qui):

```
-NoProfile -NonInteractive -Command "curl.exe -sS -X POST -H 'Content-Type: application/json' -H 'Authorization: Bearer <API_TOKEN>' -d '{"path":"{content_path}","args":"-ua","session_id":"{hash}"}' http://127.0.0.1:5000/api/execute"
```

Notes:
- Qui will substitute `{content_path}` and `{hash}` into the arguments template before launching PowerShell. The JSON payload is wrapped as one argument to `curl.exe` and uses escaped double-quotes so PowerShell passes the literal JSON to `curl.exe`.
- If Upload‑Assistant is not on `127.0.0.1:5000` from the Qui host, replace the URL with the reachable service address.
- If you face quoting headaches, prefer the wrapper script approach (PowerShell `ConvertTo-Json` or a small `.ps1` file) which avoids manual JSON escaping.
- No terminal is required/terminal does not work with the above setup.

### /api/input
- Methods: POST
- Auth: requires either a valid Bearer API token (programmatic clients) OR a logged-in web session. Bearer tokens are allowed without CSRF; session callers must be authenticated. Rate-limited.
- Rate limit: 200 per hour
- POST payload: {"session_id": "default", "input": "..."}
- Description: send interactive input to a running execution session (inproc queue or subprocess stdin)
- Response: {"success": true} or error JSON

### /api/kill
- Methods: POST
- Auth: requires either a valid Bearer API token (programmatic clients) OR a logged-in web session. Bearer tokens are allowed without CSRF; session callers must be authenticated. Rate-limited.
- Rate limit: 50 per hour
- POST payload: {"session_id": "..."}
- Description: terminate a running execution session and perform cleanup
- Response: {"success": true, "message": "..."} or error JSON

### /api/browse
- Methods: GET
- Auth: requires either a valid Bearer API token (programmatic use) OR a logged-in web session + CSRF + Origin (same-origin). Bearer tokens are allowed without CSRF; session callers must provide `X-CSRF-Token` and same-origin headers.
- Query params: path (filesystem path within configured browse roots)
- Description: lists files and subfolders in resolved path; skips unsupported video extensions and hidden files
- Response: {"items": [...], "success": true, "path": "...", "count": N}

---
The following endpoints via a valid web session.

### /api/csrf_token
- Methods: GET
- Auth: requires web session (login/remember)
- Description: returns per-session CSRF token for use by the frontend
- Response: {"csrf_token": "`<token>`", "success": true}

### /api/2fa/status
- Methods: GET
- Auth: requires web session + CSRF + Origin (same-origin)
- Description: whether TOTP 2FA is enabled for the user
- Response: {"enabled": true|false, "success": true}

### /api/access_log/level
- Methods: GET, POST
- Auth: GET — requires web session + CSRF + Origin; POST — requires web session + CSRF + Origin
- POST payload: {"level": "access_denied"|"access"|"disabled"}
- Description: read or set access logging level
- Responses: GET -> {"success": true, "level": "..."}; POST -> {"success": true, "level": "..."}

### /api/access_log/entries
- Methods: GET
- Auth: requires web session + CSRF + Origin
- Query params: n (number of entries, default 50, max 200)
- Description: returns recent access log entries
- Response: {"success": true, "entries": [...]} 

### /api/ip_control
- Methods: GET, POST
- Auth: requires web session + CSRF + Origin for both GET and POST
- POST payload: {"whitelist": ["1.2.3.4"], "blacklist": ["5.6.7.8"]}
- Description: read or update IP whitelist/blacklist (IP addresses validated)
- Response: GET -> {"success": true, "whitelist": [...], "blacklist": [...]}; POST -> {"success": true}

### /api/2fa/setup
- Methods: POST
- Auth: requires web session + CSRF + Origin (disallows API tokens or basic auth)
- Description: generate a temporary TOTP secret, provisioning URI and one-time recovery codes; stores temp values in session
- Response: {"secret": "`<base32>`", "uri": "otpauth://...", "recovery_codes": [...], "success": true}

### /api/2fa/enable
- Methods: POST
- Auth: requires web session + CSRF + Origin
- POST payload: {"code": "123456"}
- Description: verify temporary TOTP code and enable 2FA; persists hashed recovery codes
- Response: {"success": true, "recovery_codes": [...]} (returns the one-time recovery codes initially generated)

### /api/2fa/disable
- Methods: POST
- Auth: requires web session + CSRF + Origin
- Description: disable 2FA for the user; clears TOTP secret and recovery codes
- Response: {"success": true}

### /api/browse_roots
- Methods: GET
- Auth: none required; if a Bearer token is provided it must be valid
- Description: returns configured browse root directories
- Response: {"items": [{"name":"...","path":"...","type":"folder"}], "success": true}

### /api/config_options
- Methods: GET
- Auth: requires web session + CSRF + Origin (disallows bearer/basic auth)
- Description: returns configuration options derived from example-config.py + user overrides
- Response: {"success": true, "sections": [...]} 

### /api/torrent_clients
- Methods: GET
- Auth: requires web session + CSRF + Origin (disallows bearer token)
- Description: returns list of configured torrent client names
- Response: {"success": true, "clients": ["qbit", ...]}

### /api/config_update
- Methods: POST
- Auth: requires web session + CSRF + Origin (disallows bearer/basic auth)
- POST payload: {"path": ["SECTION", "KEY"], "value": `<value>`} (path is array of path components)
- Description: updates data/config.py with a coerced Python literal of the provided value; special handling for certain client lists
- Response: {"success": true, "value": `<json-safe-value>`}

### /api/config_remove_subsection
- Methods: POST
- Auth: requires web session + CSRF + Origin
- POST payload: {"path": ["SECTION"]}
- Description: remove a top-level subsection from user config
- Response: {"success": true, "value": null}

### /api/tokens
- Methods: GET, POST, DELETE
- Auth: requires web session + CSRF + Origin; management disallowed via Basic/Bearer auth
- GET: lists token metadata (id, user, label, created, expiry) — does NOT return token secret values
  - Response: {"success": true, "tokens": [...], "read_only": false}
- POST: create or store a token
  - payload for generate: {"action": "generate", "label": "...", "persist": true|false}
  - payload for store: {"action": "store", "token": "`<token_string>`", "label": "..."}
  - Response (generate): {"success": true, "token": "`<token_or_null>`", "persisted": true|false}
- DELETE: revoke token
  - payload: {"id": "`<token_id>`"}
  - Response: {"success": true}

---

Notes & security model summary:
- Web session authentication (login + encrypted session cookie) is required for any endpoints that modify server state (config, tokens, IP lists, enabling/disabling 2FA). Bearer tokens are intended for programmatic calls and are accepted only on a subset of read/execute endpoints; tokens are validated as valid/invalid (no per-token scope enforcement).
- CSRF protection: state-changing endpoints invoked from the browser require a per-session CSRF token passed in a header (see `/api/csrf_token`). Token management endpoints explicitly disallow Basic/Bearer auth to ensure management is performed from the authenticated UI with CSRF protection.
- Rate limits: enforced for interactive/execution endpoints (see endpoints above). The limiter key function distinguishes authenticated sessions from unauthenticated callers.
