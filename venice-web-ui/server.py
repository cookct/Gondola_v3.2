import sys
import os
import json
import traceback
import queue
import threading
import re
import time
import uuid
import base64  # Moved to top level
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response, stream_with_context, send_from_directory

# ============================================================================
# COMPREHENSIVE DEBUG LOGGING CONFIGURATION
# ============================================================================
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f'gondola_debug_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# Create logger
logger = logging.getLogger('gondola')
logger.setLevel(logging.DEBUG)

# File handler - captures EVERYTHING
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s.%(msecs)03d | %(levelname)-8s | %(funcName)-25s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)

# Console handler - also show everything for debugging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter(
    '%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("=" * 80)
logger.info("GONDOLA DEBUG LOGGING INITIALIZED")
logger.info(f"Log file: {LOG_FILE}")
logger.info("=" * 80)

# Add parent dir to path to import venice package
sandbox_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(sandbox_dir)

# Import from the modular package
from venice.core import UI, MODELS, get_model_config
from venice.workspace import Workspace
from venice.memory import Memory
from venice.tools import CombinedTools
from venice.prompts.system import SYSTEM_PROMPT, build_system_prompt, get_checkpoint_message
from venice.api import get_api_key, execute_tool, parse_tool_call
from venice.tools.schema import TOOL_SCHEMAS

# NEW: Import smart context management modules
from venice.project_index import ProjectIndex
from venice.context_manager import ContextManager, ModelConfig
from venice.agent_state import AgentState

app = Flask(__name__)

# Configuration
# sandbox_dir is the 'gondola' root
IMAGES_DIR = os.path.join(sandbox_dir, 'images')

# Persist workspace setting to survive restarts
WORKSPACE_CONFIG_FILE = os.path.join(sandbox_dir, '.workspace_config')

def load_saved_workspace():
    """Load workspace from config file if it exists."""
    if os.path.exists(WORKSPACE_CONFIG_FILE):
        try:
            with open(WORKSPACE_CONFIG_FILE, 'r') as f:
                saved_path = f.read().strip()
                if saved_path and os.path.isdir(saved_path):
                    logger.info(f"Restored workspace from config: {saved_path}")
                    return saved_path
        except Exception as e:
            logger.warning(f"Failed to load saved workspace: {e}")
    return sandbox_dir  # Default

def save_workspace(path):
    """Save workspace path to config file."""
    try:
        with open(WORKSPACE_CONFIG_FILE, 'w') as f:
            f.write(path)
        logger.info(f"Saved workspace to config: {path}")
    except Exception as e:
        logger.warning(f"Failed to save workspace: {e}")

WORKSPACE_DIR = load_saved_workspace()
print(f"Workspace Dir: {WORKSPACE_DIR}")
print(f"Images Dir: {IMAGES_DIR}")

# Global state
workspace = None
memory = None
tools = None
client = None
messages = []
interrupt_flag = threading.Event()

# NEW: Smart context management globals
project_index = None  # Compressed project understanding
context_manager = None  # Token-aware context builder
agent_state = None  # Session state tracking

def web_symlink_handler(link_path, real_target, inside_workspace):
    """Web UI symlink handler: allow internal symlinks, deny external"""
    if inside_workspace:
        print(f"SYMLINK (allowed): {link_path} -> {real_target}")
        return True
    print(f"SYMLINK BLOCKED: {link_path} -> {real_target} (outside workspace)")
    return False

def initialize():
    global workspace, memory, tools, client, messages, interrupt_flag
    global project_index, context_manager, agent_state

    logger.info("=" * 60)
    logger.info("INITIALIZING GONDOLA SERVER")
    logger.info("=" * 60)

    try:
        logger.debug(f"Workspace directory: {WORKSPACE_DIR}")
        workspace = Workspace(WORKSPACE_DIR, symlink_handler=web_symlink_handler)
        logger.debug("Workspace initialized")

        memory = Memory(workspace.root_dir)
        logger.debug(f"Memory initialized, root: {workspace.root_dir}")

        tools = CombinedTools(workspace, memory)
        logger.debug("Tools initialized")

        interrupt_flag.clear()

        # NEW: Build project index for smart context
        logger.info("Building project index...")
        index_start = time.time()
        project_index = ProjectIndex(WORKSPACE_DIR)
        project_index.build()
        index_time = time.time() - index_start
        logger.info(f"Project index built: {project_index.file_count()} files in {index_time:.2f}s")

        # NEW: Initialize agent state tracker
        agent_state = AgentState()
        logger.debug("Agent state tracker initialized")

        api_key = get_api_key()
        if not api_key:
            logger.error("VENICE_API_KEY not found - chat will fail!")
        else:
            logger.info(f"API key found (length: {len(api_key)}, prefix: {api_key[:8]}...)")
            from openai import OpenAI
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.venice.ai/api/v1",
                timeout=120.0
            )
            logger.info("OpenAI client initialized with 120s timeout")

        # Initialize system prompt (will be rebuilt dynamically per request)
        memory_context = memory.get_context()
        full_prompt = SYSTEM_PROMPT
        if memory_context:
            full_prompt += f"\n\n## MEMORY FROM PREVIOUS SESSIONS:\n\n{memory_context}"
            logger.debug(f"Memory context added ({len(memory_context)} chars)")

        messages = [{"role": "system", "content": full_prompt}]
        logger.info(f"System prompt initialized ({len(full_prompt)} chars)")
        logger.info("INITIALIZATION COMPLETE")

    except Exception as e:
        logger.error(f"INITIALIZATION FAILED: {e}")
        logger.error(traceback.format_exc())

