'''
API utilities for Venice CLI
'''

import os
import re
import json
import logging
import time

from venice.config import SCRIPT_DIR
from venice.core import UI, MODELS
from venice.tools import CombinedTools
from venice.tools.schema import TOOL_SCHEMAS

# Get logger from parent module
logger = logging.getLogger('gondola.api')

# Build a lookup of tool schemas for validation
_TOOL_SCHEMA_MAP = {}
for schema in TOOL_SCHEMAS:
    if schema.get("type") == "function":
        func = schema.get("function", {})
        name = func.get("name")
        if name:
            _TOOL_SCHEMA_MAP[name] = func


def validate_tool_args(tool_name: str, args: dict) -> dict:
    """
    Validate tool arguments against schema before execution.
    Returns None if valid, or error dict if invalid.

    This catches malformed args from cheap models BEFORE they cause crashes.
    """
    schema = _TOOL_SCHEMA_MAP.get(tool_name)
    if not schema:
        return None  # Unknown tool - let execute_tool handle it

    params = schema.get("parameters", {})
    properties = params.get("properties", {})
    required = params.get("required", [])

    errors = []

    # Check required arguments
    for req_arg in required:
        if req_arg not in args or args[req_arg] is None:
            errors.append(f"Missing required argument: '{req_arg}'")

    # Check argument types
    for arg_name, arg_value in args.items():
        if arg_name in ["tool", "name"]:  # Skip meta fields
            continue
        if arg_name not in properties:
            continue  # Unknown arg, might be okay

        expected_type = properties[arg_name].get("type")
        if expected_type and arg_value is not None:
            if expected_type == "string" and not isinstance(arg_value, str):
                # Try to coerce to string
                args[arg_name] = str(arg_value)
            elif expected_type == "integer" and not isinstance(arg_value, int):
                try:
                    args[arg_name] = int(arg_value)
                except (ValueError, TypeError):
                    errors.append(f"Argument '{arg_name}' must be an integer, got: {type(arg_value).__name__}")
            elif expected_type == "boolean" and not isinstance(arg_value, bool):
                # Coerce common boolean strings
                if isinstance(arg_value, str):
                    args[arg_name] = arg_value.lower() in ("true", "yes", "1")
                else:
                    args[arg_name] = bool(arg_value)
            elif expected_type == "array" and not isinstance(arg_value, list):
                if isinstance(arg_value, str):
                    # Try to parse as JSON array
                    try:
                        args[arg_name] = json.loads(arg_value)
                    except:
                        # Treat as single-item array
                        args[arg_name] = [arg_value]

    if errors:
        return {
            "success": False,
            "error": f"Invalid arguments for '{tool_name}': {'; '.join(errors)}. Check the tool schema and provide all required arguments with correct types."
        }

    return None  # Valid


def _get_key_from_config(key_name, env_var_name):
    """
    Helper function to retrieve an API key from environment variable or config files.
    
    Lookup order:
    1. Environment variable specified by env_var_name
    2. Config files (app_config.json, ~/.venice_config.json, ~/.config/venice/config.json)
    
    Args:
        key_name: The config key name to look for in JSON files (e.g., "venice_api_key")
        env_var_name: The environment variable name to check (e.g., "VENICE_API_KEY")
    
    Returns:
        The API key string if found, None otherwise
    """
    # Check environment variable first
    key = os.getenv(env_var_name)
    if key:
        return key
    
    # Config file locations to search
    config_locations = [
        os.path.join(SCRIPT_DIR, "app_config.json"),
        os.path.expanduser("~/.venice_config.json"),
        os.path.expanduser("~/.config/venice/config.json"),
        "app_config.json",
    ]
    
    for config_path in config_locations:
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            key = config.get(key_name)
            if key:
                return key
        except FileNotFoundError:
            continue
        except Exception as e:
            UI.warning(f"Error reading {config_path}: {e}")
            continue
    return None


def get_api_key():
    """Retrieve the Venice API key from environment or config files."""
    return _get_key_from_config("venice_api_key", "VENICE_API_KEY")


def get_together_api_key():
    """Retrieve the Together API key from environment or config files."""
    return _get_key_from_config("together_api_key", "TOGETHER_API_KEY")


def get_brave_api_key():
    """Retrieve the Brave Search API key from environment or config files."""
    return _get_key_from_config("brave_api_key", "BRAVE_API_KEY")


