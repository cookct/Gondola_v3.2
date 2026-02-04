#!/bin/bash

# Gondola v2.0 (Native Function Calling) Launcher
# Running on Port 5009

# Path to the virtual environment python
PYTHON_EXEC="/home/anonymous/gemini-workspace/litellm_venv/bin/python"

# Path to the server script
SERVER_SCRIPT="venice-web-ui/server.py"

# Ensure we are in the Project directory
cd "$(dirname "$0")"

echo "------------------------------------------------"
echo "Starting Gondola v2.0 (NATIVE)..."
echo "URL: http://localhost:5009"
echo "------------------------------------------------"

# Generate ctags index in background
ctags -R -o .gondola_tags . 2>/dev/null &

# Run the server
$PYTHON_EXEC $SERVER_SCRIPT