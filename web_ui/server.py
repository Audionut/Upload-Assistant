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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

app = Flask(__name__)
CORS(app)

# ANSI color code regex pattern
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# Store active processes
active_processes = {}


def strip_ansi(text):
    """Remove ANSI escape codes from text"""
    return ANSI_ESCAPE.sub('', text)


@app.route('/')
def index():
    """Serve the main UI"""
    try:
        return render_template('index.html')
    except Exception as e:
        error_msg = f"Error loading template: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_msg)
        return f"<pre>{error_msg}</pre>", 500


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
    path = request.args.get('path', '/')
    print(f"Browsing path: {path}")

    try:
        if not os.path.exists(path):
            return jsonify({
                'error': f'Path does not exist: {path}',
                'success': False
            }), 404

        if not os.path.isdir(path):
            return jsonify({
                'error': f'Not a directory: {path}',
                'success': False
            }), 400

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
            error_msg = f'Permission denied: {path}'
            print(f"Error: {error_msg}")
            return jsonify({'error': error_msg, 'success': False}), 403

        return jsonify({
            'items': items,
            'success': True,
            'path': path,
            'count': len(items)
        })

    except Exception as e:
        error_msg = f'Error browsing {path}: {str(e)}'
        print(f"Error: {error_msg}")
        print(traceback.format_exc())
        return jsonify({'error': error_msg, 'success': False}), 500


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
                command = ['python', '-u', '/Upload-Assistant/upload.py', path]

                # Add arguments if provided
                if args:
                    import shlex
                    command.extend(shlex.split(args))

                print(f"Running: {' '.join(command)}")

                yield f"data: {json.dumps({'type': 'system', 'data': f'Executing: {' '.join(command)}'})}\n\n"

                # Set environment to unbuffered and force line buffering
                env = os.environ.copy()
                env['PYTHONUNBUFFERED'] = '1'
                env['PYTHONIOENCODING'] = 'utf-8'
                # Disable Python output buffering

                process = subprocess.Popen(
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
                error_msg = f'Execution error: {str(e)}'
                print(f"Error: {error_msg}")
                print(traceback.format_exc())
                yield f"data: {json.dumps({'type': 'error', 'data': error_msg})}\n\n"

                # Clean up on error
                if session_id in active_processes:
                    del active_processes[session_id]

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        error_msg = f'Request error: {str(e)}'
        print(f"Error: {error_msg}")
        print(traceback.format_exc())
        return jsonify({'error': error_msg, 'success': False}), 500


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
            print(f"Error writing to stdin: {str(e)}")
            return jsonify({'error': f'Failed to write input: {str(e)}', 'success': False}), 500

        return jsonify({'success': True})

    except Exception as e:
        error_msg = f'Input error: {str(e)}'
        print(f"Error: {error_msg}")
        return jsonify({'error': error_msg, 'success': False}), 500


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
        error_msg = f'Kill error: {str(e)}'
        print(f"Error: {error_msg}")
        return jsonify({'error': error_msg, 'success': False}), 500


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
    print("Server will run at: http://localhost:5000")
    print("Health check: http://localhost:5000/api/health")
    print("=" * 50)

    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            threaded=True,
            use_reloader=False
        )
    except Exception as e:
        print(f"FATAL: Failed to start server: {str(e)}")
        print(traceback.format_exc())
        sys.exit(1)
