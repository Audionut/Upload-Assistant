# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import subprocess
import json
import os
import sys
import traceback
import re
import threading
import queue
import hmac
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

app = Flask(__name__)


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
    CORS(app, resources={r"/api/*": {"origins": cors_origins}}, allow_headers=["Content-Type", "Authorization"])

# ANSI color code regex pattern
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# Store active processes
active_processes = {}


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
    if not hmac.compare_digest(auth.password or '', expected_password):
        return False

    return True


def _auth_required_response():
    return Response(
        'Authentication required',
        401,
        {'WWW-Authenticate': 'Basic realm="Upload Assistant Web UI"'},
    )


@app.before_request
def _require_basic_auth_for_webui():
    # Health endpoint can be used for orchestration checks.
    if request.path == '/api/health':
        return None

    # If user configured auth, require it for everything (including / and static).
    # This makes remote deployment safer by default.
    if _webui_auth_configured() and not _webui_auth_ok():
        return _auth_required_response()

    return None


def _validate_upload_assistant_args(tokens: list[str]) -> list[str]:
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
        return [os.path.abspath(os.sep)]

    roots: list[str] = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        root = os.path.abspath(part)
        roots.append(root)

    return roots or [os.path.abspath(os.sep)]


def _resolve_user_path(
    user_path: str | None,
    *,
    require_exists: bool = True,
    require_dir: bool = False,
) -> str:
    roots = _get_browse_roots()
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
    # Do not rely on string replacement for traversal ("../"); instead:
    # - join (when relative)
    # - normpath
    # - realpath + commonpath check (prevents symlink-escape)
    matched_root: str | None = None
    candidate_norm: str | None = None

    if expanded and os.path.isabs(expanded):
        for root in roots:
            root_abs = os.path.abspath(root)
            try:
                rel = os.path.relpath(expanded, root_abs)
            except ValueError:
                # Different drive on Windows.
                continue

            if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
                continue

            matched_root = root_abs
            candidate_norm = os.path.normpath(os.path.join(root_abs, rel))
            break
    else:
        matched_root = os.path.abspath(default_root)
        candidate_norm = os.path.normpath(os.path.join(matched_root, expanded))

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
        raise ValueError(f'Path does not exist: {candidate}')

    if require_dir and not os.path.isdir(candidate):
        raise ValueError(f'Not a directory: {candidate}')

    return candidate


def _resolve_browse_path(user_path: str | None) -> str:
    return _resolve_user_path(user_path, require_exists=True, require_dir=True)


def strip_ansi(text):
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
        items = []
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
                        while True:
                            chunk = process.stderr.read(1)
                            if not chunk:
                                break
                            output_queue.put(('stderr', chunk))
                    except Exception as e:
                        print(f"stderr read error: {e}")

                output_queue = queue.Queue()

                # Start threads (no input thread needed - we write directly)
                stdout_thread = threading.Thread(target=read_stdout, daemon=True)
                stderr_thread = threading.Thread(target=read_stderr, daemon=True)

                stdout_thread.start()
                stderr_thread.start()

                # Stream output as raw characters
                while process.poll() is None or not output_queue.empty():
                    try:
                        output_type, char = output_queue.get(timeout=0.1)
                        # Send raw character data (preserves ANSI codes)
                        yield f"data: {json.dumps({'type': output_type, 'data': char})}\n\n"
                    except queue.Empty:
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
def not_found(e):
    return jsonify({'error': 'Not found', 'success': False}), 404


@app.errorhandler(500)
def internal_error(e):
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
