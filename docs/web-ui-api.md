# Upload Assistant — Web UI API Reference

This document summarizes the Web UI HTTP API implemented in web_ui/server.py. For each endpoint: HTTP methods, authentication/CSRF requirements, accepted payload or query parameters, special rules (token rules, rate limits), and example response shapes.

---

**/api/health**
- Methods: GET
- Auth: none
- Description: basic health check
- Response: {"status": "healthy", "success": true, "message": "..."}

**/api/csrf_token**
- Methods: GET
- Auth: requires web session (login/remember)
- Description: returns per-session CSRF token for use by the frontend
- Response: {"csrf_token": "<token>", "success": true}

**/api/2fa/status**
- Methods: GET
- Auth: requires web session + CSRF + Origin (same-origin)
- Description: whether TOTP 2FA is enabled for the user
- Response: {"enabled": true|false, "success": true}

- **/api/access_log/level**
- Methods: GET, POST
- Auth: GET — requires web session + CSRF + Origin; POST — requires web session + CSRF + Origin
- POST payload: {"level": "access_denied"|"access"|"disabled"}
- Description: read or set access logging level
- Responses: GET -> {"success": true, "level": "..."}; POST -> {"success": true, "level": "..."}

- **/api/access_log/entries**
- Methods: GET
- Auth: requires web session + CSRF + Origin
- Query params: n (number of entries, default 50, max 200)
- Description: returns recent access log entries
- Response: {"success": true, "entries": [...]} 

- **/api/ip_control**
- Methods: GET, POST
- Auth: requires web session + CSRF + Origin for both GET and POST
- POST payload: {"whitelist": ["1.2.3.4"], "blacklist": ["5.6.7.8"]}
- Description: read or update IP whitelist/blacklist (IP addresses validated)
- Response: GET -> {"success": true, "whitelist": [...], "blacklist": [...]}; POST -> {"success": true}

- **/api/2fa/setup**
- Methods: POST
- Auth: requires web session + CSRF + Origin (disallows API tokens or basic auth)
- Description: generate a temporary TOTP secret, provisioning URI and one-time recovery codes; stores temp values in session
- Response: {"secret": "<base32>", "uri": "otpauth://...", "recovery_codes": [...], "success": true}

**/api/2fa/enable**
- Methods: POST
- Auth: requires web session + CSRF + Origin
- POST payload: {"code": "123456"}
- Description: verify temporary TOTP code and enable 2FA; persists hashed recovery codes
- Response: {"success": true, "recovery_codes": [...]} (returns the one-time recovery codes initially generated)

**/api/2fa/disable**
- Methods: POST
- Auth: requires web session + CSRF + Origin
- Description: disable 2FA for the user; clears TOTP secret and recovery codes
- Response: {"success": true}

**/api/browse_roots**
- Methods: GET
- Auth: none required; if a Bearer token is provided it must be valid
- Description: returns configured browse root directories
- Response: {"items": [{"name":"...","path":"...","type":"folder"}], "success": true}

**/api/config_options**
- Methods: GET
- Auth: requires web session + CSRF + Origin (disallows bearer/basic auth)
- Description: returns configuration options derived from example-config.py + user overrides
- Response: {"success": true, "sections": [...]} 

**/api/torrent_clients**
- Methods: GET
- Auth: requires web session + CSRF + Origin (disallows bearer token)
- Description: returns list of configured torrent client names
- Response: {"success": true, "clients": ["qbit", ...]}

**/api/config_update**
- Methods: POST
- Auth: requires web session + CSRF + Origin (disallows bearer/basic auth)
- POST payload: {"path": ["SECTION", "KEY"], "value": <value>} (path is array of path components)
- Description: updates data/config.py with a coerced Python literal of the provided value; special handling for certain client lists
- Response: {"success": true, "value": <json-safe-value>}

**/api/config_remove_subsection**
- Methods: POST
- Auth: requires web session + CSRF + Origin
- POST payload: {"path": ["SECTION"]}
- Description: remove a top-level subsection from user config
- Response: {"success": true, "value": null}

**/api/tokens**
- Methods: GET, POST, DELETE
- Auth: requires web session + CSRF + Origin; management disallowed via Basic/Bearer auth
- GET: lists token metadata (id, user, label, created, expiry) — does NOT return token secret values
  - Response: {"success": true, "tokens": [...], "read_only": false}
- POST: create or store a token
  - payload for generate: {"action": "generate", "label": "...", "persist": true|false}
  - payload for store: {"action": "store", "token": "<token_string>", "label": "..."}
  - Response (generate): {"success": true, "token": "<token_or_null>", "persisted": true|false}
- DELETE: revoke token
  - payload: {"id": "<token_id>"}
  - Response: {"success": true}

**/api/browse**
- Methods: GET
- Auth: requires either a valid Bearer API token (programmatic use) OR a logged-in web session + CSRF + Origin (same-origin). Bearer tokens are allowed without CSRF; session callers must provide `X-CSRF-Token` and same-origin headers.
- Query params: path (filesystem path within configured browse roots)
- Description: lists files and subfolders in resolved path; skips unsupported video extensions and hidden files
- Response: {"items": [...], "success": true, "path": "...", "count": N}

- **/api/execute**
- Methods: POST, OPTIONS
- Auth: POST requires CSRF header for session callers; Bearer tokens are allowed for programmatic use (must be valid)
- Rate limit: 100 per hour (keyed by _rate_limit_key_func)
- POST payload: {"path": "<file>", "args": "<cmdline args>", "session_id": "<id>"}
- Description: starts an upload.py run (subprocess or in-process) and streams server-sent events (SSE) from the returned connection. OPTIONS returns 204.
- Response: SSE stream; on API level, initial validation errors return JSON like {"error":"...","success":false}

**/api/input**
- Methods: POST
- Auth: requires either a valid Bearer API token (programmatic clients) OR a logged-in web session. Bearer tokens are allowed without CSRF; session callers must be authenticated. Rate-limited.
- Rate limit: 200 per hour
- POST payload: {"session_id": "default", "input": "..."}
- Description: send interactive input to a running execution session (inproc queue or subprocess stdin)
- Response: {"success": true} or error JSON

**/api/kill**
- Methods: POST
- Auth: requires either a valid Bearer API token (programmatic clients) OR a logged-in web session. Bearer tokens are allowed without CSRF; session callers must be authenticated. Rate-limited.
- Rate limit: 50 per hour
- POST payload: {"session_id": "..."}
- Description: terminate a running execution session and perform cleanup
- Response: {"success": true, "message": "..."} or error JSON

---

Notes & security model summary:
- Web session authentication (login + encrypted session cookie) is required for any endpoints that modify server state (config, tokens, IP lists, enabling/disabling 2FA). Bearer tokens are intended for programmatic calls and are accepted only on a subset of read/execute endpoints; tokens are validated as valid/invalid (no per-token scope enforcement).
- CSRF protection: state-changing endpoints invoked from the browser require a per-session CSRF token passed in a header (see `/api/csrf_token`). Token management endpoints explicitly disallow Basic/Bearer auth to ensure management is performed from the authenticated UI with CSRF protection.
- Rate limits: enforced for interactive/execution endpoints (see endpoints above). The limiter key function distinguishes authenticated sessions from unauthenticated callers.