def _clean_and_parse_json(json_str):
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    if json_str.startswith("```"):
        json_str = json_str[3:]
    if json_str.endswith("```"):
        json_str = json_str[:-3]
    json_str = json_str.strip()
    return json.loads(json_str)


def _parse_xml_tags(response_content):
    # Build tag names as variables to avoid parser issues
    wf_tag = "write_file"
    ef_tag = "edit_file"
    rc_tag = "run_command"
    
    # Pattern for write_file
    wf_pattern = r"<" + wf_tag + r'\s+filename=["\']([^"\']+)["\']>\s*(.*?)\s*</' + wf_tag + r'>'
    write_match = re.search(wf_pattern, response_content, re.DOTALL)
    if write_match:
        return {
            "tool": "write_file",
            "filename": write_match.group(1),
            "content": write_match.group(2)
        }
    
    # Pattern for edit_file
    ef_pattern = r"<" + ef_tag + r'\s+filename=["\']([^"\']+)["\']>\s*<search>\s*(.*?)\s*</search>\s*<replace>\s*(.*?)\s*</replace>\s*</' + ef_tag + r'>'
    edit_match = re.search(ef_pattern, response_content, re.DOTALL)
    if edit_match:
        return {
            "tool": "edit_file",
            "filename": edit_match.group(1),
            "old_text": edit_match.group(2),
            "new_text": edit_match.group(3)
        }
    
    # Pattern for run_command
    rc_pattern = r"<" + rc_tag + r">\s*(.*?)\s*</" + rc_tag + r">"
    cmd_match = re.search(rc_pattern, response_content, re.DOTALL)
    if cmd_match:
        return {
            "tool": "run_command",
            "command": cmd_match.group(1)
        }
    
    return None


def _find_balanced_json(text, start_pos=0):
    """Find a balanced JSON object using proper brace matching."""
    start = text.find("{", start_pos)
    if start == -1:
        return None
    
    depth = 0
    in_string = False
    escape_next = False
    
    for i, char in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    
    return None


def _parse_python_style_call(response_content):
    """Parse Python-style function calls like: ["make_directory(path='test_project')"]"""
    # Match array of function call strings
    # Pattern: [ "function_name(args)" ] or just function_name(args)

    # First try to find array format: ["func(...)"]
    array_pattern = r'\[\s*["\']([a-z_]+)\(([^)]*)\)["\']\s*\]'
    array_match = re.search(array_pattern, response_content, re.IGNORECASE)
    if array_match:
        func_name = array_match.group(1)
        args_str = array_match.group(2)
        return _parse_func_args(func_name, args_str)

    # Try standalone function call: func_name(args)
    func_pattern = r'\b([a-z_]+)\(([^)]*)\)'
    # Look for known tool names
    known_tools = ['list_files', 'read_file', 'write_file', 'edit_file', 'run_command',
                   'search_content', 'make_directory', 'delete_directory', 'delete_file',
                   'move_file', 'copy_file', 'map_project', 'validate_syntax', 'done',
                   'get_file_info', 'find_functions', 'find_classes', 'extract_symbol',
                   'remember', 'recall', 'forget', 'write_constant', 'replace_lines',
                   'insert_at_line', 'delete_lines', 'append_to_file', 'list_backups',
                   'restore_backup', 'undo_edit', 'set_preference', 'semantic_search',
                   'get_skeleton', 'symbol_jump', 'inspect_type', 'web_search', 'fetch_url',
                   'search_docs', 'search_stackoverflow', 'search_github', 'download_placeholder_image', 'download_image', 'image_search']

    for match in re.finditer(func_pattern, response_content):
        func_name = match.group(1)
        if func_name in known_tools:
            args_str = match.group(2)
            return _parse_func_args(func_name, args_str)

    return None


def _parse_func_args(func_name, args_str):
    """Parse function arguments like: path='test_project', recursive=True"""
    result = {"tool": func_name}

    if not args_str.strip():
        return result

    # Parse key=value pairs
    # Handle both 'string' and "string" quotes, and unquoted values
    arg_pattern = r"(\w+)\s*=\s*(?:'([^']*)'|\"([^\"]*)\"|(\w+))"

    for match in re.finditer(arg_pattern, args_str):
        key = match.group(1)
        # Value is in group 2 (single quote), 3 (double quote), or 4 (unquoted)
        value = match.group(2) or match.group(3) or match.group(4)

        # Convert boolean/numeric strings
        if value == 'True':
            value = True
        elif value == 'False':
            value = False
        elif value == 'None':
            value = None
        elif value and value.isdigit():
            value = int(value)

        result[key] = value

    return result


