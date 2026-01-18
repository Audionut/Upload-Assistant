# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false
import hmac
import json
import os
import queue
import re
import subprocess
import sys
import threading
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict, Union, cast

from flask import Flask, Response, jsonify, render_template, request  # pyright: ignore[reportMissingImports]
from flask_cors import CORS  # pyright: ignore[reportMissingModuleSource]
from werkzeug.security import safe_join  # pyright: ignore[reportMissingImports]

sys.path.insert(0, str(Path(__file__).parent.parent))

Flask = cast(Any, Flask)
Response = cast(Any, Response)
jsonify = cast(Any, jsonify)
render_template = cast(Any, render_template)
request = cast(Any, request)
CORS_fn = cast(Any, CORS)
safe_join = cast(Any, safe_join)

app: Any = Flask(__name__)


def _parse_cors_origins() -> list[str]:
    raw = os.environ.get('UA_WEBUI_CORS_ORIGINS', '').strip()
    if not raw:
        return []
    origins: list[str] = []
    for part in raw.split(','):
        part = part.strip()
        if part:
            origins.append(part)
    return origins


cors_origins = _parse_cors_origins()
if cors_origins:
    CORS_fn(app, resources={r"/api/*": {"origins": cors_origins}}, allow_headers=["Content-Type", "Authorization"])

# ANSI color code regex pattern
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

class ProcessInfo(TypedDict):
    process: subprocess.Popen[str]


# Store active processes
active_processes: dict[str, ProcessInfo] = {}


class BrowseItem(TypedDict):
    """Serialized representation of an entry returned by the browse API."""

    name: str
    path: str
    type: Literal['folder', 'file']
    children: Union[list['BrowseItem'], None]


def _webui_auth_configured() -> bool:
    return bool(os.environ.get('UA_WEBUI_USERNAME')) or bool(os.environ.get('UA_WEBUI_PASSWORD'))


def _webui_auth_ok() -> bool:
    expected_username = os.environ.get('UA_WEBUI_USERNAME', '')
    expected_password = os.environ.get('UA_WEBUI_PASSWORD', '')

    # If auth is configured at all, require both values.
    if not expected_username or not expected_password:
        return False

    auth = request.authorization
    if not auth or auth.type != 'basic':
        return False

    # Constant-time compare to avoid leaking timing info.
    if not hmac.compare_digest(auth.username or '', expected_username):
        return False
    return hmac.compare_digest(auth.password or '', expected_password)


def _auth_required_response():
    return Response(
        'Authentication required',
        401,
        {'WWW-Authenticate': 'Basic realm="Upload Assistant Web UI"'},
    )


@app.before_request
def _require_basic_auth_for_webui():  # pyright: ignore[reportUnusedFunction]
    # Health endpoint can be used for orchestration checks.
    if request.path == '/api/health':
        return None

    # If user configured auth, require it for everything (including / and static).
    # This makes remote deployment safer by default.
    if _webui_auth_configured() and not _webui_auth_ok():
        return _auth_required_response()

    return None


def _validate_upload_assistant_args(tokens: Sequence[Any]) -> list[str]:
    # These are passed to upload.py (not the Python interpreter) and are executed
    # with shell=False. Still validate to avoid control characters and abuse.
    safe: list[str] = []
    for tok in tokens:
        if not isinstance(tok, str):
            raise TypeError('Invalid argument')
        if not tok or len(tok) > 1024:
            raise ValueError('Invalid argument')
        if '\x00' in tok or '\n' in tok or '\r' in tok:
            raise ValueError('Invalid characters in argument')
        safe.append(tok)
    return safe


def _get_browse_roots() -> list[str]:
    raw = os.environ.get('UA_BROWSE_ROOTS', '').strip()
    if not raw:
        # Require explicit configuration; do not default to the filesystem root.
        return []

    roots: list[str] = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        root = os.path.abspath(part)
        roots.append(root)

    return roots


