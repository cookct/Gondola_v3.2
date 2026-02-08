#!/usr/bin/env python3
"""
Venice CLI Entry Point
"""

import os
import sys

# Force standalone mode: Prioritize this project's modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
import re
import shutil
import subprocess
import difflib
import ast
import hashlib
import threading
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from openai import OpenAI
import httpx

# NEW: Import persistence manager
try:
    from venice.persistence import PersistenceManager
except ImportError:
    PersistenceManager = None

# ============================================================================
# COMPREHENSIVE DEBUG LOGGING CONFIGURATION FOR CLI
# ============================================================================
LOG_DIR = os.path.join(project_root, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f'gondola_cli_debug_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# Create logger
logger = logging.getLogger('gondola.cli')
logger.setLevel(logging.DEBUG)

# File handler - captures EVERYTHING
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s.%(msecs)03d | %(levelname)-8s | %(funcName)-25s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)

# Console handler - show INFO and above
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    '%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("=" * 80)
logger.info("GONDOLA CLI DEBUG LOGGING INITIALIZED")
logger.info(f"Log file: {LOG_FILE}")
logger.info("=" * 80)

# Import configuration, UI, Workspace, and Memory
from venice.config import DEFAULT_MODEL, DEFAULT_WORKSPACE, SCRIPT_DIR
from venice.core import Colors, UI, MODELS, get_model_config
from venice.workspace import Workspace
from venice.memory import Memory
from venice.tools import CombinedTools as Tools
from venice.prompts.system import SYSTEM_PROMPT, build_system_prompt, get_checkpoint_message
from venice.api import get_api_key, parse_tool_call, execute_tool, _clean_and_parse_json
from venice.tools.schema import TOOL_SCHEMAS

# NEW: Import smart context management modules
from venice.project_index import ProjectIndex
from venice.context_manager import ContextManager, ModelConfig
from venice.agent_state import AgentState
from venice.persistence import PersistenceManager


