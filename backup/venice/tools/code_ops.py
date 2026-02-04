"""
Code analysis, refactoring, and memory operations for Venice CLI
"""

import os
import ast
import json
import shutil
from datetime import datetime

from venice.core import UI, Colors
from venice.tools.base import Tools


class CodeOpsMixin(Tools):
    """Mixin for code analysis, refactoring, and memory operations"""

    # ---- Memory ----

    def remember(self, note):
        """Save a note to persistent memory"""
        self.next_step("Saving to memory")

        if not self.memory:
            UI.step_error("Memory not available")
            return {"success": False, "error": "Memory not initialized"}

        self.memory.add_note(note)
        UI.step_detail(f"Saved: {note[:60]}...")
        UI.step_done("Note saved")
        return {"success": True, "note": note}

    def recall(self):
        """Recall all stored memories"""
        self.next_step("Recalling memories")

        if not self.memory:
            UI.step_error("Memory not available")
            return {"success": False, "error": "Memory not initialized"}

        context = self.memory.get_context()
        if context:
            UI.step_detail("Memory contents:")
            for line in context.split('\n')[:20]:
                UI.step_detail(f"  {line}")
            UI.step_done()
            return {"success": True, "memory": context}
        else:
            UI.step_detail("No memories stored yet")
            UI.step_done()
            return {"success": True, "memory": ""}

    def forget(self, clear_all=False):
        """Clear stored memories"""
        self.next_step("Clearing memories")

        if not self.memory:
            UI.step_error("Memory not available")
            return {"success": False, "error": "Memory not initialized"}

        if clear_all:
            self.memory.data = self.memory._default()
            self.memory.save()
            UI.step_done("All memories cleared")
        else:
            self.memory.clear_notes()
            UI.step_done("Project notes cleared")

        return {"success": True}

    def set_preference(self, key, value):
        """Set a user preference"""
        self.next_step(f"Setting preference: {key}")

        if not self.memory:
            UI.step_error("Memory not available")
            return {"success": False, "error": "Memory not initialized"}

        self.memory.set_preference(key, value)
        UI.step_detail(f"{key} = {value}")
        UI.step_done()
        return {"success": True, "key": key, "value": value}

    # ---- Task Completion ----

    def done(self, summary):
        """Signal task is complete"""
        UI.success(f"COMPLETE: {summary}")
        return {"success": True, "summary": summary}

    # ---- Code Analysis (Multi-Language) ----

    def validate_syntax(self, filename):
        """Check if file has valid syntax"""
        self.next_step(f"Validating syntax of {filename}")

        try:
            path = self.workspace._resolve(filename)
            if not os.path.exists(path):
                return {"success": False, "error": f"File '{filename}' does not exist"}

            ext = os.path.splitext(filename)[1].lower()

            if ext == '.py':
                with open(path, 'r', encoding='utf-8') as f:
                    ast.parse(f.read())
                UI.step_done("Python syntax is valid")
                return {"success": True, "valid": True, "type": "python"}

            elif ext == '.json':
                with open(path, 'r', encoding='utf-8') as f:
                    json.load(f)
                UI.step_done("JSON syntax is valid")
                return {"success": True, "valid": True, "type": "json"}
            
            elif ext == '.js':
                # Basic JS check: ensure balanced braces/parens
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Very naive check, but catches catastrophic cut-offs
                if content.count('{') != content.count('}'):
                    return {"success": True, "valid": False, "warning": "Unbalanced braces {} in JS file"}
                if content.count('(') != content.count(')'):
                    return {"success": True, "valid": False, "warning": "Unbalanced parens () in JS file"}
                return {"success": True, "valid": True, "type": "javascript"}

            else:
                return {"success": True, "valid": True, "type": "unknown", "message": "No validator available"}

        except SyntaxError as e:
            UI.step_error(f"Syntax Error: {e}")
            return {"success": False, "valid": False, "error": str(e), "line": e.lineno, "offset": e.offset}
        except json.JSONDecodeError as e:
            UI.step_error(f"JSON Error: {e}")
            return {"success": False, "valid": False, "error": str(e), "line": e.lineno, "column": e.colno}
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def find_functions(self, filename):
        """List functions in Python or JS files"""
        self.next_step(f"Finding functions in {filename}")
        try:
            path = self.workspace._resolve(filename)
            ext = os.path.splitext(filename)[1].lower()
            
            if ext == '.py':
                return self._find_py_functions(path)
            elif ext == '.js':
                return self._find_js_functions(path)
            else:
                return {"success": False, "error": f"Unsupported file type: {ext}"}
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def _find_py_functions(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({"name": node.name, "line": node.lineno, "end_line": node.end_lineno})
        functions.sort(key=lambda x: x['line'])
        UI.step_done(f"Found {len(functions)} Python functions")
        return {"success": True, "functions": functions}

    def _find_js_functions(self, path):
        import re
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        lines = content.splitlines()
        functions = []
        
        # Regex for: function foo(), const foo = () =>, foo: function()
        patterns = [
            r'function\s+([a-zA-Z0-9_]+)\s*\(',
            r'(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>',
            r'([a-zA-Z0-9_]+)\s*:\s*(?:async\s*)?function\s*\('
        ]
        
        for i, line in enumerate(lines):
            for p in patterns:
                match = re.search(p, line)
                if match:
                    functions.append({"name": match.group(1), "line": i + 1})
                    break
        
        UI.step_done(f"Found {len(functions)} JS functions")
        return {"success": True, "functions": functions}

    def find_classes(self, filename):
        """List classes (Python) or Selectors (CSS)"""
        self.next_step(f"Analyzing structure of {filename}")
        try:
            path = self.workspace._resolve(filename)
            ext = os.path.splitext(filename)[1].lower()
            
            if ext == '.py':
                return self._find_py_classes(path)
            elif ext == '.css':
                return self._find_css_selectors(path)
            else:
                return {"success": False, "error": f"Unsupported file type: {ext}"}
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def _find_py_classes(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append({"name": node.name, "line": node.lineno, "end_line": node.end_lineno})
        classes.sort(key=lambda x: x['line'])
        UI.step_done(f"Found {len(classes)} Python classes")
        return {"success": True, "classes": classes}

    def _find_css_selectors(self, path):
        import re
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        selectors = []
        # Naive regex for CSS selectors starting a block
        for i, line in enumerate(lines):
            line = line.strip()
            if line.endswith('{') and not line.startswith('@'):
                sel = line[:-1].strip()
                selectors.append({"name": sel, "line": i + 1})
        UI.step_done(f"Found {len(selectors)} CSS selectors")
        return {"success": True, "classes": selectors}

    def map_project(self, max_depth=2):
        """Generate a structural map of the project (files and symbols)"""
        self.next_step("Mapping project structure")
        
        try:
            tree = {}
            for root, dirs, files in os.walk(self.workspace.root_dir):
                # Ignore hidden/heavy
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'__pycache__', 'venv', 'node_modules'}]
                
                rel_root = os.path.relpath(root, self.workspace.root_dir)
                if rel_root == '.': rel_root = ''
                
                # Check depth
                depth = 0 if not rel_root else rel_root.count(os.sep) + 1
                if depth > max_depth: continue

                for f in files:
                    if f.startswith('.'): continue
                    full_path = os.path.join(root, f)
                    rel_path = os.path.join(rel_root, f)
                    
                    # Analyze file
                    ext = os.path.splitext(f)[1].lower()
                    summary = ""
                    
                    if ext == '.py':
                        funcs = self._find_py_functions(full_path)["functions"]
                        classes = self._find_py_classes(full_path)["classes"]
                        if funcs or classes:
                            summary = f"[{len(classes)} classes, {len(funcs)} funcs]"
                    elif ext == '.js':
                        funcs = self._find_js_functions(full_path)["functions"]
                        if funcs:
                            summary = f"[{len(funcs)} functions]"
                    
                    tree[rel_path] = summary

            # Format output
            output = ["PROJECT MAP:"]
            for path, summary in sorted(tree.items()):
                line = f"- {path}"
                if summary: line += f"  {Colors.GREY}{summary}{Colors.RESET}"
                output.append(line)
            
            result = "\n".join(output)
            UI.step_detail(f"Mapped {len(tree)} files")
            UI.step_done()
            return {"success": True, "map": result}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    # ---- Refactoring Helpers (Robust Tools) ----

    def extract_symbol(self, source_file, symbol_name, target_file=None):
        """Programmatically extract a variable, function, or class and optionally save it"""
        self.next_step(f"Extracting '{symbol_name}' from {source_file}")
        try:
            src_path = self.workspace._resolve(source_file)
            with open(src_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            lines = source_code.splitlines()
            
            tree = ast.parse(source_code)
            found_node = None
            
            for node in ast.iter_child_nodes(tree):
                # Check for Function or Class
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    if node.name == symbol_name:
                        found_node = node
                        break
                # Check for Variable Assignment
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == symbol_name:
                            found_node = node
                            break
            
            if not found_node:
                UI.step_error(f"Symbol '{symbol_name}' not found")
                return {"success": False, "error": f"Symbol '{symbol_name}' not found in top-level of {source_file}"}

            # Extract the raw lines
            start = found_node.lineno - 1
            end = found_node.end_lineno
            extracted_code = "\n".join(lines[start:end])

            if target_file:
                dst_path = self.workspace._resolve(target_file)
                # If file exists, append. If not, create.
                mode = 'a' if os.path.exists(dst_path) else 'w'
                with open(dst_path, mode, encoding='utf-8') as f:
                    if mode == 'a': f.write("\n\n")
                    f.write(extracted_code)
                UI.step_done(f"Extracted to {target_file}")
                return {"success": True, "code": extracted_code, "action": "saved"}
            
            UI.step_done()
            return {"success": True, "code": extracted_code}
        
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def write_constant(self, filename, variable_name, value):
        """Robustly write a string constant to a file, handling all escaping automatically.
        
        NOTE: This creates a Python variable assignment like: MY_VAR = "value"
        Do NOT use this for writing executable scripts - use write_file instead.
        """
        self.next_step(f"Writing constant '{variable_name}' to {filename}")
        try:
            # Warn if this looks like executable code (common misuse)
            if isinstance(value, str):
                code_indicators = ['def ', 'class ', 'import ', 'from ', 'if __name__']
                if any(indicator in value for indicator in code_indicators):
                    UI.step_detail(f"{Colors.YELLOW}⚠ WARNING: Value looks like executable code.{Colors.RESET}")
                    UI.step_detail(f"{Colors.YELLOW}  Use write_file for scripts, not write_constant.{Colors.RESET}")
            
            # Format as a valid Python assignment using repr() for perfect escaping
            if isinstance(value, str) and '\n' in value:
                # For multiline strings, use triple quotes but ESCAPE any existing triple quotes
                safe_value = value.replace('"""', '\\"\\"\\"')
                content = f'{variable_name} = """{safe_value}"""'
            else:
                content = f'{variable_name} = {repr(value)}'

            result = self.write_file(filename, content)
            
            # Add clarification to the result
            if result.get("success"):
                result["note"] = f"Created Python variable assignment: {variable_name} = <your_string>"
                result["usage"] = f"Import with: from {os.path.splitext(filename)[0]} import {variable_name}"
            
            return result
        
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def undo_edit(self, filename):
        """Restore the most recent backup of a file"""
        self.next_step(f"Undoing last edit to {filename}")
        try:
            # Get backups
            result = self.list_backups(filename)
            if not result["success"] or not result["backups"]:
                return {"success": False, "error": "No backups found"}
            
            # Latest is first
            latest = result["backups"][0]["name"]
            return self.restore_backup(latest, filename)
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}