# Initialize on startup
initialize()

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files', methods=['GET'])
def list_files():
    try:
        path = request.args.get('path', '.')
        result = tools.list_files(path, recursive=False)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/files/content', methods=['GET'])
def get_file_content():
    filename = request.args.get('filename')
    if not filename:
        return jsonify({"success": False, "error": "No filename provided"}), 400
    result = tools.read_file(filename)
    return jsonify(result)

@app.route('/api/backups', methods=['GET'])
def list_backups():
    """List all available backups"""
    try:
        backup_dir = os.path.join(WORKSPACE_DIR, '.venice_backups')
        if not os.path.exists(backup_dir):
            return jsonify({"success": True, "backups": []})
        backups = []
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith('.bak'):
                full_path = os.path.join(backup_dir, f)
                stat = os.stat(full_path)
                size = stat.st_size
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size < 1024:
                        size_str = f"{size:.1f} {unit}"
                        break
                    size /= 1024
                else:
                    size_str = f"{size:.1f} TB"
                from datetime import datetime
                modified = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                backups.append({"name": f, "size": size_str, "modified": modified})
        return jsonify({"success": True, "backups": backups})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/backups/restore', methods=['POST'])
def restore_backup():
    """Restore a file from backup"""
    try:
        data = request.json
        backup_name = data.get('backup_name')
        
        if not backup_name:
            return jsonify({"success": False, "error": "No backup name provided"}), 400
        
        result = tools.restore_backup(backup_name)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/memory', methods=['GET'])
def get_memory():
    """Get session history and notes from memory"""
    try:
        if not memory:
            return jsonify({"success": False, "error": "Memory not initialized"}), 500
        
        return jsonify({
            "success": True,
            "sessions": memory.data.get("session_history", []),
            "notes": memory.data.get("project_notes", []),
            "key_files": memory.data.get("key_files", [])
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/balance', methods=['GET'])
def get_balance():
    """Get cached balance from memory"""
    try:
        if not memory:
            return jsonify({"success": False, "error": "Memory not initialized"}), 500
        
        usd = memory.data.get("last_balance_usd")
        vcu = memory.data.get("last_balance_vcu")
        
        return jsonify({
            "success": True,
            "usd_balance": f"{usd:.4f}" if usd is not None else None,
            "vcu_balance": f"{vcu:.0f}" if vcu is not None else None
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/image/edit', methods=['POST'])
def edit_image():
    try:
        data = request.json
        prompt = data.get('prompt')
        image_b64 = data.get('image') # Base64 encoded string
        model = data.get('model', 'qwen-image')  # Default to qwen-image

        if not prompt:
            return jsonify({"success": False, "error": "No prompt provided"}), 400

        api_key = get_api_key()
        if not api_key:
            return jsonify({"success": False, "error": "API Key not found"}), 500

        import httpx

        # Determine mode: Text-to-Image or Image-to-Image (Edit)
        if image_b64:
            endpoint = "https://api.venice.ai/api/v1/image/edit"
            # Payload for Edit endpoint with model and image
            payload = {
                "model": model,  # e.g., "grok-imagine-edit"
                "prompt": prompt,
                "image": image_b64  # Frontend sends raw base64 (split(',')[1])
            }
        else:
            endpoint = "https://api.venice.ai/api/v1/image/generate"
            payload = {
                "model": model,  # e.g., "grok-imagine" or "qwen-image"
                "prompt": prompt,
                "width": 1024,
                "height": 1024,
                "steps": 4,
                "hide_watermark": False,
                "return_binary": False
            }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if response.status_code != 200:
                print(f"DEBUG IMAGE ERROR: {response.text}")
                return jsonify({"success": False, "error": f"Venice API Error ({response.status_code}): {response.text}"}), response.status_code
            
            # Handle Binary Response (image/png)
            content_type = response.headers.get("Content-Type", "")
            if "image" in content_type:
                filename = f"edit_{int(time.time())}.png"
                filepath = os.path.join(IMAGES_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(response.content)
                return jsonify({"success": True, "image_url": f"/images/{filename}"})

            # Handle JSON Response
            try:
                result = response.json()
            except json.JSONDecodeError:
                return jsonify({"success": False, "error": f"Invalid response: {response.text[:200]}"}), 500
            
            # DEBUG: Print raw response if something is wrong
            if "images" not in result and "data" not in result:
                print(f"DEBUG IMAGE RESPONSE: {json.dumps(result, indent=2)}")
            
            # Handle new format: {"images": ["base64string..."]}
            if "images" in result and len(result["images"]) > 0:
                output_b64 = result["images"][0]
                
                filename = f"edit_{int(time.time())}.png"
                filepath = os.path.join(IMAGES_DIR, filename)
                
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(output_b64))
                return jsonify({"success": True, "image_url": f"/images/{filename}"})

            # Handle old/OpenAI format: {"data": [{"b64_json": "..."}]}
            elif "data" in result and len(result["data"]) > 0:
                img_data = result["data"][0]
                output_b64 = img_data.get("b64_json")
                output_url = img_data.get("url")
                
                filename = f"edit_{int(time.time())}.png"
                filepath = os.path.join(IMAGES_DIR, filename)
                
                if output_b64:
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(output_b64))
                    return jsonify({"success": True, "image_url": f"/images/{filename}"})
                elif output_url:
                    img_resp = client.get(output_url)
                    with open(filepath, "wb") as f:
                        f.write(img_resp.content)
                    return jsonify({"success": True, "image_url": f"/images/{filename}"})
            
            return jsonify({"success": False, "error": "No image data in response"}), 500

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/interrupt', methods=['POST'])
def interrupt():
    global interrupt_flag
    interrupt_flag.set()
    return jsonify({"success": True, "message": "Interrupt signal sent"})

@app.route('/api/models', methods=['GET'])
def get_models():
    return jsonify({
        "models": MODELS,
        "current": "qwen3-235b-a22b-instruct-2507"
    })

@app.route('/api/models', methods=['POST'])
def set_model():
    data = request.json
    model_id = data.get('model')
    if model_id in MODELS:
        return jsonify({"success": True, "model": MODELS[model_id]})
    return jsonify({"success": False, "error": "Invalid model"}), 400

@app.route('/api/workspace', methods=['GET', 'POST'])
def handle_workspace():
    global WORKSPACE_DIR, workspace, memory, tools
    if request.method == 'POST':
        data = request.json
        new_path = data.get('path')
        if not new_path:
            return jsonify({"success": False, "error": "No path provided"}), 400

        new_path = os.path.expanduser(os.path.expandvars(new_path))
        if not os.path.isabs(new_path):
            new_path = os.path.abspath(os.path.join(sandbox_dir, new_path))

        try:
            WORKSPACE_DIR = new_path
            save_workspace(new_path)  # Persist for restarts
            initialize()
            return jsonify({"success": True, "path": WORKSPACE_DIR})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "path": WORKSPACE_DIR})


@app.route('/api/workspaces', methods=['GET'])
def list_workspaces():
    """List available workspace directories"""
    parent_dir = os.path.dirname(sandbox_dir)  # gemini-workspace
    workspaces = []

    # Add parent directory itself
    workspaces.append({
        "path": parent_dir,
        "name": "gemini-workspace (root)",
        "is_current": WORKSPACE_DIR == parent_dir
    })

    # Add all subdirectories that look like projects
    try:
        for item in sorted(os.listdir(parent_dir)):
            item_path = os.path.join(parent_dir, item)
            if os.path.isdir(item_path) and not item.startswith('.'):
                workspaces.append({
                    "path": item_path,
                    "name": item,
                    "is_current": WORKSPACE_DIR == item_path
                })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "workspaces": workspaces, "current": WORKSPACE_DIR})