def _resolve_user_path(
    user_path: Optional[Any],
    *,
    require_exists: bool = True,
    require_dir: bool = False,
) -> str:
    roots = _get_browse_roots()
    if not roots:
        raise ValueError('Browsing is not configured')

    default_root = roots[0]

    if user_path is None or user_path == '':
        expanded = ''
    else:
        if not isinstance(user_path, str):
            raise ValueError('Path must be a string')
        if len(user_path) > 4096:
            raise ValueError('Invalid path')
        if '\x00' in user_path or '\n' in user_path or '\r' in user_path:
            raise ValueError('Invalid characters in path')

        expanded = os.path.expandvars(os.path.expanduser(user_path))

    # Build a normalized path and validate it against allowlisted roots.
    # Use werkzeug.utils.safe_join as the initial join/sanitizer, then also
    # enforce a realpath+commonpath constraint to prevent symlink escapes.
    matched_root: Union[str, None] = None
    candidate_norm: Union[str, None] = None

    if expanded and os.path.isabs(expanded):
        # If a user supplies an absolute path, only allow it if it is under
        # one of the configured browse roots (or their realpath equivalents,
        # since the browse API returns realpath-resolved paths to the frontend).
        for root in roots:
            root_abs = os.path.abspath(root)
            root_real = os.path.realpath(root_abs)

            # Check against both the configured root and its realpath.
            # This handles the case where the frontend sends back a realpath
            # (e.g., /mnt/storage/torrents) that was returned by a previous
            # browse call, but the configured root is a symlink (e.g., /data/torrents).
            for check_root in (root_abs, root_real):
                try:
                    rel = os.path.relpath(expanded, check_root)
                except ValueError:
                    # Different drive on Windows.
                    continue

                if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
                    continue

                # Handle the case where the path equals the root exactly.
                # safe_join may return None for '.' in some Werkzeug versions.
                if rel == '.':
                    matched_root = check_root
                    candidate_norm = os.path.normpath(check_root)
                    break

                joined = safe_join(check_root, rel)
                if joined is None:
                    continue

                matched_root = check_root
                candidate_norm = os.path.normpath(joined)
                break

            if matched_root:
                break
    else:
        matched_root = os.path.abspath(default_root)
        # Handle empty path (initial browse request) - use the root directly.
        # safe_join may return None for empty strings in some Werkzeug versions.
        if not expanded:
            candidate_norm = os.path.normpath(matched_root)
        else:
            joined = safe_join(matched_root, expanded)
            if joined is None:
                raise ValueError('Browsing this path is not allowed')
            candidate_norm = os.path.normpath(joined)

    if not matched_root or not candidate_norm:
        raise ValueError('Browsing this path is not allowed')

    candidate_real = os.path.realpath(candidate_norm)
    root_real = os.path.realpath(matched_root)
    try:
        if os.path.commonpath([candidate_real, root_real]) != root_real:
            raise ValueError('Browsing this path is not allowed')
    except ValueError as e:
        # ValueError can happen on Windows if drives differ.
        raise ValueError('Browsing this path is not allowed') from e

    candidate = candidate_real

    if require_exists and not os.path.exists(candidate):
        raise ValueError('Path does not exist')

    if require_dir and not os.path.isdir(candidate):
        raise ValueError('Not a directory')

    return candidate


