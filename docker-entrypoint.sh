#!/bin/bash
set -e

# Activate virtual environment (where Flask is installed)
source /venv/bin/activate

# Start Web UI if enabled
if [ "$ENABLE_WEB_UI" = "true" ]; then
    echo "Starting Upload Assistant Web UI..."
    cd /Upload-Assistant
    python web_ui/server.py &
    WEB_UI_PID=$!
    echo "Web UI started with PID: $WEB_UI_PID"
    echo "Access at: http://localhost:5000"
fi

# If no command is provided, or the first argument is not an executable,
# default to running upload.py with the supplied arguments.
if [ $# -eq 0 ]; then
    set -- python upload.py
elif ! command -v "$1" >/dev/null 2>&1 && [ ! -x "$1" ]; then
    set -- python upload.py "$@"
fi

# Execute the main command
exec "$@"