def _parse_json_tool_call(response_content):
    # Try tool_code tags first - extract content between tags, then parse
    tc_tag = "tool_code"
    # Match everything between tags (not just braces)
    tc_pattern = r"<" + tc_tag + r">(.*?)</" + tc_tag + r">"
    tool_code_match = re.search(tc_pattern, response_content, re.DOTALL)
    if tool_code_match:
        tag_content = tool_code_match.group(1).strip()
        # Now find balanced JSON within the tag content
        json_str = _find_balanced_json(tag_content)
        if json_str:
            try:
                parsed = _clean_and_parse_json(json_str)
                if "tool" in parsed or "name" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass

    # Fallback: brace matching on full response
    try:
        json_str = _find_balanced_json(response_content)
        if json_str:
            parsed = _clean_and_parse_json(json_str)
            if "tool" in parsed or "name" in parsed:
                return parsed
    except Exception:
        pass

    return None


def _detect_truncated_tags(response_content):
    """Detect if XML tags were started but not closed (truncated response)."""
    tags_to_check = ["write_file", "edit_file", "run_command", "tool_code"]
    
    for tag in tags_to_check:
        # Check if opening tag exists
        open_pattern = r"<" + tag + r"[^>]*>"
        if re.search(open_pattern, response_content):
            # Check if closing tag exists
            close_pattern = r"</" + tag + r">"
            if not re.search(close_pattern, response_content):
                return tag
    return None


def parse_tool_call(response_content):
    # First check for truncated tags
    truncated_tag = _detect_truncated_tags(response_content)
    if truncated_tag:
        return {
            "error": f"Tool call truncated (missing closing </{truncated_tag}> tag). The response may have been cut off. Please retry with the complete tool call."
        }

    result = _parse_xml_tags(response_content)
    if result:
        return result

    result = _parse_json_tool_call(response_content)
    if result:
        return result

    # Try Python-style function calls (for models like Gemma)
    result = _parse_python_style_call(response_content)
    if result:
        return result

    return None


def _validate_and_write_file(tools: CombinedTools, args: dict):
    """Validate write_file content isn't a placeholder before writing."""
    filename = args.get("filename")
    content = args.get("content", "")

    # Detect placeholder patterns (Gemma loves these)
    placeholder_patterns = [
        "<!-- content from above -->",
        "<!-- HTML content from above -->",
        "<!-- see above -->",
        "// code from above",
        "// see above",
        "# content from above",
        "... content here ...",
        "[content goes here]",
        "[insert content]",
    ]

    content_lower = content.lower().strip()

    # Check for placeholder patterns
    for pattern in placeholder_patterns:
        if pattern.lower() in content_lower:
            return {
                "success": False,
                "error": f"PLACEHOLDER DETECTED: You used '{pattern}' instead of actual content. "
                         f"You MUST include the FULL content in the write_file call, not a reference to content written elsewhere."
            }

    # Check for suspiciously short content for code files
    if len(content.strip()) < 20 and filename.endswith(('.html', '.js', '.py', '.css')):
        return {
            "success": False,
            "error": f"Content too short ({len(content)} chars). Include the FULL file content, not a placeholder."
        }

    # Content looks valid, proceed with write
    return tools.write_file(filename, content)


