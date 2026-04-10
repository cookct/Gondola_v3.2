#!/bin/bash

# Gondola v2.3 (Native Function Calling) Launcher
# Running on Port 5056 (Default)

PORT=${GONDOLA_PORT:-5056}

# Path to the virtual environment python
PYTHON_EXEC="/home/anonymous/gemini-workspace/litellm_venv/bin/python"

# Path to the server script
SERVER_SCRIPT="cortex-web-ui/server.py"

# Ensure we are in the Project directory
cd "$(dirname "$0")"

echo "------------------------------------------------"
echo "Starting Gondola v2.3 (NATIVE)..."
echo "URL: http://localhost:$PORT"
echo "------------------------------------------------"

# Generate ctags index in background
ctags -R -o .gondola_tags . 2>/dev/null &

# Run the server
$PYTHON_EXEC $SERVER_SCRIPT