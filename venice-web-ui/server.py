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
import subprocess
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
from venice.api import get_api_key, get_together_api_key, execute_tool, parse_tool_call
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

def initialize(clear_messages=False):
    global workspace, memory, tools, client, messages, interrupt_flag
    global project_index, context_manager, agent_state

    logger.info("=" * 60)
    logger.info("INITIALIZING GONDOLA SERVER")
    logger.info("=" * 60)

    try:
        logger.debug(f"Workspace directory: {WORKSPACE_DIR}")
        workspace = Workspace(WORKSPACE_DIR, symlink_handler=web_symlink_handler)
        logger.debug("Workspace initialized")

        memory = Memory(workspace.root_dir, conversation_dir=sandbox_dir)
        logger.debug(f"Memory initialized, root: {workspace.root_dir}, conversation_dir: {sandbox_dir}")

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

        # Restore conversation from last session if available (unless clearing)
        if clear_messages:
            messages = [{"role": "system", "content": full_prompt}]
            logger.info("Starting fresh conversation (workspace switched)")
        else:
            saved_messages = memory.load_conversation()
            if saved_messages:
                messages = [{"role": "system", "content": full_prompt}] + saved_messages
                logger.info(f"Restored {len(saved_messages)} messages from previous session")
            else:
                messages = [{"role": "system", "content": full_prompt}]

        logger.info(f"System prompt initialized ({len(full_prompt)} chars)")
        logger.info("INITIALIZATION COMPLETE")

    except Exception as e:
        logger.error(f"INITIALIZATION FAILED: {e}")
        logger.error(traceback.format_exc())

# Initialize on startup
initialize()

import random

MISFITS_QUOTES = [
    "I have a gift.",
    "I'm gracefully tall, you're freakishly short.",
    "Save me, Barry!",
    "I appear to have shat myself.",
    "Pure mindless vandalism!",
    "Bullseye!",
    "You look like a panty sniffer.",
    "That accent is just a noise!",
    "Strange tingling sensation in my anus.",
    "I'm pretty sure this breaches the terms of my ASBO.",
    "We were so beautiful!",
    "I'm a screw-up and I plan to be a screw-up.",
    "Where do you get this stuff?",
    "It just comes to me.",
    "I'm immortal!",
    "Kind of put a downer on the whole thing.",
    "Me? I got done for eating some pick-n-mix."
]

def get_nathan_status(action=None, tool_name=None):
    if action == "think":
        return random.choice([
            "I have a gift.",
            "Thinking? It just comes to me.",
            "Where do you get this stuff?",
            "I'm immortal! (thinking...)"
        ])
    if action == "tool":
        if tool_name:
            return f"{random.choice(['Pure mindless vandalism!', 'Bullseye!', 'I have a gift.'])} (using {tool_name})"
        return random.choice([
            "Pure mindless vandalism!",
            "Bullseye!",
            "I'm pretty sure this breaches the terms of my ASBO.",
            "I have a gift (for tools)."
        ])
    if action == "connect":
        return random.choice([
            "That accent is just a noise!",
            "Save me, Barry!",
            "Connected. You like that? Oh yeah!"
        ])
    if action == "stream":
        return random.choice([
            "Strange tingling sensation in my anus (receiving data...)",
            "We were so beautiful! (streaming...)",
            "Oh yeah, oh yeah, oh yeah!"
        ])
    if action == "nudge":
        return "Your response was empty? You mentally deficient?! (nudging)"
    if action == "interrupt":
        return "Kind of put a downer on the whole thing (interrupted)."
    return random.choice(MISFITS_QUOTES)

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
        logger.info(f"Listing backups from: {backup_dir}")
        if not os.path.exists(backup_dir):
            return jsonify({"success": True, "backups": []})
        
        # Get all files with metadata first
        backup_files = []
        for f in os.listdir(backup_dir):
            if f.endswith('.bak'):
                full_path = os.path.join(backup_dir, f)
                try:
                    stat = os.stat(full_path)
                    backup_files.append({
                        "name": f,
                        "path": full_path,
                        "size_bytes": stat.st_size,
                        "mtime": stat.st_mtime
                    })
                except OSError:
                    continue

        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x['mtime'], reverse=True)

        backups = []
        for b in backup_files:
            size = b['size_bytes']
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    size_str = f"{size:.1f} {unit}"
                    break
                size /= 1024
            else:
                size_str = f"{size:.1f} TB"
            
            from datetime import datetime
            modified = datetime.fromtimestamp(b['mtime']).strftime('%Y-%m-%d %H:%M')
            backups.append({"name": b['name'], "size": size_str, "modified": modified})
            
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

@app.route('/api/interrupt', methods=['POST'])
def interrupt():
    global interrupt_flag
    interrupt_flag.set()
    return jsonify({"success": True, "message": "Interrupt signal sent"})

