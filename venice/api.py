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


def get_api_key():
    key = os.getenv("VENICE_API_KEY")
    if key:
        return key
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
            key = config.get("venice_api_key")
            if key:
                return key
        except FileNotFoundError:
            continue
        except Exception as e:
            UI.warning(f"Error reading {config_path}: {e}")
            continue
    return None


def get_together_api_key():
    key = os.getenv("TOGETHER_API_KEY")
    if key:
        return key
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
            key = config.get("together_api_key")
            if key:
                return key
        except FileNotFoundError:
            continue
        except Exception as e:
            # UI.warning(f"Error reading {config_path}: {e}")
            continue
    return None


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
                   'get_skeleton', 'symbol_jump', 'inspect_type']

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
            return {"success": False, "error": "Invalid JSON in tool arguments"}
    else:
        name = tool_call.get("tool") or tool_call.get("name")
        args = tool_call
        logger.debug(f"Tool '{name}' - using dict-style arguments")

    if not name:
        logger.error("No tool name specified in tool_call")
        return {"success": False, "error": "No tool name specified"}

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
        # --- Previously missing tools ---
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
