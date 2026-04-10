# Tree-sitter is optional - graceful fallback if not installed
try:
    import tree_sitter
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
    tree_sitter = None
    Language = None
    Parser = None

import subprocess
import json
from pathlib import Path
import os

# Try to import pre-built tree-sitter languages
try:
    import tree_sitter_python
    import tree_sitter_javascript
    HAS_LANGUAGE_PACKAGES = True
except ImportError:
    HAS_LANGUAGE_PACKAGES = False


from cortex.tools.base import Tools
from cortex.core import UI

class UndeadOpsMixin(Tools):
    """Provides stateless code analysis using Tree-sitter with lazy initialization."""
    
    def __init__(self, workspace, memory=None, project_index=None, **kwargs):
        super().__init__(workspace=workspace, memory=memory, project_index=project_index, **kwargs)
        self._parsers = None  # Lazy initialization
        
    @property
    def parsers(self):
        """Lazy initialization of parsers"""
        if self._parsers is None:
            self._parsers = {}
            self._setup_parsers()
        return self._parsers
    
    def _setup_parsers(self):
        """Initialize Tree-sitter parsers with proper error handling"""
        try:
            if HAS_LANGUAGE_PACKAGES:
                # Use pre-built language packages
                self.PY_LANGUAGE = Language(tree_sitter_python.language())
                self.JS_LANGUAGE = Language(tree_sitter_javascript.language())
                
                self._parsers['python'] = Parser(self.PY_LANGUAGE)
                self._parsers['javascript'] = Parser(self.JS_LANGUAGE)
            else:
                # Fallback: try to use system-installed languages
                try:
                    # Look for system languages
                    self.PY_LANGUAGE = Language('build/my-languages.so', 'python')
                    self.JS_LANGUAGE = Language('build/my-languages.so', 'javascript')
                    
                    self._parsers['python'] = Parser(self.PY_LANGUAGE)
                    self._parsers['javascript'] = Parser(self.JS_LANGUAGE)
                except (ImportError, OSError) as e:
                    UI.step_detail(f"Tree-sitter languages not available: {e}")
                    
        except Exception as e:
            print(f"Failed to initialize Tree-sitter parsers: {e}")
            self._parsers = {}

    def get_skeleton(self, filename: str) -> dict:
        """Return AST structure with line ranges, imports and timestamps using Tree-sitter"""
        if not HAS_TREE_SITTER:
            return {"error": "Tree-sitter not installed. Install with: pip install tree-sitter"}
            
        path = self.workspace._resolve(filename)
        if not os.path.exists(path):
            return {"error": "File not found"}
            
        # Determine language
        if filename.endswith('.py'):
            lang = 'python'
        elif filename.endswith('.js') or filename.endswith('.jsx'):
            lang = 'javascript'
        else:
            return {"error": "Unsupported file type"}
            
        if lang not in self.parsers:
            return {"error": f"{lang} parser not available"}
            
        parser = self.parsers[lang]
        try:
            with open(path, 'r') as f:
                source_code = f.read()
                
            tree = parser.parse(bytes(source_code, 'utf8'))
            
            # Extract basic skeleton
            skeleton = self._extract_skeleton(tree.root_node, source_code)
            
            # Augment with imports
            skeleton["imports"] = self._extract_imports(tree.root_node, source_code, lang)
            
            # Augment with last modified (from git if possible)
            skeleton["last_modified"] = self._get_last_modified(path)
            
            return skeleton
            
        except Exception as e:
            return {"error": str(e)}

    def _extract_imports(self, node, source_code, lang):
        """Extract import statements from AST"""
        imports = []
        
        # Simple query for imports
        if lang == 'python':
            # Look for import_from and import_statement
            def find_py_imports(n):
                if n.type in ['import_statement', 'import_from_statement']:
                    imports.append(source_code[n.start_byte:n.end_byte].strip())
                for child in n.children:
                    find_py_imports(child)
            find_py_imports(node)
        elif lang == 'javascript':
            def find_js_imports(n):
                if n.type == 'import_declaration':
                    imports.append(source_code[n.start_byte:n.end_byte].strip())
                for child in n.children:
                    find_js_imports(child)
            find_js_imports(node)
            
        return imports

    def _get_last_modified(self, path):
        """Get last modified timestamp using git blame if available, else os"""
        try:
            # Try git first for more precision
            import subprocess
            result = subprocess.run(
                ["git", "log", "-1", "--format=%cd", "--", str(path)],
                capture_output=True, text=True, cwd=os.path.dirname(path)
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            pass  # Git not available or failed, use fallback
        
        # Fallback to OS stats
        mtime = os.path.getmtime(path)
        from datetime import datetime
        return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
    
    def _extract_skeleton(self, node, source_code: str, depth=0) -> dict:
        """Recursively extract class/method structure"""
        if depth > 5:  # Limit recursion
            return {}
            
        result = {
            "type": node.type,
            "start_line": node.start_point[0] + 1, # 1-indexed
            "end_line": node.end_point[0] + 1,     # 1-indexed
            "children": []
        }
        
        # Extract name if available
        if node.type in ['class_definition', 'function_definition', 'method_definition']:
            for child in node.children:
                if child.type == 'identifier':
                    result["name"] = source_code[child.start_byte:child.end_byte]
                    break
                    
        # Process children
        for child in node.children:
            # Skip trivial nodes
            if child.type not in ['comment', 'string', 'number']:
                child_skeleton = self._extract_skeleton(child, source_code, depth + 1)
                if child_skeleton:
                    result["children"].append(child_skeleton)
                    
        return result
    
    def get_symbol_coordinates(self, filename: str, symbol_name: str) -> dict:
        """Find exact line:column coordinates for a symbol"""
        skeleton = self.get_skeleton(filename)
        if "error" in skeleton:
            return skeleton
            
        # Search for symbol in AST
        result = self._find_symbol_in_skeleton(skeleton, symbol_name)
        if result:
            return result
        return {"error": f"Symbol '{symbol_name}' not found"}
    
    def _find_symbol_in_skeleton(self, node: dict, symbol_name: str) -> dict:
        """Recursively search for symbol in skeleton"""
        if "name" in node and node["name"] == symbol_name:
            return {
                "line": node["start_line"],
                "column": 0,
                "type": node["type"]
            }
            
        for child in node.get("children", []):
            result = self._find_symbol_in_skeleton(child, symbol_name)
            if result:
                return result
        return None

    # ---- Global Symbol Map (Ctags) ----

    def symbol_jump(self, symbol_name):
        """Project-wide search for a symbol definition using Ctags"""
        self.next_step(f"Symbol jump: {symbol_name}")
        
        tags_file = os.path.join(self.workspace.root_dir, ".gondola_tags")
        if not os.path.exists(tags_file):
            return {"success": False, "error": "Ctags index not found. Background indexing may still be running."}
            
        try:
            # Use grep to find symbol in tags file
            cmd = ["grep", f"^{symbol_name}\t", tags_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return {"success": False, "error": f"Symbol '{symbol_name}' not found in project index."}
                
            matches = []
            for line in result.stdout.splitlines():
                parts = line.split('\t')
                if len(parts) >= 2:
                    filename = parts[1]
                    line_num = 1
                    
                    # Try to find line number in fields (usually at the end)
                    for part in parts[2:]:
                        if part.startswith('line:'):
                            try:
                                line_num = int(part.split(':')[1])
                                break
                            except:
                                pass
                    
                    # Fallback: parse search pattern if it's a number
                    if line_num == 1 and len(parts) >= 3:
                        addr = parts[2].strip(';"')
                        if addr.isdigit():
                            line_num = int(addr)
                            
                    matches.append({"filename": filename, "line": line_num})
            
            UI.step_detail(f"Found match in {matches[0]['filename']}")
            UI.step_done()
            return {"success": True, "matches": matches}
            
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    # ---- Surgical Autopsy (Jedi) ----

    def inspect_type(self, filename, symbol):
        """Deep autopsy of a symbol's type/signature using Jedi"""
        self.next_step(f"Inspecting type of '{symbol}' in {filename}")
        
        try:
            # 1. Get coordinates using Tree-sitter (stateless)
            coords = self.get_symbol_coordinates(filename, symbol)
            if "error" in coords:
                UI.step_error(coords["error"])
                return {"success": False, "error": coords["error"]}

            # 2. Spawn surgical worker (Jedi)
            from cortex.undead_manager import UndeadManager
            manager = UndeadManager()
            result = manager.inspect_type(filename, symbol, coords)
            
            if "error" in result:
                UI.step_error(result["error"])
                return {"success": False, "error": result["error"]}
                
            UI.step_done()
            return {"success": True, "type_info": result["type_info"]}
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}