@app.route('/api/save-session', methods=['POST'])
def save_session():
    """Manually save the current session to memory"""
    global memory, agent_state
    try:
        data = request.json
        history = data.get('history', [])

        # Generate a simple summary from the conversation
        user_messages = [m.get('content', '') for m in history if m.get('role') == 'user' and isinstance(m.get('content'), str)]

        if user_messages:
            # Take first few user messages as summary
            summary = ' | '.join(user_messages[:3])
            if len(summary) > 200:
                summary = summary[:197] + '...'
        else:
            summary = f"Session saved at {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        # Get files touched from agent state if available
        files_touched = []
        if agent_state:
            files_touched = list(agent_state.files_written.union(agent_state.files_edited))

        # Save to memory
        memory.add_session_summary(summary, files_touched)
        logger.info(f"Manual session save: {summary[:50]}... ({len(files_touched)} files)")

        return jsonify({
            "success": True,
            "summary": summary,
            "files_count": len(files_touched)
        })
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/conversation', methods=['GET'])
def get_conversation():
    """Get current conversation for frontend restore"""
    global messages
    # Return all non-system messages
    conversation = [m for m in messages if m.get('role') != 'system']
    return jsonify({
        "success": True,
        "messages": conversation,
        "count": len(conversation)
    })

@app.route('/api/summarize', methods=['POST'])
def summarize_session():
    """Summarize the current session and return new history with summary + last 10 messages."""
    try:
        data = request.json
        history = data.get('history', [])
        keep_last_messages = data.get('keep_last_messages', 10)
        
        if not history:
            return jsonify({"success": False, "error": "No history provided"}), 400
        
        # Get the last N user messages to keep
        user_messages = [msg for msg in history if msg.get('role') == 'user']
        last_user_messages = user_messages[-keep_last_messages:] if len(user_messages) > keep_last_messages else user_messages
        
        # Create a summary of the session
        session_text = ""
        for msg in history:
            if msg.get('role') == 'user':
                session_text += f"User: {msg.get('content', '')}\n"
            elif msg.get('role') == 'assistant':
                session_text += f"Assistant: {msg.get('content', '')}\n"
        
        # Generate summary (using a simple approach for now)
        summary = f"Session Summary ({len(history)} messages total):\n"
        summary += f"- {len([m for m in history if m.get('role') == 'user'])} user messages\n"
        summary += f"- {len([m for m in history if m.get('role') == 'assistant'])} assistant responses\n"
        
        # Add some key actions if detectable
        if 'edit_file' in str(history):
            summary += "- File editing operations performed\n"
        if 'run_command' in str(history):
            summary += "- Command execution performed\n"
        if 'create' in str(history).lower():
            summary += "- File creation operations\n"
            
        summary += "\nLast actions preserved for continuity."
        
        # Build new history: summary + last user messages + their assistant responses
        new_history = [{
            "role": "system",
            "content": f"[SESSION SUMMARY] {summary}"
        }]
        
        # Add the last user messages and their corresponding assistant responses
        for msg in history:
            if msg.get('role') == 'user' and msg in last_user_messages:
                new_history.append(msg)
                # Find the assistant response that came after this user message
                user_index = history.index(msg)
                if user_index + 1 < len(history) and history[user_index + 1].get('role') == 'assistant':
                    new_history.append(history[user_index + 1])
        
        return jsonify({
            "success": True,
            "new_history": new_history,
            "summary": summary,
            "original_length": len(history),
            "new_length": len(new_history)
        })
        
    except Exception as e:
        logger.error(f"Error in summarize_session: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/models', methods=['GET'])
def get_models():
    return jsonify({
        "models": MODELS,
        "current": "moonshotai/Kimi-K2-Instruct-0905"
    })

@app.route('/api/models', methods=['POST'])
def set_model():
    data = request.json
    model_id = data.get('model')
    if model_id in MODELS:
        return jsonify({"success": True, "model": MODELS[model_id]})
    return jsonify({"success": False, "error": "Invalid model"}), 400

@app.route('/api/provider-models', methods=['GET'])
def get_provider_models():
    """Fetch available models from a provider API (Together or Venice)"""
    provider = request.args.get('provider', 'together')

    try:
        import httpx

        if provider == 'together':
            api_key = get_together_api_key()
            if not api_key:
                return jsonify({"success": False, "error": "Together API key not configured"}), 400

            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    "https://api.together.xyz/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )

                if response.status_code != 200:
                    return jsonify({"success": False, "error": f"API returned {response.status_code}"}), 500

                models_data = response.json()

                # Filter for chat models that likely support function calling
                # Together models with type "chat" generally support tool use
                filtered_models = []
                for model in models_data:
                    model_type = model.get('type', '')
                    model_id = model.get('id', '')

                    # Filter for chat/language models (these typically support function calling)
                    if model_type in ['chat', 'language', 'code']:
                        pricing = model.get('pricing', {})
                        filtered_models.append({
                            "id": model_id,
                            "name": model.get('display_name') or model_id.split('/')[-1],
                            "type": model_type,
                            "context_length": model.get('context_length', 4096),
                            "organization": model.get('organization', ''),
                            "price_in": pricing.get('input', 0),
                            "price_out": pricing.get('output', 0),
                        })

                # Sort by organization then name
                filtered_models.sort(key=lambda x: (x['organization'], x['name']))

                return jsonify({
                    "success": True,
                    "provider": "together",
                    "models": filtered_models,
                    "count": len(filtered_models)
                })

        elif provider == 'venice':
            api_key = get_api_key()
            if not api_key:
                return jsonify({"success": False, "error": "Venice API key not configured"}), 400

            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    "https://api.venice.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )

                if response.status_code != 200:
                    return jsonify({"success": False, "error": f"API returned {response.status_code}"}), 500

                data = response.json()
                models_list = data.get('data', []) if isinstance(data, dict) else data

                # Filter for text/chat models
                filtered_models = []
                for model in models_list:
                    model_id = model.get('id', '')
                    model_type = model.get('type', model.get('object', ''))

                    # Include text and chat models
                    if 'text' in str(model_type).lower() or 'chat' in str(model_type).lower() or model_type == 'model':
                        filtered_models.append({
                            "id": model_id,
                            "name": model.get('name', model_id),
                            "type": model_type,
                            "context_length": model.get('context_length', model.get('context_window', 32000)),
                            "organization": model.get('owned_by', ''),
                            "price_in": 0,
                            "price_out": 0,
                        })

                filtered_models.sort(key=lambda x: x['name'])

                return jsonify({
                    "success": True,
                    "provider": "venice",
                    "models": filtered_models,
                    "count": len(filtered_models)
                })

        else:
            return jsonify({"success": False, "error": f"Unknown provider: {provider}"}), 400

    except Exception as e:
        logger.error(f"Error fetching provider models: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

# Known models with verified function calling support (OpenAI-compatible tool calling)
# Together AI: https://docs.together.ai/docs/function-calling
# Venice AI: Uses OpenAI-compatible tool calling for most instruction-tuned models
KNOWN_FUNCTION_CALLING_MODELS = {
    # === Together AI Models ===
    "openai/gpt-oss-120b", "openai/gpt-oss-20b",
    "moonshotai/Kimi-K2-Thinking", "moonshotai/Kimi-K2-Instruct-0905",
    "zai-org/GLM-4.5-Air-FP8",
    "Qwen/Qwen3-Next-80B-A3B-Instruct", "Qwen/Qwen3-Next-80B-A3B-Thinking",
    "Qwen/Qwen3-235B-A22B-Thinking-2507", "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8",
    "Qwen/Qwen3-235B-A22B-fp8-tput",
    "deepseek-ai/DeepSeek-R1", "deepseek-ai/DeepSeek-V3",
    "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
    "meta-llama/Llama-4-Scout-17B-16E-Instruct",
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "meta-llama/Llama-3.2-3B-Instruct-Turbo",
    "Qwen/Qwen2.5-7B-Instruct-Turbo", "Qwen/Qwen2.5-72B-Instruct-Turbo",
    "mistralai/Mistral-Small-24B-Instruct-2501",
    "arcee-ai/virtuoso-large",
    "Qwen/Qwen3-VL-32B-Instruct",
    # === Venice AI Models (OpenAI-compatible tool calling) ===
    "claude-opus-45", "claude-sonnet-45", "claude-sonnet-4",
    "openai-gpt-52-codex", "openai-gpt-5-turbo", "openai-gpt-4o",
    "kimi-k2-5", "kimi-k2",
    "llama-3.3-70b", "llama-3.1-405b", "llama-3.1-70b",
    "qwen-2.5-coder", "qwen-2.5-72b", "qwen3-235b",
    "deepseek-r1", "deepseek-v3", "deepseek-coder-v2",
    "mistral-large", "mistral-small",
}

def infer_function_calling_config(model_id: str, model_type: str, context_length: int, provider: str) -> dict:
    """
    Infer function calling configuration based on model characteristics.
    Both Together AI and Venice AI use OpenAI-compatible tool calling.
    """
    # Check if it's a known function-calling model (either provider)
    is_known_fc_model = model_id in KNOWN_FUNCTION_CALLING_MODELS

    # Venice models: Most instruction-tuned models support OpenAI tool calling
    # Be more permissive for Venice since their API handles tool calling uniformly
    is_venice = provider == 'venice'

    # Infer from model type if not in known list
    # chat, code, and language types typically support function calling
    type_supports_fc = model_type in ('chat', 'code', 'language', 'text')

    # Check for common function-calling model patterns in the ID
    fc_patterns = ['instruct', 'chat', 'coder', 'turbo', 'gpt', 'claude', 'llama-3', 'llama-4',
                   'qwen', 'mistral', 'deepseek', 'kimi', 'gemma', 'phi', 'codestral']
    id_suggests_fc = any(p in model_id.lower() for p in fc_patterns)

    # Determine if model likely supports native function calling
    # Venice: More permissive - their API handles tool calling uniformly for most models
    # Together: Rely on known list + inference
    if is_venice:
        # Venice uses OpenAI-compatible tool calling broadly
        native_fc = is_known_fc_model or type_supports_fc or id_suggests_fc
    else:
        native_fc = is_known_fc_model or (type_supports_fc and id_suggests_fc)

    # Determine max agent turns based on context length
    # Larger context = can handle more turns without truncation
    if context_length >= 128000:
        max_turns = 50
    elif context_length >= 64000:
        max_turns = 40
    elif context_length >= 32000:
        max_turns = 30
    else:
        max_turns = 20

    # Determine if model likely supports parallel tool calls
    # Most modern instruction-tuned models do
    supports_parallel = native_fc and context_length >= 32000

    # Build configuration
    config = {
        "native_function_calling": native_fc,
        "max_agent_turns": max_turns,
        "needs_explicit_stop": False,
        "supports_parallel_tools": supports_parallel,
        "preferred_tool_choice": "auto",
        "tool_choice_on_nudge": "required" if native_fc else "auto",
        "force_done_at_max": True,
        # Inferred capabilities for description
        "_inferred": {
            "is_known_fc_model": is_known_fc_model,
            "type_supports_fc": type_supports_fc,
            "id_suggests_fc": id_suggests_fc,
            "provider": provider,
            "venice_inference": is_venice and not is_known_fc_model
        }
    }

    return config

@app.route('/api/models/add', methods=['POST'])
def add_model():
    """Add a new model to the runtime MODELS configuration"""
    global MODELS

    try:
        data = request.json
        model_id = data.get('model_id')

        if not model_id:
            return jsonify({"success": False, "error": "No model_id provided"}), 400

        if model_id in MODELS:
            return jsonify({"success": False, "error": f"Model '{model_id}' already exists"}), 400

        # Build model config from provided data
        provider = data.get('provider', 'venice')
        context_length = data.get('context_length', 32000)
        model_type = data.get('type', 'chat')

        # AUTO-CONFIGURE: Infer function calling settings from model characteristics
        fc_config = infer_function_calling_config(model_id, model_type, context_length, provider)
        inferred_info = fc_config.pop('_inferred', {})

        # Build description based on capabilities
        capabilities = []
        if fc_config['native_function_calling']:
            capabilities.append("Function Calling")
        if model_type == 'vision' or 'vl' in model_id.lower() or 'vision' in model_id.lower():
            capabilities.append("Vision")
        capabilities.extend(["Reasoning", "Code"])
        if context_length >= 100000:
            capabilities.append("Long Context")
        description = " · ".join(capabilities)

        new_model = {
            "name": data.get('name', model_id.split('/')[-1]),
            "type": model_type,
            "provider": provider,
            "description": description,
            "strength": data.get('strength', data.get('organization', 'Custom Model')),
            "rank": data.get('rank', 3),
            "context_limit": context_length,
            "price_in": data.get('price_in', 0),
            "price_out": data.get('price_out', 0),
            "max_tokens": min(data.get('max_tokens', 8000), 32000),
            "stream_timeout": 180,
            # Merge inferred function calling config
            **fc_config
        }

        # Add to MODELS dict
        MODELS[model_id] = new_model

        # Log what was inferred
        logger.info(f"Added new model: {model_id} (provider: {provider})")
        logger.info(f"  Auto-configured: native_fc={fc_config['native_function_calling']}, "
                   f"max_turns={fc_config['max_agent_turns']}, parallel={fc_config['supports_parallel_tools']}")
        if inferred_info.get('is_known_fc_model'):
            logger.info(f"  (Known function-calling model from Together AI docs)")

        # Determine inference source for UI feedback
        if inferred_info.get('is_known_fc_model'):
            inferred_from = "verified (known model)"
        elif inferred_info.get('venice_inference'):
            inferred_from = "Venice OpenAI-compatible"
        else:
            inferred_from = "model type/name patterns"

        return jsonify({
            "success": True,
            "model_id": model_id,
            "model": new_model,
            "auto_configured": {
                "native_function_calling": fc_config['native_function_calling'],
                "max_agent_turns": fc_config['max_agent_turns'],
                "supports_parallel_tools": fc_config['supports_parallel_tools'],
                "is_known_fc_model": inferred_info.get('is_known_fc_model', False),
                "inferred_from": inferred_from
            }
        })

    except Exception as e:
        logger.error(f"Error adding model: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/models/remove', methods=['POST'])
def remove_model():
    """Remove a model from the runtime MODELS configuration"""
    global MODELS

    try:
        data = request.json
        model_id = data.get('model_id')

        if not model_id:
            return jsonify({"success": False, "error": "No model_id provided"}), 400

        if model_id not in MODELS:
            return jsonify({"success": False, "error": f"Model '{model_id}' not found"}), 404

        del MODELS[model_id]
        logger.info(f"Removed model: {model_id}")

        return jsonify({"success": True, "model_id": model_id})

    except Exception as e:
        logger.error(f"Error removing model: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

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
            initialize(clear_messages=True)  # Clear conversation when switching workspaces
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

def manage_context(messages, max_bytes=200000):
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
    model_id = data.get('model', 'moonshotai/Kimi-K2-Instruct-0905')
    planning_mode = data.get('planning_mode', False)

    logger.info(f"[{request_id}] Model: {model_id}")
    logger.info(f"[{request_id}] Planning Mode: {planning_mode}")
    logger.info(f"[{request_id}] Message length: {len(user_message) if user_message else 0} chars")
    logger.info(f"[{request_id}] Has image: {bool(image_data)}")
    logger.debug(f"[{request_id}] User message preview: {(user_message or '')[:200]}...")

    if not user_message and not image_data:
        logger.warning(f"[{request_id}] No message or image provided")
        return jsonify({"error": "No message or image provided"}), 400

    if user_message and user_message.lower() == 'clear':
        logger.info(f"[{request_id}] Clear command received - reinitializing")
        memory.clear_conversation()  # Clear saved conversation
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
                default_checkpoints = [10, 20, 30, 40, 45, 48]
                checkpoint_turns = model_config.get('checkpoint_turns', default_checkpoints)
                needs_explicit_stop = model_config.get('needs_explicit_stop', False)

                # Function calling optimization settings
                preferred_tool_choice = model_config.get('preferred_tool_choice', 'auto')
                tool_choice_on_nudge = model_config.get('tool_choice_on_nudge', 'required')
                force_done_at_max = model_config.get('force_done_at_max', True)
                supports_parallel_tools = model_config.get('supports_parallel_tools', True)

                logger.info(f"[{request_id}] Model config loaded:")
                logger.info(f"[{request_id}]   max_agent_turns: {MAX_AGENT_TURNS}")
                logger.info(f"[{request_id}]   checkpoint_turns: {checkpoint_turns}")
                logger.info(f"[{request_id}]   needs_explicit_stop: {needs_explicit_stop}")
                logger.info(f"[{request_id}]   native_function_calling: {model_config.get('native_function_calling', True)}")
                logger.info(f"[{request_id}]   preferred_tool_choice: {preferred_tool_choice}")
                logger.info(f"[{request_id}]   tool_choice_on_nudge: {tool_choice_on_nudge}")
                logger.info(f"[{request_id}]   force_done_at_max: {force_done_at_max}")

                # NEW: Reset agent state for this task
                agent_state.reset()
                agent_state.task_description = user_message or "image task"
                agent_state.model_id = model_id
                agent_state.max_turns = MAX_AGENT_TURNS

                # Track consecutive empty responses for nudge injection
                consecutive_empty_responses = 0
                MAX_EMPTY_RESPONSES = 3  # Give up after 3 nudges

                # OPTIMIZATION: Dynamic tool_choice control
                tool_choice_override = None  # None means use default "auto"

                # OPTIMIZATION: Tool result cache (for read_file within same task)
                tool_result_cache = {}  # key: (tool_name, args_hash) -> result

                # OPTIMIZATION: Retry configuration for transient errors
                MAX_API_RETRIES = 3
                RETRY_BASE_DELAY = 1.0  # seconds
                RETRYABLE_STATUS_CODES = {429, 502, 503, 504}  # Rate limit, bad gateway, service unavailable, timeout

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

                    event_queue.put({"type": "status", "data": get_nathan_status("think")})
                    response_content = ""
                    global messages
                    pre_manage_count = len(messages)
                    messages = manage_context(messages)
                    logger.debug(f"[{request_id}] Context managed: {pre_manage_count} -> {len(messages)} messages")

                    # Initialize timing before try block so exception handlers can use it
                    api_call_start = time.time()

                    try:
                        import httpx

                        # Get model-specific settings FIRST (needed for provider routing)
                        from venice.core import MODELS
                        model_info = MODELS.get(model_id, {})
                        max_tokens = model_info.get("max_tokens", 20000)
                        stream_timeout = model_info.get("stream_timeout", 180)
                        context_limit = model_info.get("context_limit", 128000)
                        pricing = model_info.get("pricing", "unknown")

                        # Determine Provider and Endpoint
                        # Use explicit provider field from model config
                        model_provider = model_info.get("provider", "venice")  # Default to Venice
                        is_together = (model_provider == "together")

                        if is_together:
                            api_key = get_together_api_key()
                            api_base = "https://api.together.xyz/v1/chat/completions"
                            if not api_key:
                                logger.error(f"[{request_id}] Together API Key missing for {model_id}")
                                event_queue.put({"type": "error", "data": "Together API Key not configured."})
                                break
                        else:  # venice or default
                            api_key = get_api_key()
                            api_base = "https://api.venice.ai/api/v1/chat/completions"
                            if not api_key:
                                logger.error(f"[{request_id}] Venice API Key missing")
                                event_queue.put({"type": "error", "data": "Venice API Key not configured."})
                                break

                        # NEW: Rebuild system prompt dynamically with project context
                        if project_index and agent_state:
                            # Only include full project context for the first few turns to save tokens
                            include_full_context = (agent_turns < 3)
                            project_context = context_manager.project_context if (context_manager and include_full_context) else None
                            
                            files_read = agent_state.get_files_read_list()
                            memory_context = memory.get_context() if memory else None

                            dynamic_prompt = build_system_prompt(
                                model_id=model_id,
                                project_context=project_context,
                                turn_count=agent_turns,
                                max_turns=MAX_AGENT_TURNS,
                                files_already_read=files_read,
                                planning_mode=planning_mode,
                                memory_context=memory_context
                            )
                            # Update system message in messages list
                            if messages and messages[0].get('role') == 'system':
                                messages[0]['content'] = dynamic_prompt
                                logger.debug(f"[{request_id}] Dynamic system prompt updated ({len(dynamic_prompt)} chars, context included: {include_full_context})")

                        logger.info(f"[{request_id}] ╔══════════════════════════════════════════════════════════")
                        logger.info(f"[{request_id}] ║ API REQUEST TO {model_provider.upper()}")
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

                        # Update timing right before actual API call for accuracy
                        api_call_start = time.time()
                        logger.info(f"[{request_id}] >>> Initiating API call at {datetime.now().isoformat()}")
                        event_queue.put({"type": "status", "data": get_nathan_status("connect")})

                        # Generous timeouts: connect=60s, read=180s (time between chunks), write=60s, pool=60s
                        # The read timeout is high because some models take a long time to produce the first token

                        # OPTIMIZATION: Dynamic tool_choice based on agent state and model config
                        effective_tool_choice = tool_choice_override or preferred_tool_choice

                        # Force done() when at max turns (if model config allows)
                        if force_done_at_max and agent_turns >= MAX_AGENT_TURNS - 1:
                            effective_tool_choice = {
                                "type": "function",
                                "function": {"name": "done"}
                            }
                            logger.info(f"[{request_id}] Forcing tool_choice to 'done' at turn {agent_turns + 1}")

                        # Construct payload
                        api_payload = {
                            "model": model_id,
                            "messages": messages,
                            "temperature": 0.4,
                            "max_tokens": max_tokens,
                            "stream": True,
                            "tools": TOOL_SCHEMAS,
                            "tool_choice": effective_tool_choice
                        }
                        # Only add venice_parameters for Venice
                        if not is_together:
                            api_payload["venice_parameters"] = {"include_venice_system_prompt": True}

                        logger.debug(f"[{request_id}] tool_choice: {effective_tool_choice}")

                        # OPTIMIZATION: Retry loop with exponential backoff
                        api_attempt = 0
                        api_success = False
                        last_api_error = None

                        while api_attempt < MAX_API_RETRIES and not api_success:
                            api_attempt += 1
                            if api_attempt > 1:
                                retry_delay = RETRY_BASE_DELAY * (2 ** (api_attempt - 2))  # 1s, 2s, 4s...
                                logger.warning(f"[{request_id}] API retry {api_attempt}/{MAX_API_RETRIES} after {retry_delay:.1f}s delay")
                                event_queue.put({"type": "status", "data": f"Retrying ({api_attempt}/{MAX_API_RETRIES})..."})
                                time.sleep(retry_delay)
                                api_call_start = time.time()  # Reset timing for retry

                            try:
                                with httpx.Client(timeout=httpx.Timeout(connect=60.0, read=180.0, write=60.0, pool=60.0)) as http_client:
                                    with http_client.stream(
                                "POST",
                                api_base,
                                headers={
                                    "Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json"
                                },
                                json=api_payload
                                    ) as response:
                                connection_time = time.time() - api_call_start
                                logger.info(f"[{request_id}] <<< Connection established in {connection_time:.3f}s")
                                event_queue.put({"type": "status", "data": get_nathan_status("connect")})
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
                                        event_queue.put({"type": "status", "data": get_nathan_status("stream")})

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

                                # OPTIMIZATION: Mark API call as successful to exit retry loop
                                api_success = True

                            except httpx.TimeoutException as e:
                                elapsed = time.time() - api_call_start
                                last_api_error = f"Connection timeout after {elapsed:.1f}s: {str(e)}"
                                logger.warning(f"[{request_id}] ⚠️ HTTPX TIMEOUT (attempt {api_attempt}/{MAX_API_RETRIES})")
                                logger.warning(f"[{request_id}] Exception: {str(e)}")
                                # Timeouts are retryable
                                if api_attempt >= MAX_API_RETRIES:
                                    logger.error(f"[{request_id}] ⛔ Max retries exceeded for timeout")
                                    event_queue.put({"type": "error", "data": last_api_error})
                                    return

                            except httpx.ConnectError as e:
                                last_api_error = f"Connection error: {str(e)}"
                                logger.warning(f"[{request_id}] ⚠️ HTTPX CONNECTION ERROR (attempt {api_attempt}/{MAX_API_RETRIES})")
                                logger.warning(f"[{request_id}] Exception: {str(e)}")
                                # Connection errors are retryable
                                if api_attempt >= MAX_API_RETRIES:
                                    logger.error(f"[{request_id}] ⛔ Max retries exceeded for connection error")
                                    event_queue.put({"type": "error", "data": last_api_error})
                                    return

                            except httpx.HTTPStatusError as e:
                                status_code = e.response.status_code
                                last_api_error = f"HTTP {status_code}: {str(e)}"
                                logger.warning(f"[{request_id}] ⚠️ HTTP STATUS ERROR {status_code} (attempt {api_attempt}/{MAX_API_RETRIES})")

                                if status_code in RETRYABLE_STATUS_CODES:
                                    # Retryable status codes (rate limit, server errors)
                                    if api_attempt >= MAX_API_RETRIES:
                                        logger.error(f"[{request_id}] ⛔ Max retries exceeded for HTTP {status_code}")
                                        event_queue.put({"type": "error", "data": last_api_error})
                                        return
                                else:
                                    # Non-retryable status codes (4xx client errors except 429)
                                    logger.error(f"[{request_id}] ⛔ Non-retryable HTTP error: {status_code}")
                                    event_queue.put({"type": "error", "data": last_api_error})
                                    return

                            except Exception as e:
                                elapsed = time.time() - api_call_start
                                last_api_error = str(e)
                                logger.error(f"[{request_id}] ⛔ UNEXPECTED EXCEPTION IN API CALL!")
                                logger.error(f"[{request_id}] Exception type: {type(e).__name__}")
                                logger.error(f"[{request_id}] Exception message: {str(e)}")
                                logger.error(f"[{request_id}] Elapsed time: {elapsed:.2f}s")
                                logger.error(f"[{request_id}] Traceback:\n{traceback.format_exc()}")
                                event_queue.put({"type": "error", "data": str(e)})
                                return

                        # End of retry loop - check if we succeeded
                        if not api_success:
                            logger.error(f"[{request_id}] ⛔ API call failed after {MAX_API_RETRIES} attempts")
                            event_queue.put({"type": "error", "data": f"API call failed after {MAX_API_RETRIES} retries: {last_api_error}"})
                            return
                    
                    if stop_signal:
                        event_queue.put({"type": "status", "data": get_nathan_status("interrupt")})
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
                        # Check if this is an empty response (no content AND no tool calls)
                        is_empty_response = not response_content or len(response_content.strip()) == 0

                        if is_empty_response and consecutive_empty_responses < MAX_EMPTY_RESPONSES:
                            consecutive_empty_responses += 1
                            logger.warning(f"[{request_id}] EMPTY RESPONSE detected ({consecutive_empty_responses}/{MAX_EMPTY_RESPONSES}) - injecting continuation nudge")

                            # Remove the empty assistant message we just added
                            if messages and messages[-1].get("role") == "assistant":
                                messages.pop()

                            # Inject a nudge to continue working
                            nudge_msg = "SYSTEM: Your response was empty. The task is not complete. Continue working - use tools to make progress, then call done() when finished."
                            messages.append({"role": "user", "content": nudge_msg})
                            event_queue.put({"type": "status", "data": get_nathan_status("nudge")})

                            # OPTIMIZATION: Force tool use after nudge (using model-specific config)
                            tool_choice_override = tool_choice_on_nudge
                            logger.info(f"[{request_id}] Setting tool_choice to '{tool_choice_on_nudge}' after nudge")

                            # Continue the loop instead of breaking
                            agent_turns += 1
                            continue
                        else:
                            if consecutive_empty_responses >= MAX_EMPTY_RESPONSES:
                                logger.error(f"[{request_id}] Too many empty responses ({consecutive_empty_responses}) - giving up")
                                event_queue.put({"type": "error", "data": "Model stopped responding. Task may be incomplete."})
                            else:
                                logger.info(f"[{request_id}] No tool calls but has content - ending turn normally")
                            break

                    # Reset empty response counter and tool_choice override on successful tool call response
                    consecutive_empty_responses = 0
                    tool_choice_override = None  # Reset to auto after successful response

                    # Execute tools
                    logger.info(f"[{request_id}] Executing {len(native_tool_calls)} tool call(s)")
                    for tc in native_tool_calls:
                        tool_name = tc["function"]["name"]
                        tool_id = tc["id"]
                        tool_args = tc["function"].get("arguments", "{}")

                        logger.info(f"[{request_id}] ┌─ TOOL: {tool_name}")
                        logger.info(f"[{request_id}] │  ID: {tool_id}")
                        logger.debug(f"[{request_id}] │  Args: {tool_args[:500]}{'...' if len(tool_args) > 500 else ''}")

                        event_queue.put({"type": "status", "data": get_nathan_status("tool", tool_name)})
                        tool_start = time.time()

                        try:
                            # HARD LOCK: Planning Mode enforcement
                            if planning_mode and tool_name in ['write_file', 'edit_file', 'append_to_file', 'delete_lines', 'replace_lines', 'insert_at_line']:
                                logger.warning(f"[{request_id}] │  BLOCKED: {tool_name} called in Planning Mode")
                                result = {
                                    "success": False,
                                    "error": f"TOOL BLOCKED: You are in PLANNING MODE. You are forbidden from using {tool_name}. Present your plan to the user using the information you have gathered."
                                }
                                result_str = json.dumps(result)
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_id,
                                    "name": tool_name,
                                    "content": result_str
                                })
                                event_queue.put({
                                    "type": "tool_done",
                                    "data": {
                                        "tool": tool_name,
                                        "success": False,
                                        "error": "Blocked by Planning Mode governor."
                                    }
                                })
                                continue

                            class NativeTC:
                                def __init__(self, d):
                                    self.function = type('Func', (), d['function'])

                            # OPTIMIZATION: Check tool result cache for read_file
                            if tool_name == 'read_file':
                                try:
                                    args_dict = json.loads(tool_args) if isinstance(tool_args, str) else tool_args
                                    filename = args_dict.get('filename', '')
                                    start_line = args_dict.get('start_line')
                                    end_line = args_dict.get('end_line')
                                    cache_key = f"read_file:{filename}:{start_line}:{end_line}"

                                    if cache_key in tool_result_cache:
                                        # Return cached result
                                        cached_result = tool_result_cache[cache_key]
                                        logger.info(f"[{request_id}] │  CACHE HIT: {filename}")
                                        result_str = json.dumps({
                                            "success": True,
                                            "cached": True,
                                            "filename": filename,
                                            "content": cached_result.get('content', ''),
                                            "lines": cached_result.get('lines', 0),
                                            "note": "Returned from cache - file was already read this session"
                                        })
                                        messages.append({
                                            "role": "tool",
                                            "tool_call_id": tc["id"],
                                            "name": tool_name,
                                            "content": result_str
                                        })
                                        event_queue.put({
                                            "type": "tool_done",
                                            "data": {"tool": tool_name, "success": True, "cached": True}
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

                            # NEW: Track file reads and populate cache
                            if tool_name == 'read_file' and isinstance(result, dict) and result.get('success'):
                                filename = args_dict.get('filename', '')
                                content = result.get('content', '')
                                agent_state.record_file_read(filename, content)
                                # OPTIMIZATION: Cache the result for future reads
                                start_line = args_dict.get('start_line')
                                end_line = args_dict.get('end_line')
                                cache_key = f"read_file:{filename}:{start_line}:{end_line}"
                                tool_result_cache[cache_key] = {
                                    'content': content,
                                    'lines': result.get('lines', 0)
                                }
                                logger.debug(f"[{request_id}] │  Cached read_file result: {cache_key}")

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

                            # Emit tool_done event for frontend UI
                            event_queue.put({
                                "type": "tool_done",
                                "data": {
                                    "tool": tool_name,
                                    "success": True
                                }
                            })

                            if tool_name == "done":
                                logger.info(f"[{request_id}] 'done' tool called - stopping agent loop")
                                # NEW: Record done in agent state
                                summary = args_dict.get('summary', '')
                                agent_state.record_done(summary)
                                # NEW: Save session to persistent memory
                                files_touched = list(agent_state.files_written.union(agent_state.files_edited))
                                memory.add_session_summary(summary, files_touched)
                                logger.info(f"[{request_id}] Session saved to memory ({len(files_touched)} files touched)")
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
                            # Emit tool_done event with error for frontend UI
                            event_queue.put({
                                "type": "tool_done",
                                "data": {
                                    "tool": tool_name,
                                    "success": False,
                                    "error": str(e)
                                }
                            })

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
        # Auto-save conversation for crash recovery
        memory.save_conversation(messages)
        yield f"event: done\ndata: {json.dumps({'history_length': len(messages)})}\n\n"
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/git/status', methods=['GET'])
def git_status():
    """Get git repository status"""
    try:
        if not tools:
            return jsonify({"success": False, "error": "Tools not initialized"}), 500
        result = tools.git_status()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Git status error: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/git/log', methods=['GET'])
def git_log():
    """Get git log"""
    try:
        n = int(request.args.get('n', 20))
        if not tools:
            return jsonify({"success": False, "error": "Tools not initialized"}), 500
        result = tools.git_log(n=n)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Git log error: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/git/branches', methods=['GET'])
def git_branches():
    """List git branches"""
    try:
        if not tools:
            return jsonify({"success": False, "error": "Tools not initialized"}), 500
        result = tools.git_branch()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Git branches error: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/git/checkout', methods=['POST'])
def git_checkout():
    """Checkout a branch or commit"""
    try:
        data = request.json
        target = data.get('target')
        if not target:
            return jsonify({"success": False, "error": "No target provided"}), 400
        
        # Use subprocess directly for checkout as it's not in git_ops.py yet
        result = subprocess.run(
            ['git', 'checkout', target],
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return jsonify({"success": True, "output": result.stdout})
        else:
            return jsonify({"success": False, "error": result.stderr})
    except Exception as e:
        logger.error(f"Git checkout error: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/git/graph', methods=['GET'])
def git_graph():
    """Get git graph output"""
    try:
        result = subprocess.run(
            ['git', 'log', '--graph', '--oneline', '--all', '-n', '30', '--color=never'],
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return jsonify({"success": True, "output": result.stdout})
        else:
            return jsonify({"success": False, "error": result.stderr})
    except Exception as e:
        logger.error(f"Git graph error: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/forget', methods=['POST'])
def forget():
    """Clear all memory and conversation history"""
    try:
        logger.info("Forget command received - clearing all memory and history")
        if memory:
            memory.clear_conversation()
            memory.clear_notes()
            # Reset memory data to default
            memory.data = memory._default()
            memory.save()
        
        # Global messages list reset
        global messages
        initialize(clear_messages=True)
        
        return jsonify({"success": True, "message": "Memory and conversation cleared."})
    except Exception as e:
        logger.error(f"Forget error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':

    logger.info("=" * 70)

    logger.info("STARTING GONDOLA SERVER")

    logger.info(f"Port: 5050")

    logger.info(f"Log file: {LOG_FILE}")

    logger.info("=" * 70)

    print("Starting Gondola Server (Modular) on port 5050...")

    app.run(host='0.0.0.0', port=5050, debug=True, use_reloader=False)


