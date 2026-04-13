"""
Code analysis, refactoring, and memory operations for Cortex AI
"""

import os
import ast
import json
import shutil
from datetime import datetime

from cortex.core import UI, Colors
from cortex.tools.base import Tools


class CodeOpsMixin(Tools):
    """Mixin for code analysis, refactoring, and memory operations"""

    def __init__(self, workspace, memory=None, project_index=None, **kwargs):
        super().__init__(workspace=workspace, memory=memory, project_index=project_index, **kwargs)

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
        return {"success": True, "summary": summary, "terminate": True}

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
                # Use tree-sitter if available via UndeadOpsMixin
                if hasattr(self, 'parsers') and 'javascript' in self.parsers:
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        tree = self.parsers['javascript'].parse(bytes(content, 'utf8'))
                        # Tree-sitter root_node.has_error is True if there's a syntax error
                        if tree.root_node.has_error:
                            UI.step_error("JS syntax error detected by Tree-sitter")
                            return {"success": True, "valid": False, "error": "Syntax error in JS file"}
                        UI.step_done("JS syntax is valid (Tree-sitter)")
                        return {"success": True, "valid": True, "type": "javascript"}
                    except Exception as e:
                        UI.step_detail(f"Tree-sitter JS check failed: {e}")
                
                # Fallback: Basic JS check: ensure balanced braces/parens
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Very naive check, but catches catastrophic cut-offs
                if content.count('{') != content.count('}'):
                    return {"success": True, "valid": False, "warning": "Unbalanced braces {} in JS file"}
                if content.count('(') != content.count(')'):
                    return {"success": True, "valid": False, "warning": "Unbalanced parens () in JS file"}
                UI.step_done("JS syntax looks okay (balanced braces)")
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

    # ---- Semantic Search ----

    def semantic_search(self, query, max_results=5):
        """Search the project using vector similarity for conceptual matches. Returns file paths and line hints."""
        # self.next_step(f"Semantic search: {query}")  # Skip UI dependency for standalone use
        
        # Create project index on-demand if not available
        if not self.project_index:
            try:
                from cortex.project_index import ProjectIndex
                workspace_path = self.workspace.root_dir if hasattr(self.workspace, 'root_dir') else str(self.workspace)
                self.project_index = ProjectIndex(workspace_path)
                self.project_index.build()
                # UI.step_info(f"Built project index with {self.project_index.file_count()} files")
            except Exception as e:
                # UI.step_error(f"Failed to build project index: {e}")
                return {"success": False, "error": f"Project index not available: {e}"}
        
        try:
            results = self.project_index.semantic_search(query, max_results=max_results)
            
            # Also check for relevant knowledge entries
            knowledge_results = []
            if hasattr(self, 'get_relevant_knowledge'):
                knowledge_entries = self.get_relevant_knowledge(query)
                for entry in knowledge_entries:
                    knowledge_results.append({
                        "filename": f".cortex_knowledge/{entry['title']}.md",
                        "relevance": 0.95,  # High relevance for explicit knowledge
                        "summary": f"Knowledge: {entry['title']}",
                        "line_hints": [],
                        "knowledge_content": entry['content']  # Include actual knowledge
                    })
            
            formatted_results = []
            for filepath, score in results:
                summary = self.project_index.file_summaries.get(filepath, "No summary available")
                
                # Extract line hints from symbols if they match query
                line_hints = []
                if filepath in self.project_index.symbols:
                    syms = self.project_index.symbols[filepath]
                    query_terms = query.lower().split()
                    
                    for sym_type in ['classes', 'functions']:
                        if sym_type in syms:
                            for sym in syms[sym_type]:
                                name = sym['name'] if isinstance(sym, dict) else sym
                                line = sym['line'] if isinstance(sym, dict) else None
                                if any(term in name.lower() for term in query_terms):
                                    line_hints.append({"name": name, "line": line, "type": sym_type[:-1]})

                formatted_results.append({
                    "filename": filepath,
                    "relevance": round(score, 3),
                    "summary": summary,
                    "line_hints": line_hints
                })
            
            # Merge knowledge results (they usually have higher relevance)
            formatted_results = knowledge_results + formatted_results
            
            # Sort by relevance
            formatted_results.sort(key=lambda x: x["relevance"], reverse=True)
            
            if formatted_results:
                UI.step_detail(f"Found {len(formatted_results)} relevant results")
                for res in formatted_results[:3]:
                    hints_str = f" ({len(res['line_hints'])} line hints)" if res.get('line_hints') else ""
                    knowledge_marker = " [KNOWLEDGE]" if '.cortex_knowledge/' in res['filename'] else ""
                    UI.step_detail(f"  - {res['filename']}{knowledge_marker} {hints_str}")
                UI.step_done()
            else:
                UI.step_detail("No conceptually relevant files found")
                UI.step_done()
                
            return {"success": True, "results": formatted_results[:max_results]}
            
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    