def main():
 import argparse

 parser = argparse.ArgumentParser(description="Venice CLI v2 - Code Assistant")
 parser.add_argument("-w", "--workspace", default=DEFAULT_WORKSPACE, help="Workspace directory")
 parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help="Model to use")
 parser.add_argument("--forget", action="store_true", help="Clear project notes and session history")
 args = parser.parse_args()

 try:
  workspace = Workspace(args.workspace)
 except PermissionError as e:
  UI.error(str(e))
  sys.exit(1)

 # Initialize memory
 memory = Memory(workspace.root_dir)

 if args.forget:
  memory.clear_notes()
  memory.data["session_history"] = []
  memory.save()
  UI.success("Memory cleared (project notes and session history).")
  sys.exit(0)

 # Get API key
 memory = Memory(workspace.root_dir)
  
 # NEW: Build project index for smart context
 UI.info("Building project index...")
 project_index = ProjectIndex(workspace.root_dir)
 project_index.build()
 UI.info(f"Indexed {project_index.file_count()} files")
 
 # Trigger Ctags indexing in background (Phase 3)
 try:
    subprocess.Popen([
        "ctags", "-R", "--fields=+l", "--languages=Python,JavaScript", 
        "-f", os.path.join(workspace.root_dir, ".gondola_tags")
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
 except (OSError, subprocess.SubprocessError):
    pass  # ctags not installed or failed, that's ok

 # NEW: Initialize agent state tracker
 agent_state = AgentState()

 tools = Tools(workspace, memory, project_index, agent_state=agent_state)
 
 # Initialize persistence if available
 persistence = PersistenceManager(workspace.root_dir) if PersistenceManager else None

 # Build system prompt with memory context
 memory_context = memory.get_context()
 if memory_context:
  full_prompt = SYSTEM_PROMPT + f"\n\n## MEMORY FROM PREVIOUS SESSIONS:\n\n{memory_context}"
 else:
  full_prompt = SYSTEM_PROMPT

 # Inject Resurrection Point if available
 if persistence:
     last_checkpoint = persistence.get_last_checkpoint()
     if last_checkpoint and last_checkpoint.get("thought"):
         # Step 7: Divergence Detection
         try:
             # Check how many files changed between shadow branch and current workspace
             # We use the marker file to find the base tree of the shadow branch
             result = subprocess.run(
                 ["git", "diff", "--name-only", "HEAD", persistence.branch_name],
                 capture_output=True, text=True, cwd=workspace.root_dir
             )
             changed_files = [f for f in result.stdout.splitlines() if f]
             
             if len(changed_files) > 5:
                 UI.warning(f"RESURRECTION WARNING: Workspace diverged significantly ({len(changed_files)} files changed).")
                 UI.step_detail("The codebase has changed since your last session. Resurrecting state with caution.")
                 
             resurrection_msg = f"\n\n## RESURRECTION POINT:\nYou were interrupted. Your last state was:\nThought: {last_checkpoint['thought']}\nPending Task: {last_checkpoint['task']}\nContinue where you left off."
             full_prompt += resurrection_msg
             UI.info("Resurrected cognitive state from shadow branch")
             if changed_files:
                 UI.info(f"Divergence detected ({len(changed_files)} files changed)")
         except Exception as e:
             # Fallback if git diff fails
             resurrection_msg = f"\n\n## RESURRECTION POINT:\nYou were interrupted. Your last state was:\nThought: {last_checkpoint['thought']}\nPending Task: {last_checkpoint['task']}\nContinue where you left off."
             full_prompt += resurrection_msg
             UI.info("Resurrected cognitive state (divergence check failed)")

 # Initialize current model
 current_model = args.model if args.model in MODELS else DEFAULT_MODEL

 # Welcome
 UI.header("Venice CLI v2.3", Colors.CYAN)
 print(f"{Colors.GREY}Workspace: {workspace.root_dir}{Colors.RESET}")
 print(f"{Colors.GREY}Model: {MODELS[current_model]['name']} ({current_model}){Colors.RESET}")
 if memory_context:
  print(f"{Colors.GREEN}Memory loaded from previous sessions{Colors.RESET}")
 print(f"{Colors.GREY}Type /help for commands, 'exit' to quit{Colors.RESET}")

 messages = [{"role": "system", "content": full_prompt}]
 session_summaries = [] # Track what was done this session
 recent_edits = [] # Track recent edits to detect loops

 while True:
  try:
   user_input = UI.prompt()

   if not user_input.strip():
    continue

   if user_input.lower() in ('exit', 'quit'):
    # Save session summary before exit
    if session_summaries or tools.files_touched:
     summary = "; ".join(session_summaries) if session_summaries else "Session with file edits"
     memory.add_session_summary(summary, list(tools.files_touched))
    UI.info(f"Session saved to memory ({len(tools.files_touched)} files touched)")
    UI.info("Goodbye!")
    break

   if user_input.lower() == 'clear':
    messages = [{"role": "system", "content": full_prompt}]
    UI.info("Conversation cleared")
    continue

   if user_input.lower() in ('/model', '/models'):
    new_model = UI.model_selector(MODELS, current_model)
    if new_model:
     current_model = new_model
     model_info = MODELS[current_model]
     UI.info(f"Now using: {model_info['name']} ({model_info['type']})")
    continue

   if user_input.lower().startswith('/image '):
    # Image analysis with vision model
    image_path = user_input[7:].strip()
    if not os.path.exists(image_path):
     # Try relative to workspace
     image_path = os.path.join(workspace.root_dir, image_path)

    if not os.path.exists(image_path):
     UI.error(f"Image not found: {user_input[7:].strip()}")
     continue

    # Switch to vision model if not already
    if MODELS[current_model]['type'] != 'vision':
     old_model = current_model
     current_model = "claude-opus-45"
     UI.info(f"Switched to {MODELS[current_model]['name']} for image analysis")

    # Read and encode image
    import base64
    with open(image_path, 'rb') as f:
     image_data = base64.b64encode(f.read()).decode('utf-8')

    # Determine mime type
    ext = os.path.splitext(image_path)[1].lower()
    mime_types = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}
    mime_type = mime_types.get(ext, 'image/png')

    UI.info(f"Analyzing: {os.path.basename(image_path)}")

    # Add image message
    messages.append({
     "role": "user",
     "content": [
      {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}},
      {"type": "text", "text": "Describe this image in detail. What do you see?"}
     ]
    })
    # Continue to the API call below
    user_input = None # Skip normal message append

   if user_input and user_input.lower() == '/help':
    print(f"\n{Colors.CYAN}Commands:{Colors.RESET}")
    print(f" /model - Switch between models")
    print(f" /image PATH - Analyze an image (auto-switches to vision model)")
    print(f" /help - Show this help")
    print(f" clear - Clear conversation")
    print(f" exit - Exit and save session")
    print(f"\n{Colors.CYAN}Current model:{Colors.RESET} {MODELS[current_model]['name']}")
    continue

   if user_input: # Skip if already added (e.g., /image command)
    messages.append({"role": "user", "content": user_input})

   # Agent loop with protection
   agent_turns = 0
   consecutive_edit_failures = 0
   consecutive_loop_warnings = 0
   session_id = uuid.uuid4().hex[:8]
   logger.info(f"[{session_id}] Starting new CLI session")

   # NEW: Get model-specific configuration
   model_cfg = get_model_config(current_model)
   MAX_AGENT_TURNS = model_cfg['max_agent_turns']
   # Default checkpoints for all models - ensure we always remind to stop
   default_checkpoints = [5, 10, 15, 20, 25, 30]
   checkpoint_turns = model_cfg.get('checkpoint_turns', default_checkpoints)
   needs_explicit_stop = model_cfg.get('needs_explicit_stop', False)

   logger.info(f"[{session_id}] Model config: max_turns={MAX_AGENT_TURNS}, checkpoints={checkpoint_turns}")

   # NEW: Reset agent state for this task
   agent_state.reset()
   agent_state.task_description = user_input or ""
   agent_state.model_id = current_model
   agent_state.max_turns = MAX_AGENT_TURNS

   # NEW: Set up context manager with project context
   ctx_model_config = ModelConfig(
    name=model_cfg['name'],
    context_limit=model_cfg['context_limit'],
    native_function_calling=model_cfg.get('native_function_calling', True),
    max_agent_turns=MAX_AGENT_TURNS
   )
   context_manager = ContextManager(ctx_model_config)

   # Get project context for system prompt
   if project_index and user_input:
    project_context = project_index.get_context_for_task(user_input)
    context_manager.set_project_context(project_context)
    logger.info(f"[{session_id}] Project context: {len(project_context)} chars")

   while True:
    turn_start = time.time()
    agent_turns += 1
    logger.info(f"[{session_id}] ══════════════════════════════════════════════════════")
    logger.info(f"[{session_id}] AGENT TURN {agent_turns}")
    logger.info(f"[{session_id}] Model: {current_model}")
    logger.info(f"[{session_id}] Messages in context: {len(messages)}")

    UI.thinking()

    # Phase 5: Check Diagnostics Portal at start of turn
    diag_path = os.path.join(workspace.root_dir, ".gondola_diagnostics.json")
    if os.path.exists(diag_path):
        try:
            with open(diag_path, "r") as f:
                diags = json.load(f)
            if diags:
                diag_msg = f"SYSTEM ALERT: Background diagnostics found issues:\n{json.dumps(diags, indent=2)}\nFix these if they relate to your recent changes."
                messages.append({"role": "user", "content": diag_msg})
                # Clear after reading to avoid repeated alerts
                os.remove(diag_path)
        except (IOError, OSError, json.JSONDecodeError):
            pass  # Diagnostics file missing or corrupt, that's ok

    # Sanitize messages to prevent API errors
    sanitized_messages = []
    for m in messages:
        if m.get("role") == "assistant":
            content = m.get("content")
            tool_calls = m.get("tool_calls")
            
            # Check for valid tool calls (must be a non-empty list)
            has_tools = tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0
            
            # Check for valid content (must be a non-empty string)
            has_content = content is not None and str(content).strip() != ""
            
            if has_tools or has_content:
                m_copy = {"role": "assistant"}
                
                # Only include content if it's non-empty
                # Omit entirely if empty and we have tool_calls
                if has_content:
                    m_copy["content"] = content
                elif not has_tools:
                    # No tools and no content - shouldn't happen, but include empty string
                    m_copy["content"] = ""
                
                # Include tool_calls if present
                if has_tools:
                    m_copy["tool_calls"] = tool_calls
                
                sanitized_messages.append(m_copy)
            # Else drop the message entirely
        else:
            sanitized_messages.append(m)

    # Debug: Print message structure if needed
    # import json
    # print(f"DEBUG MESSAGES: {json.dumps(sanitized_messages, indent=2)}")

    # NEW: Rebuild dynamic system prompt with project context
    if project_index and agent_state:
     files_read = agent_state.get_files_read_list()
     dynamic_prompt = build_system_prompt(
      model_id=current_model,
      project_context=context_manager.project_context if context_manager else None,
      turn_count=agent_turns,
      max_turns=MAX_AGENT_TURNS,
      files_already_read=files_read
     )
     # Update system message
     if messages and messages[0].get('role') == 'system':
      messages[0]['content'] = dynamic_prompt
      logger.debug(f"[{session_id}] Dynamic system prompt updated ({len(dynamic_prompt)} chars)")

    # Get model-specific settings
    model_info = MODELS.get(current_model, {})
    max_tokens = model_info.get("max_tokens", 20000)
    stream_timeout = model_info.get("stream_timeout", 60)
    context_limit = model_info.get("context_limit", 128000)
    pricing = model_info.get("pricing", "unknown")

    logger.info(f"[{session_id}] ┌─────────────────────────────────────────────────────")
    logger.info(f"[{session_id}] │ API REQUEST")
    logger.info(f"[{session_id}] │ Model:          {current_model}")
    logger.info(f"[{session_id}] │ Max Tokens:     {max_tokens}")
    logger.info(f"[{session_id}] │ Stream Timeout: {stream_timeout}s")
    logger.info(f"[{session_id}] │ Context Limit:  {context_limit}")
    logger.info(f"[{session_id}] │ Pricing:        {pricing}")
    logger.info(f"[{session_id}] │ Messages:       {len(sanitized_messages)}")
    logger.info(f"[{session_id}] └─────────────────────────────────────────────────────")

    # Retry logic for timeout errors
    max_retries = 3
    retry_delay = 2
    stream = None

    for attempt in range(max_retries):
     api_call_start = time.time()
     logger.info(f"[{session_id}] >>> API call attempt {attempt + 1}/{max_retries} at {datetime.now().isoformat()}")

     try:
      # Build Venice-specific parameters
      venice_params = {
          "include_venice_system_prompt": False
      }

      stream = client.chat.completions.create(
       model=current_model,
       messages=sanitized_messages,
       temperature=0.4,
       max_completion_tokens=max_tokens,
       stream=True,
       tools=TOOL_SCHEMAS,
       tool_choice="auto",
       timeout=300.0,
       extra_body={"venice_parameters": venice_params}
      )
      api_connect_time = time.time() - api_call_start
      logger.info(f"[{session_id}] <<< Stream created in {api_connect_time:.3f}s")
      break  # Success

     except Exception as e:
      api_elapsed = time.time() - api_call_start
      error_str = str(e).lower()
      UI.clear_thinking()

      logger.error(f"[{session_id}] ⛔ API CALL FAILED (attempt {attempt + 1})")
      logger.error(f"[{session_id}] Exception type: {type(e).__name__}")
      logger.error(f"[{session_id}] Exception message: {str(e)}")
      logger.error(f"[{session_id}] Elapsed time: {api_elapsed:.2f}s")

      if "timeout" in error_str or "timed out" in error_str:
       logger.error(f"[{session_id}] TIMEOUT DETECTED!")
       if attempt < max_retries - 1:
        logger.info(f"[{session_id}] Retrying in {retry_delay}s (exponential backoff)")
        UI.warning(f"Timeout (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay}s...")
        time.sleep(retry_delay)
        retry_delay *= 2  # Exponential backoff
        UI.thinking()
        continue
       else:
        logger.error(f"[{session_id}] ALL RETRIES EXHAUSTED - giving up")
        UI.error(f"Timed out after {max_retries} attempts")
        UI.info("Try: 1) Switch to faster model (/model), 2) Type 'clear' to reset context")
        break
      else:
       logger.error(f"[{session_id}] NON-TIMEOUT ERROR - not retrying")
       UI.error(f"API Error: {e}")
       break

    if stream is None:
     logger.error(f"[{session_id}] Stream is None - failed all retries or encountered error")
     break  # Failed all retries

    UI.clear_thinking()

    response_content = ""
    finish_reason = None
    native_tool_calls = []  # Track native function calls from API
    current_tool_call = {}  # Accumulator for streaming tool call chunks
    print() # New line before response

    # Stall detection for cheaper models
    last_chunk_time = time.time()
    stream_start_time = time.time()
    first_chunk_time = None
    chunk_count = 0
    total_content_chars = 0

    logger.info(f"[{session_id}] Starting stream processing...")

    for chunk in stream:
     chunk_count += 1
     current_time = time.time()

     # Log first chunk timing (time to first token)
     if first_chunk_time is None:
      first_chunk_time = current_time
      ttft = first_chunk_time - api_call_start
      logger.info(f"[{session_id}] ⚡ FIRST CHUNK received! Time-to-first-token: {ttft:.3f}s")

     # Log progress every 100 chunks
     if chunk_count % 100 == 0:
      elapsed = current_time - stream_start_time
      logger.debug(f"[{session_id}] Chunk #{chunk_count} | Elapsed: {elapsed:.1f}s | Content chars: {total_content_chars}")

     # Check for stream timeout (model stalled)
     time_since_last = current_time - last_chunk_time
     if time_since_last > stream_timeout:
      logger.error(f"[{session_id}] ⚠️ STREAM STALL DETECTED!")
      logger.error(f"[{session_id}] Time since last chunk: {time_since_last:.1f}s (threshold: {stream_timeout}s)")
      logger.error(f"[{session_id}] Total chunks received: {chunk_count}")
      logger.error(f"[{session_id}] Total content chars: {total_content_chars}")
      UI.warning(f"Stream timeout after {stream_timeout}s - model may be stuck")
      break
     last_chunk_time = current_time

     # Check if choices exist
     if not chunk.choices:
      continue

     choice = chunk.choices[0]

     # Track finish reason
     if choice.finish_reason:
      finish_reason = choice.finish_reason
      logger.debug(f"[{session_id}] Finish reason: {finish_reason}")

     # Handle reasoning content
     if hasattr(choice.delta, 'reasoning_content') and choice.delta.reasoning_content:
      UI.reasoning(choice.delta.reasoning_content)

     # Handle native tool_calls (streaming format)
     if hasattr(choice.delta, 'tool_calls') and choice.delta.tool_calls:
      for tc in choice.delta.tool_calls:
       idx = tc.index if hasattr(tc, 'index') else 0
       # Initialize tool call entry if needed
       while len(native_tool_calls) <= idx:
        native_tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
        logger.debug(f"[{session_id}] New tool call detected at index {idx}")

       if hasattr(tc, 'id') and tc.id:
        native_tool_calls[idx]["id"] = tc.id
       if hasattr(tc, 'function') and tc.function:
        if hasattr(tc.function, 'name') and tc.function.name:
         native_tool_calls[idx]["function"]["name"] = tc.function.name
        if hasattr(tc.function, 'arguments') and tc.function.arguments:
         native_tool_calls[idx]["function"]["arguments"] += tc.function.arguments
         # Visual feedback for tool generation
         curr_len = len(native_tool_calls[idx]["function"]["arguments"])
         t_name = native_tool_calls[idx]["function"]["name"] or "tool"
         print(f"\r{Colors.DIM}Generating {t_name} args... {curr_len} chars{Colors.RESET}", end="", flush=True)

     # Handle standard content
     if choice.delta.content:
      content = choice.delta.content
      total_content_chars += len(content)

      # Don't print tool_code tags
      if "<tool_code>" not in response_content and "<tool_code>" not in content:
       print(content, end="", flush=True)
      elif "<tool_code>" in response_content and "</tool_code>" in content:
       # End of tool code, continue printing after
       pass

      response_content += content

    # Log stream completion
    stream_duration = time.time() - stream_start_time
    logger.info(f"[{session_id}] ✓ Stream completed")
    logger.info(f"[{session_id}]   Total chunks: {chunk_count}")
    logger.info(f"[{session_id}]   Total content chars: {total_content_chars}")
    logger.info(f"[{session_id}]   Stream duration: {stream_duration:.2f}s")
    logger.info(f"[{session_id}]   Finish reason: {finish_reason}")
    logger.info(f"[{session_id}]   Tool calls detected: {len(native_tool_calls)}")
    if native_tool_calls:
     for idx, tc in enumerate(native_tool_calls):
      logger.info(f"[{session_id}]     [{idx}] {tc['function']['name']} (args: {len(tc['function']['arguments'])} chars)")

    print() # New line after response

    # Warn if response was truncated due to length
    if finish_reason == "length":
     logger.warning(f"[{session_id}] Response truncated (finish_reason=length)")
     UI.warning("Response was truncated (hit token limit). The model may need to retry with shorter output.")

    # Detect if model timed out on backend
    if finish_reason is None and not response_content.strip() and not native_tool_calls:
     logger.error(f"[{session_id}] Backend timeout or connection lost - no response received")
     logger.error(f"[{session_id}] finish_reason=None, response_content empty, no tool calls")
     UI.error("Backend timeout or connection lost - no response received")
     UI.info("Try again or switch to a different model")
     break

    # NATIVE TOOL CALLS (priority - proper OpenAI function calling)
    if native_tool_calls and native_tool_calls[0].get("function", {}).get("name"):
     # Build assistant message with tool_calls
     assistant_msg = {"role": "assistant", "tool_calls": []}
     if response_content.strip():
      assistant_msg["content"] = response_content

     for i, tc in enumerate(native_tool_calls):
      tc_id = tc.get("id") or f"call_{i}"
      assistant_msg["tool_calls"].append({
       "id": tc_id,
       "type": "function",
       "function": {
        "name": tc["function"]["name"],
        "arguments": tc["function"]["arguments"]
       }
      })
     messages.append(assistant_msg)

     # Process each tool call
     logger.info(f"[{session_id}] Processing {len(native_tool_calls)} native tool call(s)")
     for tc in native_tool_calls:
      tool_name = tc["function"]["name"]
      try:
       tool_args = json.loads(tc["function"]["arguments"])
      except json.JSONDecodeError:
       tool_args = {}
       logger.warning(f"[{session_id}] Failed to parse tool arguments as JSON")

      tc_id = tc.get("id") or "call_0"

      logger.info(f"[{session_id}] ┌─ TOOL: {tool_name}")
      logger.info(f"[{session_id}] │  ID: {tc_id}")
      logger.debug(f"[{session_id}] │  Args: {json.dumps(tool_args)[:500]}")

      UI.info(f"Tool: {tool_name}")

      # Increment turn counter
      agent_turns += 1

      # NEW: Update agent state
      agent_state.record_turn()

      # NEW: Check for loop patterns
      loop_warning = agent_state.detect_loop_pattern()
      if loop_warning:
       consecutive_loop_warnings += 1
       logger.warning(f"[{session_id}] LOOP DETECTED ({consecutive_loop_warnings}x): {loop_warning}")
       UI.warning(f"Loop pattern detected ({consecutive_loop_warnings}x)")
       
       if consecutive_loop_warnings >= 2:
        # Force break after 2 consecutive loop warnings
        logger.warning(f"[{session_id}] FORCING BREAK after {consecutive_loop_warnings} loop warnings")
        UI.warning("Forcing stop due to repeated loop detection")
        messages.append({
         "role": "tool",
         "tool_call_id": tc_id,
         "content": "SYSTEM: FORCED STOP. Loop detected multiple times. You MUST call done() NOW."
        })
        break
       else:
        messages.append({
         "role": "user",
         "content": f"SYSTEM: {loop_warning}"
        })
      else:
       consecutive_loop_warnings = 0  # Reset if no loop detected

      # NEW: Inject checkpoint reminders
      if agent_turns in checkpoint_turns:
       checkpoint_msg = get_checkpoint_message(agent_turns, current_model)
       if checkpoint_msg:
        logger.info(f"[{session_id}] Injecting checkpoint at turn {agent_turns}")
        UI.info(f"Checkpoint: {checkpoint_msg}")
        # BUGFIX: Actually inject the checkpoint into the conversation!
        messages.append({
         "role": "user",
         "content": f"SYSTEM CHECKPOINT: {checkpoint_msg}"
        })

      # Check for max turns
      if agent_turns >= MAX_AGENT_TURNS:
       logger.warning(f"[{session_id}] MAX_AGENT_TURNS ({MAX_AGENT_TURNS}) reached!")
       UI.warning(f"Reached {MAX_AGENT_TURNS} tool calls. Pausing for your input.")
       messages.append({
        "role": "tool",
        "tool_call_id": tc_id,
        "content": "SYSTEM: Max tool calls reached. You MUST call done() NOW with your best response."
       })
       break

      # Detect edit loops
      if tool_name in ("edit_file", "replace_lines"):
       edit_sig = f"{tool_name}:{tool_args.get('filename')}:{tool_args.get('start_line', '')}:{tool_args.get('old_text', '')[:50]}"
       if edit_sig in recent_edits:
        logger.warning(f"[{session_id}] Edit loop detected! Signature: {edit_sig[:100]}")
        UI.warning("Detected repeated edit attempt - breaking loop")
        messages.append({
         "role": "tool",
         "tool_call_id": tc_id,
         "content": "SYSTEM: Loop detected. You're repeating the same edit."
        })
        break
       recent_edits.append(edit_sig)
       recent_edits = recent_edits[-10:]

      # NEW: Check for duplicate file reads
      if tool_name == 'read_file':
       filename = tool_args.get('filename', '')
       if agent_state.was_file_read(filename):
        logger.warning(f"[{session_id}] │  DUPLICATE READ: {filename}")
        UI.warning(f"Duplicate read: {filename} (already read)")
        messages.append({
         "role": "tool",
         "tool_call_id": tc_id,
         "content": json.dumps({"success": True, "warning": "You already read this file. Use your previous read."})
        })
        continue

      # Execute tool - build tool_call dict for execute_tool
      tool_call_dict = {"tool": tool_name, **tool_args}
      tools.set_steps(1)
      tool_start = time.time()
      result = execute_tool(tools, tool_call_dict)
      tool_duration = time.time() - tool_start

      # NEW: Track tool call in agent state
      tool_warning = agent_state.record_tool_call(tool_name, tool_args, result)
      if tool_warning:
       logger.warning(f"[{session_id}] │  {tool_warning}")

      # Phase 1: Create cognitive checkpoint after successful edit
      if tool_name in ("write_file", "edit_file", "replace_lines") and result.get("success"):
          thought = response_content[:100] if response_content else "Performing edit"
          task = f"Complete work in {tool_args.get('filename')}"
          if persistence:
              persistence.checkpoint(thought, task)

      # NEW: Track file reads
      if tool_name == 'read_file' and isinstance(result, dict) and result.get('success'):
       content = result.get('content', '')
       full_hash = result.get('hash')
       agent_state.record_file_read(tool_args.get('filename', ''), content, full_hash=full_hash)

      # NEW: Track file writes/edits
      if tool_name == 'write_file':
       agent_state.record_file_write(tool_args.get('filename', ''))
      if tool_name == 'edit_file':
       agent_state.record_file_edit(tool_args.get('filename', ''))

      # NEW: Compress large results
      result_str = json.dumps(result)
      if len(result_str) > 5000 and context_manager:
       result_str = context_manager.compress_tool_result(tool_name, result)
       logger.info(f"[{session_id}] │  Compressed result: {len(result_str)} chars")

      logger.info(f"[{session_id}] │  Duration: {tool_duration:.2f}s")
      logger.info(f"[{session_id}] │  Success: {result.get('success', 'N/A')}")
      logger.debug(f"[{session_id}] │  Result: {result_str[:300]}")
      logger.info(f"[{session_id}] └─ DONE")

      # Check if task is done
      if tool_name == "done":
       done_summary = tool_args.get("summary", "Task completed")
       session_summaries.append(done_summary)
       # NEW: Record done in agent state
       agent_state.record_done(done_summary)
       messages.append({
        "role": "tool",
        "tool_call_id": tc_id,
        "content": result_str
       })
       break

      # Handle edit failures
      if tool_name in ("edit_file", "replace_lines") and not result.get("success"):
       consecutive_edit_failures += 1
       if consecutive_edit_failures >= 2:
        UI.warning("Multiple edit failures - stopping for user guidance")
      else:
       consecutive_edit_failures = 0

      # Validate syntax after code edits
      if tool_name in ("edit_file", "replace_lines", "write_file") and result.get("success"):
       filename = tool_args.get("filename")
       if filename and filename.endswith(".py"):
        syntax_result = tools.validate_syntax(filename)
        if not syntax_result.get("valid", True):
         UI.warning(f"Edit created syntax error at line {syntax_result.get('line')}")
         result["syntax_error"] = syntax_result.get("error")
         result["syntax_line"] = syntax_result.get("line")

      # Add tool result message (use compressed result if applicable)
      messages.append({
       "role": "tool",
       "tool_call_id": tc_id,
       "content": result_str
      })

     # Check if we hit done or max turns
     if tool_name == "done" or agent_turns >= MAX_AGENT_TURNS:
      break
     continue

    # FALLBACK: Text-based tool parsing (for models without native function calling)
    if not response_content.strip():
     UI.warning("Empty response from model")
     break

    messages.append({"role": "assistant", "content": response_content})

    # Check for tool call in text
    tool_call = parse_tool_call(response_content)

    if tool_call:
     if "error" in tool_call:
      UI.error(tool_call["error"])
      # Give appropriate guidance based on error type
      if "truncated" in tool_call["error"].lower():
       messages.append({
        "role": "user",
        "content": f"SYSTEM ERROR: {tool_call['error']}\n\nYour response was cut off before the closing tag. Please retry the COMPLETE tool call - make sure to include the closing tag (e.g., </write_file> or </tool_code>). Keep the content concise if needed."
       })
      else:
       messages.append({
        "role": "user",
        "content": f"Tool parse error: {tool_call['error']}. Please check and fix the syntax."
       })
      continue

     # Increment turn counter
     agent_turns += 1
     tool_name = tool_call.get("tool") or tool_call.get("name")

     # Check for max turns
     if agent_turns >= MAX_AGENT_TURNS:
      UI.warning(f"Reached {MAX_AGENT_TURNS} tool calls. Pausing for your input.")
      messages.append({
       "role": "user",
       "content": "SYSTEM: Reached maximum automatic tool calls. Please summarize what you've done and what remains, then wait for user input."
      })
      break

     # Detect edit loops - track edit attempts
     if tool_name in ("edit_file", "replace_lines"):
      edit_sig = f"{tool_name}:{tool_call.get('filename')}:{tool_call.get('start_line', '')}:{tool_call.get('old_text', '')[:50]}"
      if edit_sig in recent_edits:
       UI.warning("Detected repeated edit attempt - breaking loop")
       messages.append({
        "role": "user",
        "content": "SYSTEM: You're attempting the same edit again. This suggests a loop. Stop and explain what's going wrong."
       })
       break
      recent_edits.append(edit_sig)
      # Keep only last 10 edits
      recent_edits = recent_edits[-10:]

     # Execute tool
     tools.set_steps(1) # Single step for now
     result = execute_tool(tools, tool_call)

     # Check if task is done
     if tool_name == "done":
      # Capture summary for session history
      done_summary = tool_call.get("summary", "Task completed")
      session_summaries.append(done_summary)
      break

     # Handle edit failures - don't auto-retry
     if tool_name in ("edit_file", "replace_lines") and not result.get("success"):
      consecutive_edit_failures += 1
      if consecutive_edit_failures >= 2:
       UI.warning("Multiple edit failures - stopping for user guidance")
       messages.append({
        "role": "user",
        "content": f"SYSTEM: Edit failed: {result.get('error')}. You've had {consecutive_edit_failures} consecutive edit failures. Stop and ask the user for guidance instead of retrying."
       })
       break
      else:
       consecutive_edit_failures = 0 # Reset on success

     # Validate syntax after code edits
     if tool_name in ("edit_file", "replace_lines", "write_file") and result.get("success"):
      filename = tool_call.get("filename")
      if filename and filename.endswith(".py"):
       syntax_result = tools.validate_syntax(filename)
       if not syntax_result.get("valid", True):
        UI.warning(f"Edit created syntax error at line {syntax_result.get('line')}")
        result["syntax_error"] = syntax_result.get("error")
        result["syntax_line"] = syntax_result.get("line")

     # Feed result back (but don't encourage continuation on failure)
     if result.get("success"):
      messages.append({
       "role": "user",
       "content": f"Tool result:\n```json\n{json.dumps(result, indent=2)}\n```\nContinue with next step or respond to user."
      })
     else:
      messages.append({
       "role": "user",
       "content": f"Tool FAILED:\n```json\n{json.dumps(result, indent=2)}\n```\nAnalyze what went wrong. If you're unsure how to proceed, ask the user for help."
      })
     continue

    # No tool call - wait for user input
    break

  except KeyboardInterrupt:
   print()
   UI.info("Interrupted. Type 'exit' to quit.")
   continue
  except Exception as e:
   UI.error(f"Error: {e}")
   continue


if __name__ == "__main__":
 main()