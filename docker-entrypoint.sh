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

# Execute the main command
exec "$@"