def execute_tool(tools: CombinedTools, tool_call: dict):
    """Execute a tool call and return the result with comprehensive logging."""
    start_time = time.time()

    if hasattr(tool_call, "function"):
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments)
            logger.debug(f"Tool '{name}' - parsed arguments from function object")
        except Exception as e:
            logger.error(f"Tool '{name}' - failed to parse JSON arguments: {e}")
            return {"success": False, "error": f"Invalid JSON in tool arguments: {e}. Check that all strings are properly quoted and all braces are balanced."}
    else:
        name = tool_call.get("tool") or tool_call.get("name")
        args = tool_call
        logger.debug(f"Tool '{name}' - using dict-style arguments")

    if not name:
        logger.error("No tool name specified in tool_call")
        return {"success": False, "error": "No tool name specified"}

    # PRE-VALIDATION: Catch bad args before execution (helps cheap models)
    validation_error = validate_tool_args(name, args)
    if validation_error:
        logger.warning(f"Tool '{name}' failed validation: {validation_error['error']}")
        return validation_error

    logger.info(f"execute_tool: {name}")
    logger.debug(f"Tool args: {json.dumps({k: v for k, v in args.items() if k not in ['content', 'old_text', 'new_text']})[:500]}")

    tool_map = {
        "list_files": lambda: tools.list_files(
            args.get("path", "."),
            args.get("pattern"),
            args.get("recursive", True)
        ),
        "read_file": lambda: tools.read_file(
            args.get("filename"),
            args.get("start_line"),
            args.get("end_line")
        ),
        "get_file_info": lambda: tools.get_file_info(args.get("filename")),
        "search_content": lambda: tools.search_content(
            args.get("pattern"),
            args.get("path", "."),
            args.get("file_pattern"),
            args.get("ignore_case", True)
        ),
        "write_file": lambda: _validate_and_write_file(tools, args),
        "edit_file": lambda: tools.edit_file(
            args.get("filename"),
            args.get("old_text"),
            args.get("new_text")
        ),
        "run_command": lambda: tools.run_command(
            args.get("command"),
            args.get("timeout", 30)
        ),
        "map_project": lambda: tools.map_project(
            args.get("max_depth", 2)
        ),
        "extract_symbol": lambda: tools.extract_symbol(
            args.get("source_file"),
            args.get("symbol_name"),
            args.get("target_file")
        ),
        "semantic_search": lambda: tools.semantic_search(
            args.get("query"),
            args.get("max_results", 5)
        ),
        "get_skeleton": lambda: tools.get_skeleton(
            args.get("filename")
        ),
        "symbol_jump": lambda: tools.symbol_jump(
            args.get("symbol_name")
        ),
        "inspect_type": lambda: tools.inspect_type(
            args.get("filename"),
            args.get("symbol")
        ),
        "write_constant": lambda: tools.write_constant(
            args.get("filename"),
            args.get("variable_name"),
            args.get("value")
        ),
        "make_directory": lambda: tools.make_directory(args.get("path")),
        "delete_directory": lambda: tools.delete_directory(
            args.get("path"), 
            args.get("recursive", False)
        ),
        "delete_file": lambda: tools.delete_file(args.get("filename")),
        "move_file": lambda: tools.move_file(
            args.get("source"), 
            args.get("destination")
        ),
        "copy_file": lambda: tools.copy_file(
            args.get("source"), 
            args.get("destination")
        ),
        "list_backups": lambda: tools.list_backups(args.get("filename")),
        "restore_backup": lambda: tools.restore_backup(
            args.get("backup_name"), 
            args.get("target_filename")
        ),
        "undo_edit": lambda: tools.undo_edit(args.get("filename")),
        "set_preference": lambda: tools.set_preference(
            args.get("key"), 
            args.get("value")
        ),
        "begin_transaction": lambda: tools.begin_transaction(),
        "commit_transaction": lambda: tools.commit_transaction(
            dry_run=args.get("dry_run", False)
        ),
        "get_symbol_coordinates": lambda: tools.get_symbol_coordinates(
            args.get("filename"),
            args.get("symbol_name")
        ),
        "done": lambda: tools.done(args.get("summary", "Task complete")),
        # --- Web tools ---
        "web_search": lambda: tools.web_search(
            args.get("query"),
            args.get("n_results", 5)
        ),
        "fetch_url": lambda: tools.fetch_url(
            args.get("url"),
            args.get("max_length", 10000)
        ),
        # --- Previously missing tools ---
        "image_search": lambda: tools.image_search(
            args.get("query"),
            args.get("n_results", 10)
        ),
        "download_placeholder_image": lambda: tools.download_placeholder_image(
            args.get("keyword"),
            args.get("width", 800),
            args.get("height", 600),
            args.get("service", "picsum"),
            args.get("filename"),
            args.get("grayscale", False),
            args.get("blur", 0)
        ),
        "download_image": lambda: tools.download_image(
            args.get("url"),
            args.get("filename")
        ),
        "append_to_file": lambda: tools.append_to_file(
            args.get("filename"),
            args.get("content")
        ),
        "replace_lines": lambda: tools.replace_lines(
            args.get("filename"),
            args.get("start_line"),
            args.get("end_line"),
            args.get("new_content"),
            args.get("expected_hash"),
            args.get("dry_run", False),
            args.get("thought"),
            args.get("verify_risk", False)
        ),
        "insert_at_line": lambda: tools.insert_at_line(
            args.get("filename"),
            args.get("line_number"),
            args.get("content")
        ),
        "delete_lines": lambda: tools.delete_lines(
            args.get("filename"),
            args.get("start_line"),
            args.get("end_line")
        ),
        "validate_syntax": lambda: tools.validate_syntax(args.get("filename")),
        "find_functions": lambda: tools.find_functions(args.get("filename")),
        "find_classes": lambda: tools.find_classes(args.get("filename")),
        "remember": lambda: tools.remember(args.get("note")),
        "recall": lambda: tools.recall(),
        "forget": lambda: tools.forget(args.get("clear_all", False)),
        "save_knowledge": lambda: tools.save_knowledge(
            args.get("keywords", []),
            args.get("content"),
            args.get("title")
        ),
        "search_file_content": lambda: tools.search_file_content(
            args.get("pattern"),
            args.get("path", "."),
            args.get("include"),
            args.get("ignore_case", True),
            args.get("context", 0),
            args.get("before", 0),
            args.get("after", 0)
        ),
        # --- Missing git tools ---
        "git_status": lambda: tools.git_status(),
        "git_log": lambda: tools.git_log(args.get("max_count", 10)),
        "git_diff": lambda: tools.git_diff(args.get("filename")),
        "git_blame": lambda: tools.git_blame(
            args.get("filename"),
            args.get("line_number")
        ),
        # --- Missing test tools ---
        "run_tests": lambda: tools.run_tests(
            args.get("path", "."),
            args.get("pattern"),
            args.get("verbose", False),
            args.get("fail_fast", False)
        ),
        "test_coverage": lambda: tools.test_coverage(args.get("test_path")),
        "find_test_files": lambda: tools.find_test_files(args.get("path", ".")),
        "generate_test_stub": lambda: tools.generate_test_stub(
            args.get("source_file"),
            args.get("function_name")
        ),
        # --- Missing web tools ---
        "search_docs": lambda: tools.search_docs(
            args.get("library"),
            args.get("query"),
            args.get("version")
        ),
        "search_github": lambda: tools.search_github(
            args.get("query"),
            args.get("language"),
            args.get("n_results", 5)
        ),
        "search_stackoverflow": lambda: tools.search_stackoverflow(
            args.get("query"),
            args.get("tags"),
            args.get("n_results", 5)
        ),
        # --- Missing utility tools ---
        "batch_read": lambda: tools.batch_read(args.get("files")),
        "multi_edit": lambda: tools.multi_edit(args.get("edits")),
        "find_and_replace": lambda: tools.find_and_replace(
            args.get("filename"),
            args.get("pattern"),
            args.get("replacement"),
            args.get("ignore_case", True)
        ),
        "smart_context": lambda: tools.smart_context(
            args.get("filename"),
            args.get("depth", 2)
        ),
        "suggest_commit_message": lambda: tools.suggest_commit_message(),
        "list_backups": lambda: tools.list_backups(args.get("filename")),
        "undo_edit": lambda: tools.undo_edit(args.get("filename")),
        "get_file_info": lambda: tools.get_file_info(args.get("filename")),
        "delete_file": lambda: tools.delete_file(args.get("filename")),
        "make_directory": lambda: tools.make_directory(args.get("path")),
        # --- Image generation tools ---
        "generate_image": lambda: tools.generate_image(
            args.get("prompt"),
            args.get("filename"),
            args.get("width", 1024),
            args.get("height", 1024)
        ),
        "edit_image": lambda: tools.edit_image(
            args.get("reference_image"),
            args.get("prompt"),
            args.get("filename")
        ),
    }

    if name not in tool_map:
        # Fuzzy match to suggest correct tool name
        from difflib import get_close_matches
        suggestions = get_close_matches(name, tool_map.keys(), n=3, cutoff=0.6)

        if suggestions:
            suggestion_str = ", ".join(suggestions)
            logger.error(f"Unknown tool: {name}. Did you mean: {suggestion_str}?")
            return {
                "success": False,
                "error": f"❌ Unknown tool: '{name}'. Did you mean: {suggestion_str}? Use the EXACT tool name from the schema."
            }
        else:
            logger.error(f"Unknown tool: {name}")
            return {"success": False, "error": f"❌ Unknown tool: '{name}'. Check the tool schema for valid tool names."}

    try:
        result = tool_map[name]()
        duration = time.time() - start_time
        success = result.get("success", True) if isinstance(result, dict) else True
        logger.info(f"Tool '{name}' completed in {duration:.3f}s (success={success})")
        if not success:
            logger.warning(f"Tool '{name}' failed: {result.get('error', 'unknown error')}")
        return result
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Tool '{name}' raised exception after {duration:.3f}s: {e}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return {"success": False, "error": str(e)}