def _resolve_browse_path(user_path: Union[str, None]) -> str:
    return _resolve_user_path(user_path, require_exists=True, require_dir=True)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text"""
    return ANSI_ESCAPE.sub('', text)


@app.route('/')
def index():
    """Serve the main UI"""
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"Error loading template: {e}")
        print(traceback.format_exc())
        return "<pre>Internal server error</pre>", 500


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'success': True,
        'message': 'Upload Assistant Web UI is running'
    })


@app.route('/api/browse')
def browse_path():
    """Browse filesystem paths"""
    requested = request.args.get('path', '')
    try:
        path = _resolve_browse_path(requested)
    except ValueError as e:
        # Log details server-side, but avoid leaking paths/internal details to clients.
        print(f"Path resolution error for requested {requested!r}: {e}")
        return jsonify({'error': 'Invalid path specified', 'success': False}), 400

    print(f"Browsing path: {path}")

    try:
        items: list[BrowseItem] = []
        try:
            for item in sorted(os.listdir(path)):
                # Skip hidden files
                if item.startswith('.'):
                    continue

                full_path = os.path.join(path, item)
                try:
                    is_dir = os.path.isdir(full_path)

                    items.append({
                        'name': item,
                        'path': full_path,
                        'type': 'folder' if is_dir else 'file',
                        'children': [] if is_dir else None
                    })
                except (PermissionError, OSError):
                    continue

            print(f"Found {len(items)} items in {path}")

        except PermissionError:
            print(f"Error: Permission denied: {path}")
            return jsonify({'error': 'Permission denied', 'success': False}), 403

        return jsonify({
            'items': items,
            'success': True,
            'path': path,
            'count': len(items)
        })

    except Exception as e:
        print(f"Error browsing {path}: {e}")
        print(traceback.format_exc())
        return jsonify({'error': 'Error browsing path', 'success': False}), 500


@app.route('/api/execute', methods=['POST', 'OPTIONS'])
def execute_command():
    """Execute upload.py with interactive terminal support"""

    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data received', 'success': False}), 400

        path = data.get('path')
        args = data.get('args', '')
        session_id = data.get('session_id', 'default')

        print(f"Execute request - Path: {path}, Args: {args}, Session: {session_id}")

        if not path:
            return jsonify({
                'error': 'Missing path',
                'success': False
            }), 400

        def generate():
            try:
                # Build command to run upload.py directly
                validated_path = _resolve_user_path(path, require_exists=True, require_dir=False)

                upload_script = '/Upload-Assistant/upload.py'
                command = [sys.executable, '-u', upload_script]

                # Add arguments if provided
                if args:
                    import shlex

                    parsed_args = shlex.split(args)
                    command.extend(_validate_upload_assistant_args(parsed_args))

                # Ensure any path starting with '-' can't be interpreted as an option
                command.extend(['--', validated_path])

                command_str = ' '.join(command)
                print(f"Running: {command_str}")

                yield f"data: {json.dumps({'type': 'system', 'data': f'Executing: {command_str}'})}\n\n"

                # Set environment to unbuffered and force line buffering
                env = os.environ.copy()
                env['PYTHONUNBUFFERED'] = '1'
                env['PYTHONIOENCODING'] = 'utf-8'
                # Disable Python output buffering

                process = subprocess.Popen(  # lgtm[py/command-line-injection]
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=0,  # Completely unbuffered
                    cwd='/Upload-Assistant',
                    env=env,
                    universal_newlines=True
                )

                # Store process for input handling (no queue needed)
                active_processes[session_id] = {
                    'process': process
                }

                # Thread to read stdout - stream raw output with ANSI codes
                def read_stdout():
                    try:
                        if process.stdout is None:
                            return
                        while True:
                            # Read in small chunks for real-time streaming
                            chunk = process.stdout.read(1)
                            if not chunk:
                                break
                            output_queue.put(('stdout', chunk))
                    except Exception as e:
                        print(f"stdout read error: {e}")

                # Thread to read stderr - stream raw output
                def read_stderr():
                    try:
                        if process.stderr is None:
                            return
                        while True:
                            chunk = process.stderr.read(1)
                            if not chunk:
                                break
                            output_queue.put(('stderr', chunk))
                    except Exception as e:
                        print(f"stderr read error: {e}")

                output_queue: queue.Queue[tuple[str, str]] = queue.Queue()

                # Start threads (no input thread needed - we write directly)
                stdout_thread = threading.Thread(target=read_stdout, daemon=True)
                stderr_thread = threading.Thread(target=read_stderr, daemon=True)

                stdout_thread.start()
                stderr_thread.start()

                def _read_output(q: queue.Queue[tuple[str, str]]) -> tuple[bool, Union[tuple[str, str], None]]:
                    try:
                        return True, q.get(timeout=0.1)
                    except queue.Empty:
                        return False, None

                # Stream output as raw characters
                while process.poll() is None or not output_queue.empty():
                    has_output, output = _read_output(output_queue)
                    if has_output and output is not None:
                        output_type, char = output
                        # Send raw character data (preserves ANSI codes)
                        yield f"data: {json.dumps({'type': output_type, 'data': char})}\n\n"
                    else:
                        # Send keepalive
                        yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"

                # Wait for process to finish
                process.wait()

                # Clean up
                if session_id in active_processes:
                    del active_processes[session_id]

                yield f"data: {json.dumps({'type': 'exit', 'code': process.returncode})}\n\n"

            except Exception as e:
                print(f"Execution error for session {session_id}: {e}")
                print(traceback.format_exc())
                yield f"data: {json.dumps({'type': 'error', 'data': 'Execution error'})}\n\n"

                # Clean up on error
                if session_id in active_processes:
                    del active_processes[session_id]

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        print(f"Request error: {e}")
        print(traceback.format_exc())
        return jsonify({'error': 'Request error', 'success': False}), 500


@app.route('/api/input', methods=['POST'])
def send_input():
    """Send user input to running process"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        user_input = data.get('input', '')

        print(f"Received input for session {session_id}: '{user_input}'")

        if session_id not in active_processes:
            return jsonify({'error': 'No active process', 'success': False}), 404

        # Always add newline to send the input
        input_with_newline = user_input + '\n'

        # Write to process stdin
        try:
            process_info = active_processes[session_id]
            process = process_info['process']

            if process.poll() is None:  # Process still running
                if process.stdin is not None:
                    process.stdin.write(input_with_newline)
                    process.stdin.flush()
                    print(f"Sent to stdin: '{input_with_newline.strip()}'")
            else:
                print(f"Process already terminated for session {session_id}")
                return jsonify({'error': 'Process not running', 'success': False}), 400

        except Exception as e:
            print(f"Error writing to stdin for session {session_id}: {e}")
            print(traceback.format_exc())
            return jsonify({'error': 'Failed to write input', 'success': False}), 500

        return jsonify({'success': True})

    except Exception as e:
        print(f"Input error: {e}")
        print(traceback.format_exc())
        return jsonify({'error': 'Input error', 'success': False}), 500


