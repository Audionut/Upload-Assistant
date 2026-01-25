# Web UI API Reference

This document is a precise reference for the Web UI HTTP API used by the frontend and integrations.
It describes how to call endpoints, parameters, expected return values, streaming formats, authentication, and examples.

Base URL: the Web UI server root (e.g. `http://127.0.0.1:5000`). All paths below are relative to the base URL.

Auth & headers summary
- Authorization: Prefer `Authorization: Bearer <token>` when using API tokens. If `UA_TOKEN` is set on the server, use that token.
-- Session cookie / Basic Auth: the server may require session cookies or bearer tokens depending on configuration; Basic auth is only supported when a persisted webui user exists.
- CSRF: for state-changing requests include `X-CSRF-Token: <token>` header. Obtain token from `GET /api/csrf_token`.
- Content-Type: `application/json` for JSON requests.
- Use `credentials: 'same-origin'` or send cookies as appropriate for session-based auth.

Common HTTP status semantics
- 200: Success (body contents described per-endpoint).
- 400: Bad request (invalid parameters, missing required fields).
- 401: Unauthorized (invalid or missing auth/csrf).
- 403: Forbidden (path outside allowed `UA_BROWSE_ROOTS` or access denied).
- 404: Not found (invalid session id, path not found).
- 500: Server error.

GET /api/csrf_token
- Method: GET
- Auth: none required (used to fetch CSRF token for subsequent requests).
- Query params: none
- Response: JSON object

Example success (200):
```json
{ "csrf_token": "abc...", "success": true }
```

Notes: token may be an empty string on error; treat an empty token as unavailable and handle errors when sending requests that require CSRF.

GET /api/health
- Method: GET
- Auth: none required
- Response: JSON health object (server-dependent). Example:
```json
{ "status": "ok", "server_time": 1690000000 }
```

GET /api/browse
- Method: GET
- Auth: requires valid auth (session or bearer) if the server is configured for auth.
- Query params:
  - `path` (string, required): the path to list. Path must be under one of the configured `UA_BROWSE_ROOTS` entries.
- Response: JSON

Example success (200):
```json
{
  "success": true,
  "items": [
    { "name": "movie.mkv", "path": "/data/movie.mkv", "type": "file", "size": 123456789, "mtime": 1690000000 },
    { "name": "folder", "path": "/data/folder", "type": "folder" }
  ]
}
```

Errors:
- 400: missing `path` or invalid path format.
- 403: path outside allowed browse roots.

POST /api/execute
- Method: POST
- Auth: requires auth (session or bearer) depending on server config.
- Content-Type: `application/json`
- Request body JSON:
```json
{
  "path": "/absolute/path/to/target",
  "args": "--some-flag --other",
  "session_id": "session_<timestamp>"
}
```
- Response: streaming body (SSE-style events delivered as newline-prefixed chunks). The HTTP response status will be 200 on success and the body is a sequence of text chunks. Clients should read `response.body` with a reader (e.g. `response.body.getReader()`), decode chunks, buffer partial lines, split on `\n`, and parse lines that start with `data: `.

SSE message format
- Each server message is transmitted as a line beginning with `data: ` followed by valid JSON. Example lines:
```
data: {"type":"html","data":"<div>partial fragment</div>"}
data: {"type":"html_full","data":"<div>complete snapshot</div>"}
data: {"type":"exit","code":0}
```

Known `type` values and handling:
- `html`: an HTML fragment intended to be appended to the output stream. Render safely (sanitize) and append.
- `html_full`: a full snapshot of the current display — clients typically dedupe repeated identical full snapshots and replace or append accordingly.
- `exit`: execution finished. JSON contains `code` (process exit code). After receiving this, the server will close the stream.
- Other types may be defined by the server for logging or progress; treat unknown types as opaque JSON and surface them to the user.

Client SSE handling recommendations (JS example):
```javascript
const controller = new AbortController();
const res = await apiFetch('/api/execute', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({path, args, session_id}),
  signal: controller.signal
});
const reader = res.body.getReader();
const decoder = new TextDecoder();
let buffer = '';
while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, {stream: true});
  const parts = buffer.split('\n');
  buffer = parts.pop();
  for (const line of parts) {
    if (!line.startsWith('data: ')) continue;
    const obj = JSON.parse(line.slice(6));
    // process obj.type ...
  }
}
```

Notes: callers should check `controller.signal.aborted` if they support cancellation and avoid appending final/completion messages when aborted.

POST /api/input
- Method: POST
- Auth: session or bearer required
- Content-Type: `application/json`
- Request body:
```json
{ "session_id": "session_...", "input": "user typed input\n" }
```
- Response: JSON indicating success/failure. Example:
```json
{ "success": true }
```

POST /api/kill
- Method: POST
- Auth: session or bearer required
- Content-Type: `application/json`
- Request body:
```json
{ "session_id": "session_..." }
```
- Response: JSON indicating termination request accepted. Example:
```json
{ "success": true }
```

Authentication notes
- Bearer token: send `Authorization: Bearer <token>` header. When `UA_TOKEN` is set on the server, that is the canonical token and persisted token store is disabled.
- Basic auth / session: if `UA_WEBUI_USERNAME` / `UA_WEBUI_PASSWORD` are set, the server applies auth to routes (except `/api/health`). Use HTTP Basic Auth or the login flow to obtain session cookies.
- CSRF: obtain the CSRF token with `GET /api/csrf_token` and include it as `X-CSRF-Token` header for all POST/DELETE/PUT requests.

Errors and troubleshooting
- If you receive `401` while using `Bearer` auth, confirm token value and that Authorization header is sent.
- If `403` on `POST /api/execute` or `GET /api/browse`, confirm the `path` is under `UA_BROWSE_ROOTS` and that the server user has filesystem permission to the path.
- If streaming response unexpectedly closes, check server logs for process crashes; the SSE consumer should handle partial lines and JSON parse errors gracefully.

Testing and development
- Tests in this repository may use `UA_TEST_BEARER_TOKEN` to inject a temporary token into the keyring. The test fixture restores the original keyring store after tests complete.

Appendix: minimal Python client example (requests)
```python
import requests
import json

session = requests.Session()
csrf = session.get('http://localhost:5000/api/csrf_token').json().get('csrf_token')
headers = {'X-CSRF-Token': csrf}
res = session.post('http://localhost:5000/api/execute', json={'path': '/data', 'args':'', 'session_id':'s1'}, headers=headers, stream=True)
for chunk in res.iter_lines(decode_unicode=True):
    if not chunk: continue
    if chunk.startswith('data: '):
        obj = json.loads(chunk[6:])
        print(obj)
```