def manage_context(messages, max_bytes=600000):
    while True:
        current_size = len(json.dumps(messages))
        if current_size < max_bytes or len(messages) <= 2:
            break
        
        found = False
        # Start searching from index 1 to preserve the System Prompt at index 0
        i = 1
        while i < len(messages):
            msg = messages[i]
            
            # If we find an Assistant message with Tool Calls, we must remove the entire chain
            if msg.get('role') == 'assistant' and 'tool_calls' in msg:
                # Remove the assistant message (Request)
                messages.pop(i)
                found = True
                
                # Remove all subsequent Tool messages (Results)
                # Note: We keep popping from index 'i' because the list shifts left
                while i < len(messages) and messages[i].get('role') == 'tool':
                    messages.pop(i)
                
                break # Exit inner loop to re-evaluate size
            
            # If we find an orphan Tool message (shouldn't happen with above logic, but for safety)
            elif msg.get('role') == 'tool':
                messages.pop(i)
                found = True
                break
                
            # Standard User or Assistant message
            elif msg.get('role') != 'system':
                messages.pop(i)
                found = True
                break
            
            # If it's a system message (unlikely at i>0 but possible), skip it
            i += 1
            
        if not found: break
    return messages

@app.route('/api/chat', methods=['POST'])
def chat():
    global messages, client, interrupt_flag
    request_id = uuid.uuid4().hex[:8]
    request_start = time.time()

    logger.info("=" * 70)
    logger.info(f"[{request_id}] NEW CHAT REQUEST")
    logger.info("=" * 70)

    if not client:
        logger.error(f"[{request_id}] FAILED: Backend not initialized with API Key")
        return jsonify({"error": "Backend not initialized with API Key"}), 500

    data = request.json
    user_message = data.get('message')
    image_data = data.get('image')
    image_mime = data.get('image_mime', 'image/png')
    model_id = data.get('model', 'qwen3-235b-a22b-instruct-2507')

    logger.info(f"[{request_id}] Model: {model_id}")
    logger.info(f"[{request_id}] Message length: {len(user_message) if user_message else 0} chars")
    logger.info(f"[{request_id}] Has image: {bool(image_data)}")
    logger.debug(f"[{request_id}] User message preview: {(user_message or '')[:200]}...")

    if not user_message and not image_data:
        logger.warning(f"[{request_id}] No message or image provided")
        return jsonify({"error": "No message or image provided"}), 400

    if user_message and user_message.lower() == 'clear':
        logger.info(f"[{request_id}] Clear command received - reinitializing")
        initialize()
        return jsonify({"response": "Conversation cleared."})

    if image_data:
        logger.debug(f"[{request_id}] Building multimodal message with image ({image_mime})")
        message_content = [
            {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_data}"}},
            {"type": "text", "text": user_message or "Describe this image in detail."}
        ]
        messages.append({"role": "user", "content": message_content})
    else:
        messages.append({"role": "user", "content": user_message})

    logger.info(f"[{request_id}] Total messages in context: {len(messages)}")
    interrupt_flag.clear()

    def generate():
        event_queue = queue.Queue()
        def custom_printer(text):
            if text:
                event_queue.put({"type": "terminal", "data": text})
        UI.set_printer(custom_printer)
        stop_signal = False
        
        # Capture baseline balance for this entire operation
        baseline_usd = memory.data.get("last_balance_usd")
        baseline_vcu = memory.data.get("last_balance_vcu")

        def run_llm_and_tools():
            nonlocal stop_signal, baseline_usd, baseline_vcu
            global agent_state, project_index, context_manager
            try:
                agent_turns = 0
                consecutive_loop_warnings = 0

                # NEW: Get model-specific config
                model_config = get_model_config(model_id)
                MAX_AGENT_TURNS = model_config['max_agent_turns']
                # Default checkpoints for all models - ensure we always remind to stop
                default_checkpoints = [5, 10, 15, 20, 25, 30]
                checkpoint_turns = model_config.get('checkpoint_turns', default_checkpoints)
                needs_explicit_stop = model_config.get('needs_explicit_stop', False)

                logger.info(f"[{request_id}] Model config loaded:")
                logger.info(f"[{request_id}]   max_agent_turns: {MAX_AGENT_TURNS}")
                logger.info(f"[{request_id}]   checkpoint_turns: {checkpoint_turns}")
                logger.info(f"[{request_id}]   needs_explicit_stop: {needs_explicit_stop}")
                logger.info(f"[{request_id}]   native_function_calling: {model_config.get('native_function_calling', True)}")

                # NEW: Reset agent state for this task
                agent_state.reset()
                agent_state.task_description = user_message or "image task"
                agent_state.model_id = model_id
                agent_state.max_turns = MAX_AGENT_TURNS

                # NEW: Set up context manager with project index
                ctx_model_config = ModelConfig(
                    name=model_config['name'],
                    context_limit=model_config['context_limit'],
                    native_function_calling=model_config.get('native_function_calling', True),
                    max_agent_turns=MAX_AGENT_TURNS
                )
                context_manager = ContextManager(ctx_model_config)

                # Get project context for system prompt
                if project_index:
                    project_context = project_index.get_context_for_task(user_message or "")
                    context_manager.set_project_context(project_context)
                    logger.info(f"[{request_id}] Project context loaded: {len(project_context)} chars")

                while not stop_signal:
                    turn_start = time.time()
                    logger.info(f"[{request_id}] --- AGENT TURN {agent_turns + 1} ---")

                    event_queue.put({"type": "status", "data": "Thinking..."})
                    response_content = ""
                    global messages
                    pre_manage_count = len(messages)
                    messages = manage_context(messages)
                    logger.debug(f"[{request_id}] Context managed: {pre_manage_count} -> {len(messages)} messages")

                    try:
                        import httpx
                        api_key = get_api_key()

                        # NEW: Rebuild system prompt dynamically with project context
                        if project_index and agent_state:
                            project_context = context_manager.project_context if context_manager else None
                            files_read = agent_state.get_files_read_list()
                            dynamic_prompt = build_system_prompt(
                                model_id=model_id,
                                project_context=project_context,
                                turn_count=agent_turns,
                                max_turns=MAX_AGENT_TURNS,
                                files_already_read=files_read
                            )
                            # Update system message in messages list
                            if messages and messages[0].get('role') == 'system':
                                messages[0]['content'] = dynamic_prompt
                                logger.debug(f"[{request_id}] Dynamic system prompt updated ({len(dynamic_prompt)} chars)")

                        # Get model-specific settings
                        from venice.core import MODELS
                        model_info = MODELS.get(model_id, {})
                        max_tokens = model_info.get("max_tokens", 20000)
                        stream_timeout = model_info.get("stream_timeout", 60)
                        context_limit = model_info.get("context_limit", 128000)
                        pricing = model_info.get("pricing", "unknown")

                        logger.info(f"[{request_id}] ╔══════════════════════════════════════════════════════════")
                        logger.info(f"[{request_id}] ║ API REQUEST TO VENICE")
                        logger.info(f"[{request_id}] ╠══════════════════════════════════════════════════════════")
                        logger.info(f"[{request_id}] ║ Model:          {model_id}")
                        logger.info(f"[{request_id}] ║ Max Tokens:     {max_tokens}")
                        logger.info(f"[{request_id}] ║ Stream Timeout: {stream_timeout}s")
                        logger.info(f"[{request_id}] ║ Context Limit:  {context_limit}")
                        logger.info(f"[{request_id}] ║ Pricing:        {pricing}")
                        logger.info(f"[{request_id}] ║ Messages:       {len(messages)}")
                        logger.info(f"[{request_id}] ║ HTTP Timeout:   {stream_timeout + 60.0}s (connect), {stream_timeout}s (read)")
                        logger.info(f"[{request_id}] ╚══════════════════════════════════════════════════════════")

                        # Estimate payload size
                        payload_estimate = len(json.dumps(messages))
                        logger.debug(f"[{request_id}] Estimated payload size: {payload_estimate} bytes")

                        api_call_start = time.time()
                        logger.info(f"[{request_id}] >>> Initiating API call at {datetime.now().isoformat()}")

                        # Generous timeouts: connect=60s, read=180s (time between chunks), write=60s, pool=60s
                        # The read timeout is high because some models take a long time to produce the first token
                        with httpx.Client(timeout=httpx.Timeout(connect=60.0, read=180.0, write=60.0, pool=60.0)) as http_client:
                            with http_client.stream(
                                "POST",
                                "https://api.venice.ai/api/v1/chat/completions",
                                headers={
                                    "Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json"
                                },
                                json={
                                    "model": model_id,
                                    "messages": messages,
                                    "temperature": 0.4,
                                    "max_tokens": max_tokens,
                                    "stream": True,
                                    "tools": TOOL_SCHEMAS,
                                    "tool_choice": "auto",
                                    "venice_parameters": {"include_venice_system_prompt": False}
                                }
                                    ) as response:
                                connection_time = time.time() - api_call_start
                                logger.info(f"[{request_id}] <<< Connection established in {connection_time:.3f}s")
                                logger.info(f"[{request_id}] Response status: {response.status_code}")

                                # DEBUG: Log ALL headers received
                                logger.debug(f"[{request_id}] --- RESPONSE HEADERS ---")
                                for k, v in response.headers.items():
                                    logger.debug(f"[{request_id}]   {k}: {v}")

                                # Extract Balance Headers (Handle case sensitivity)
                                balance_usd = response.headers.get('x-venice-balance-usd') or response.headers.get('X-Venice-Balance-USD')
                                balance_vcu = response.headers.get('x-venice-balance-vcu') or response.headers.get('X-Venice-Balance-VCU')
                                
                                if balance_usd:
                                    try:
                                        curr_usd = float(balance_usd)
                                        curr_vcu = float(balance_vcu) if balance_vcu else 0.0
                                        
                                        # Initialize baseline if first run
                                        if baseline_usd is None: baseline_usd = curr_usd
                                        if baseline_vcu is None: baseline_vcu = curr_vcu
                                        
                                        # Cost = Baseline - Current
                                        cost_usd = 0.0
                                        if baseline_usd is not None:
                                            diff = float(baseline_usd) - curr_usd
                                            if diff > 0: cost_usd = diff
                                        
                                        cost_vcu = 0.0
                                        if baseline_vcu is not None and balance_vcu:
                                            cost_vcu = float(baseline_vcu) - curr_vcu
                                        
                                        # Update persistent memory for NEXT request
                                        memory.data["last_balance_vcu"] = curr_vcu
                                        memory.data["last_balance_usd"] = curr_usd
                                        memory.save()
                                        
                                        event_queue.put({
                                            "type": "metadata", 
                                            "data": {
                                                "usd_balance": f"{curr_usd:.4f}", 
                                                "usd_cost": f"{cost_usd:.4f}",
                                                "vcu_cost": f"{cost_vcu:.0f}"
                                            }
                                        })
                                    except: pass

                                # Check Content-Type for error/JSON responses
                                content_type = response.headers.get("content-type", "")
                                logger.debug(f"[{request_id}] Content-Type: {content_type}")

                                if "application/json" in content_type:
                                    # Handle non-stream response (likely an error)
                                    error_json = response.read().decode('utf-8')
                                    logger.error(f"[{request_id}] API returned JSON (not stream)!")
                                    logger.error(f"[{request_id}] API JSON response: {error_json}")
                                    try:
                                        err_data = json.loads(error_json)
                                        err_msg = err_data.get("error", "Unknown API Error")
                                        if isinstance(err_msg, dict): err_msg = err_msg.get("message", str(err_msg))
                                        logger.error(f"[{request_id}] Parsed error: {err_msg}")

                                        # Check if it's a timeout error - these can be retried
                                        if "timed-out" in str(err_msg).lower() or "timeout" in str(err_msg).lower():
                                            logger.warning(f"[{request_id}] Venice timeout detected - this is a server-side issue")
                                            event_queue.put({"type": "error", "data": f"Venice API timeout - the model is overloaded. Please try again or switch to a different model."})
                                        else:
                                            event_queue.put({"type": "error", "data": f"API Error: {err_msg}"})
                                    except:
                                        event_queue.put({"type": "error", "data": f"API returned JSON: {error_json[:200]}"})
                                    return

                                # Process SSE stream
                                logger.info(f"[{request_id}] Starting SSE stream processing...")
                                buffer = ""
                                tool_calls_buffer = {}
                                last_chunk_time = time.time()
                                stream_start_time = time.time()
                                stall_warned = False
                                chunk_count = 0
                                total_content_chars = 0
                                first_chunk_time = None

                                for chunk in response.iter_text():
                                    chunk_count += 1
                                    current_time = time.time()

                                    # Log first chunk timing (time to first token)
                                    if first_chunk_time is None:
                                        first_chunk_time = current_time
                                        ttft = first_chunk_time - api_call_start
                                        logger.info(f"[{request_id}] ⚡ FIRST CHUNK received! Time-to-first-token: {ttft:.3f}s")

                                    # Log every 50 chunks or every 5 seconds
                                    time_since_start = current_time - stream_start_time
                                    if chunk_count % 50 == 0 or (chunk_count > 1 and int(time_since_start) % 5 == 0 and int(time_since_start) > 0):
                                        logger.debug(f"[{request_id}] Chunk #{chunk_count} | Elapsed: {time_since_start:.1f}s | Content chars: {total_content_chars}")

                                    if stop_signal:
                                        logger.info(f"[{request_id}] Stop signal received, breaking stream")
                                        break

                                    # Check for stream stall
                                    time_since_last = current_time - last_chunk_time
                                    if time_since_last > stream_timeout:
                                        logger.error(f"[{request_id}] ⚠️ STREAM STALL DETECTED!")
                                        logger.error(f"[{request_id}] Time since last chunk: {time_since_last:.1f}s (threshold: {stream_timeout}s)")
                                        logger.error(f"[{request_id}] Total chunks received: {chunk_count}")
                                        logger.error(f"[{request_id}] Total content chars: {total_content_chars}")
                                        logger.error(f"[{request_id}] Total stream time: {time_since_start:.1f}s")
                                        if not stall_warned:
                                            event_queue.put({
                                                "type": "error",
                                                "data": f"Stream timeout after {stream_timeout}s - model may be stuck. Try again or switch models."
                                            })
                                            stall_warned = True
                                        break
                                    last_chunk_time = current_time
                                    buffer += chunk
                                    while "\n" in buffer:
                                        line, buffer = buffer.split("\n", 1)
                                        line = line.strip()
                                        if line.startswith("data: "):
                                            data_str = line[6:]
                                            if data_str == "[DONE]": continue
                                            try:
                                                data_obj = json.loads(data_str)
                                                if data_obj.get('choices'):
                                                    delta = data_obj['choices'][0].get('delta', {})
                                                    
                                                    if 'reasoning_content' in delta:
                                                        event_queue.put({"type": "reasoning", "data": delta['reasoning_content']})
                                                    
                                                    if 'content' in delta and delta['content']:
                                                        c = delta['content']
                                                        response_content += c
                                                        total_content_chars += len(c)
                                                        event_queue.put({"type": "content", "data": c})

                                                    if 'tool_calls' in delta:
                                                        for tc in delta['tool_calls']:
                                                            idx = tc.get('index', 0)
                                                            if idx not in tool_calls_buffer:
                                                                tool_calls_buffer[idx] = {"id": tc.get('id'), "name": "", "arguments": ""}
                                                                logger.debug(f"[{request_id}] New tool call detected at index {idx}")

                                                            if tc.get('id'): tool_calls_buffer[idx]["id"] = tc['id']
                                                            if tc.get('function'):
                                                                if tc['function'].get('name'):
                                                                    tool_calls_buffer[idx]["name"] += tc['function']['name']
                                                                if tc['function'].get('arguments'):
                                                                    tool_calls_buffer[idx]["arguments"] += tc['function']['arguments']
                                            except: continue

                                # Log stream completion
                                stream_duration = time.time() - stream_start_time
                                logger.info(f"[{request_id}] ✓ Stream completed")
                                logger.info(f"[{request_id}]   Total chunks: {chunk_count}")
                                logger.info(f"[{request_id}]   Total content chars: {total_content_chars}")
                                logger.info(f"[{request_id}]   Stream duration: {stream_duration:.2f}s")
                                logger.info(f"[{request_id}]   Tool calls detected: {len(tool_calls_buffer)}")
                                if tool_calls_buffer:
                                    for idx, tc in tool_calls_buffer.items():
                                        logger.info(f"[{request_id}]     [{idx}] {tc['name']} (args: {len(tc['arguments'])} chars)")

                    except httpx.TimeoutException as e:
                        elapsed = time.time() - api_call_start
                        logger.error(f"[{request_id}] ⛔ HTTPX TIMEOUT EXCEPTION!")
                        logger.error(f"[{request_id}] Exception type: {type(e).__name__}")
                        logger.error(f"[{request_id}] Exception message: {str(e)}")
                        logger.error(f"[{request_id}] Elapsed time: {elapsed:.2f}s")
                        logger.error(f"[{request_id}] Model: {model_id}")
                        logger.error(f"[{request_id}] Stream timeout setting: {stream_timeout}s")
                        event_queue.put({"type": "error", "data": f"Connection timeout after {elapsed:.1f}s: {str(e)}"})
                        return
                    except httpx.ConnectError as e:
                        logger.error(f"[{request_id}] ⛔ HTTPX CONNECTION ERROR!")
                        logger.error(f"[{request_id}] Exception: {str(e)}")
                        event_queue.put({"type": "error", "data": f"Connection error: {str(e)}"})
                        return
                    except Exception as e:
                        elapsed = time.time() - api_call_start
                        logger.error(f"[{request_id}] ⛔ UNEXPECTED EXCEPTION IN API CALL!")
                        logger.error(f"[{request_id}] Exception type: {type(e).__name__}")
                        logger.error(f"[{request_id}] Exception message: {str(e)}")
                        logger.error(f"[{request_id}] Elapsed time: {elapsed:.2f}s")
                        logger.error(f"[{request_id}] Traceback:\n{traceback.format_exc()}")
                        event_queue.put({"type": "error", "data": str(e)})
                        return
                    
                    if stop_signal:
                        event_queue.put({"type": "status", "data": "Interrupted."})
                        break
                    
                    # Store assistant message
                    if not response_content and not tool_calls_buffer:
                        break

                    # Convert tool calls
                    native_tool_calls = []
                    if tool_calls_buffer:
                        for idx in sorted(tool_calls_buffer.keys()):
                            tc_info = tool_calls_buffer[idx]
                            native_tool_calls.append({
                                "id": tc_info["id"],
                                "type": "function",
                                "function": {
                                    "name": tc_info["name"],
                                    "arguments": tc_info["arguments"]
                                }
                            })

                    # FALLBACK: If no native tool calls, try text-based parsing
                    # This enables models like Gemma3 that don't support native function calling
                    text_based_tool = None
                    if not native_tool_calls and response_content:
                        logger.info(f"[{request_id}] No native tool calls - trying text-based parsing...")
                        text_based_tool = parse_tool_call(response_content)
                        if text_based_tool:
                            if "error" in text_based_tool:
                                logger.warning(f"[{request_id}] Text tool parse error: {text_based_tool['error']}")
                                event_queue.put({"type": "error", "data": text_based_tool['error']})
                                text_based_tool = None
                            else:
                                tool_name = text_based_tool.get("tool") or text_based_tool.get("name")
                                logger.info(f"[{request_id}] ✓ Parsed text-based tool call: {tool_name}")

                                # NEW: Strip hallucinated output for models that make things up
                                if model_config.get('strip_hallucinated_output', False):
                                    # Find where the tool call ends and strip any "fake" results after it
                                    # Models like Gemma often write: list_files() -> [fake list of files]
                                    logger.info(f"[{request_id}] Stripping hallucinated output from response")
                                    # Keep only up to the tool call - remove any fake output
                                    import re
                                    # Match patterns like "list_files()" or "[\"list_files()\"]" and everything after
                                    patterns = [
                                        r'\[?"?' + re.escape(tool_name) + r'\([^)]*\)"?\].*',  # function call style
                                        r'\{"tool":\s*"' + re.escape(tool_name) + r'"[^}]*\}.*',  # JSON style
                                    ]
                                    for pattern in patterns:
                                        match = re.search(pattern, response_content, re.DOTALL)
                                        if match:
                                            # Keep text before the tool call, strip everything from tool call onward
                                            response_content = response_content[:match.start()].strip()
                                            logger.debug(f"[{request_id}] Stripped content after tool call, remaining: {len(response_content)} chars")
                                            break

                                # Convert to native format
                                native_tool_calls.append({
                                    "id": f"text_call_{agent_turns}",
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": json.dumps({k: v for k, v in text_based_tool.items() if k not in ["tool", "name"]})
                                    }
                                })

                    # Build assistant message - must have either content OR tool_calls
                    assistant_msg = {"role": "assistant"}

                    # If we have tool calls but no content, omit content field entirely
                    # If we have content (even with tool calls), include it
                    # This prevents "Assistant messages must have either content or tool_calls" error
                    if response_content:
                        assistant_msg["content"] = response_content
                    elif not native_tool_calls:
                        # No content and no tool calls - shouldn't happen due to check above, but be safe
                        assistant_msg["content"] = ""

                    if native_tool_calls:
                        assistant_msg["tool_calls"] = native_tool_calls

                    messages.append(assistant_msg)

                    if not native_tool_calls:
                        logger.info(f"[{request_id}] No tool calls (native or text-based) - ending turn")
                        break

                    # Execute tools
                    logger.info(f"[{request_id}] Executing {len(native_tool_calls)} tool call(s)")
                    for tc in native_tool_calls:
                        tool_name = tc["function"]["name"]
                        tool_id = tc["id"]
                        tool_args = tc["function"].get("arguments", "{}")

                        logger.info(f"[{request_id}] ┌─ TOOL: {tool_name}")
                        logger.info(f"[{request_id}] │  ID: {tool_id}")
                        logger.debug(f"[{request_id}] │  Args: {tool_args[:500]}{'...' if len(tool_args) > 500 else ''}")

                        event_queue.put({"type": "status", "data": f"Executing {tool_name}..."})
                        tool_start = time.time()

                        try:
                            class NativeTC:
                                def __init__(self, d):
                                    self.function = type('Func', (), d['function'])

                            # NEW: Check for duplicate file reads
                            if tool_name == 'read_file':
                                try:
                                    args_dict = json.loads(tool_args) if isinstance(tool_args, str) else tool_args
                                    filename = args_dict.get('filename', '')
                                    if agent_state.was_file_read(filename):
                                        logger.warning(f"[{request_id}] │  DUPLICATE READ DETECTED: {filename}")
                                        result = {
                                            "success": True,
                                            "warning": f"You already read this file. Use the information from your previous read.",
                                            "filename": filename
                                        }
                                        result_str = json.dumps(result)
                                        messages.append({
                                            "role": "tool",
                                            "tool_call_id": tc["id"],
                                            "name": tool_name,
                                            "content": result_str
                                        })
                                        continue  # Skip actual execution
                                except:
                                    pass  # If parsing fails, just execute normally

                            result = execute_tool(tools, NativeTC(tc))
                            tool_duration = time.time() - tool_start

                            # NEW: Track tool call in agent state
                            try:
                                args_dict = json.loads(tool_args) if isinstance(tool_args, str) else {}
                            except:
                                args_dict = {}
                            tool_warning = agent_state.record_tool_call(tool_name, args_dict, result)
                            if tool_warning:
                                logger.warning(f"[{request_id}] │  {tool_warning}")

                            # NEW: Track file reads
                            if tool_name == 'read_file' and isinstance(result, dict) and result.get('success'):
                                filename = args_dict.get('filename', '')
                                content = result.get('content', '')
                                agent_state.record_file_read(filename, content)

                            # NEW: Track file writes/edits
                            if tool_name == 'write_file':
                                agent_state.record_file_write(args_dict.get('filename', ''))
                            if tool_name == 'edit_file':
                                agent_state.record_file_edit(args_dict.get('filename', ''))

                            result_str = json.dumps(result)

                            # NEW: Compress large results
                            if len(result_str) > 5000:
                                original_len = len(result_str)
                                result_str = context_manager.compress_tool_result(tool_name, result)
                                logger.info(f"[{request_id}] │  Compressed result: {original_len} -> {len(result_str)} chars")

                            logger.info(f"[{request_id}] │  Duration: {tool_duration:.2f}s")
                            logger.info(f"[{request_id}] │  Result size: {len(result_str)} chars")
                            logger.debug(f"[{request_id}] │  Result: {result_str[:300]}{'...' if len(result_str) > 300 else ''}")
                            logger.info(f"[{request_id}] └─ SUCCESS")

                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "name": tool_name,
                                "content": result_str
                            })

                            if tool_name == "done":
                                logger.info(f"[{request_id}] 'done' tool called - stopping agent loop")
                                # NEW: Record done in agent state
                                summary = args_dict.get('summary', '')
                                agent_state.record_done(summary)
                                stop_signal = True
                                break
                        except Exception as e:
                            tool_duration = time.time() - tool_start
                            error_msg = f"Tool execution failed: {str(e)}"
                            logger.error(f"[{request_id}] │  Duration: {tool_duration:.2f}s")
                            logger.error(f"[{request_id}] │  Error: {str(e)}")
                            logger.error(f"[{request_id}] └─ FAILED")
                            logger.error(f"[{request_id}] Traceback:\n{traceback.format_exc()}")
                            messages.append({"role": "tool", "tool_call_id": tc["id"], "name": tool_name, "content": error_msg})
                            event_queue.put({"type": "error", "data": error_msg})

                    agent_turns += 1
                    agent_state.record_turn()
                    turn_duration = time.time() - turn_start
                    logger.info(f"[{request_id}] Turn {agent_turns} completed in {turn_duration:.2f}s")

                    # NEW: Check for loop patterns
                    loop_warning = agent_state.detect_loop_pattern()
                    if loop_warning:
                        consecutive_loop_warnings += 1
                        logger.warning(f"[{request_id}] LOOP DETECTED ({consecutive_loop_warnings}x): {loop_warning}")
                        
                        if consecutive_loop_warnings >= 2:
                            # Force break after 2 consecutive loop warnings
                            logger.warning(f"[{request_id}] FORCING BREAK after {consecutive_loop_warnings} loop warnings")
                            messages.append({"role": "user", "content": "SYSTEM: FORCED STOP. Loop detected multiple times. You MUST call done() NOW."})
                            event_queue.put({"type": "error", "data": "Loop detected - forcing completion"})
                            break
                        else:
                            messages.append({"role": "user", "content": f"SYSTEM: {loop_warning}"})
                    else:
                        consecutive_loop_warnings = 0  # Reset if no loop detected

                    # NEW: Inject checkpoint reminders at configured turns
                    if agent_turns in checkpoint_turns:
                        checkpoint_msg = get_checkpoint_message(agent_turns, model_id)
                        if checkpoint_msg:
                            logger.info(f"[{request_id}] Injecting checkpoint at turn {agent_turns}")
                            messages.append({"role": "user", "content": f"SYSTEM CHECKPOINT: {checkpoint_msg}"})

                    if agent_turns >= MAX_AGENT_TURNS:
                        logger.warning(f"[{request_id}] MAX AGENT TURNS ({MAX_AGENT_TURNS}) reached!")
                        # NEW: Force completion message
                        force_msg = f"SYSTEM: Maximum turns ({MAX_AGENT_TURNS}) reached. You must call done() NOW with your best response based on what you've learned."
                        messages.append({"role": "user", "content": force_msg})
                        # Give the model one more chance to call done()
                        if agent_turns > MAX_AGENT_TURNS + 1:
                            logger.error(f"[{request_id}] Model failed to call done() - force stopping")
                            event_queue.put({"type": "error", "data": f"Agent reached turn limit ({MAX_AGENT_TURNS}). Task incomplete."})
                            break

            except Exception as e:
                logger.error(f"[{request_id}] ⛔ FATAL ERROR IN AGENT LOOP!")
                logger.error(f"[{request_id}] Exception: {str(e)}")
                logger.error(f"[{request_id}] Traceback:\n{traceback.format_exc()}")
                event_queue.put({"type": "error", "data": str(e)})
            finally:
                total_request_time = time.time() - request_start
                logger.info(f"[{request_id}] ════════════════════════════════════════════════════════")
                logger.info(f"[{request_id}] REQUEST COMPLETE")
                logger.info(f"[{request_id}] Total time: {total_request_time:.2f}s")
                logger.info(f"[{request_id}] Agent turns: {agent_turns}")
                logger.info(f"[{request_id}] Final message count: {len(messages)}")
                logger.info(f"[{request_id}] ════════════════════════════════════════════════════════")
                event_queue.put(None)

        logic_thread = threading.Thread(target=run_llm_and_tools)
        logic_thread.start()

        last_ping = time.time()
        while True:
            try:
                if interrupt_flag.is_set(): stop_signal = True
                event = event_queue.get(timeout=0.1)
                if event is None: break
                yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
                last_ping = time.time()
            except queue.Empty:
                if time.time() - last_ping > 3:
                    yield ": ping\n\n"
                    last_ping = time.time()
                continue
            except Exception as e:
                logger.error(f"[{request_id}] SSE yield error: {str(e)}")
                yield f"event: error\ndata: {json.dumps(str(e))}\n\n"
                break
        logic_thread.join()
        yield f"event: done\ndata: {json.dumps({'history_length': len(messages)})}\n\n"
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':

    logger.info("=" * 70)

    logger.info("STARTING GONDOLA SERVER")

    logger.info(f"Port: 5040")

    logger.info(f"Log file: {LOG_FILE}")

    logger.info("=" * 70)

    print("Starting Gondola Server (Modular) on port 5040...")

    app.run(host='0.0.0.0', port=5040, debug=True, use_reloader=False)