@app.route('/api/kill', methods=['POST'])
def kill_process():
    """Kill a running process"""
    try:
        data = request.json
        session_id = data.get('session_id')

        print(f"Kill request for session {session_id}")

        if session_id not in active_processes:
            return jsonify({'error': 'No active process', 'success': False}), 404

        # Get the process
        process_info = active_processes[session_id]
        process = process_info['process']

        # Terminate the process
        process.terminate()

        # Give it a moment to terminate gracefully
        try:
            process.wait(timeout=2)
        except Exception:
            # Force kill if it doesn't terminate
            process.kill()

        # Clean up
        del active_processes[session_id]

        print(f"Process killed for session {session_id}")
        return jsonify({'success': True, 'message': 'Process terminated'})

    except Exception as e:
        print(f"Kill error: {e}")
        print(traceback.format_exc())
        return jsonify({'error': 'Kill error', 'success': False}), 500


@app.errorhandler(404)
def not_found(_e: Exception):
    return jsonify({'error': 'Not found', 'success': False}), 404


@app.errorhandler(500)
def internal_error(e: Exception):
    print(f"500 error: {str(e)}")
    print(traceback.format_exc())
    return jsonify({'error': 'Internal server error', 'success': False}), 500


if __name__ == '__main__':
    print("=" * 50)
    print("Starting Upload Assistant Web UI...")
    print("=" * 50)
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    host = os.environ.get('UA_WEBUI_HOST', '127.0.0.1').strip() or '127.0.0.1'
    try:
        port = int(os.environ.get('UA_WEBUI_PORT', '5000'))
    except ValueError:
        port = 5000

    scheme = 'http'
    print(f"Server will run at: {scheme}://{host}:{port}")
    print(f"Health check: {scheme}://{host}:{port}/api/health")
    if _webui_auth_configured():
        if not os.environ.get('UA_WEBUI_USERNAME') or not os.environ.get('UA_WEBUI_PASSWORD'):
            print("WARNING: UA_WEBUI_USERNAME/UA_WEBUI_PASSWORD must both be set for auth to work")
        else:
            print("Auth: HTTP Basic Auth enabled")
    else:
        print("Auth: disabled (set UA_WEBUI_USERNAME and UA_WEBUI_PASSWORD to enable)")
    print("=" * 50)

    try:
        app.run(
            host=host,
            port=port,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except Exception as e:
        print(f"FATAL: Failed to start server: {str(e)}")
        print(traceback.format_exc())
        sys.exit(1)
