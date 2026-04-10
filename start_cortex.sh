#!/bin/bash

# Cortex AI Launcher
# Running on Port 5058 (Default)

PORT=${CORTEX_PORT:-5058}

# Path to the virtual environment python
PYTHON_EXEC="/home/anonymous/gemini-workspace/litellm_venv/bin/python"

# Path to the server script
SERVER_SCRIPT="cortex-web-ui/server.py"

# Ensure we are in the Project directory
cd "$(dirname "$0")"

echo "------------------------------------------------"
echo "Starting Cortex AI..."
echo "URL: http://localhost:$PORT"
echo "------------------------------------------------"

# Generate ctags index in background
ctags -R -o .cortex_tags . 2>/dev/null &

# Run the server
$PYTHON_EXEC $SERVER_SCRIPT
