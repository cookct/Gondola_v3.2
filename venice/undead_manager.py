import jedi
import json
import tempfile
import os
from pathlib import Path

class UndeadManager:
    """Manages surgical code analysis with immediate cleanup."""
    
    def __init__(self):
        self.project_path = Path.cwd()
    
    def inspect_type(self, filename: str, symbol: str, coords: dict) -> dict:
        """Surgical autopsy: analyze code and return immediately"""
        try:
            if not coords or "error" in coords:
                return coords or {"error": "Invalid coordinates"}
                
            # Read file content
            file_path = self.project_path / filename
            if not file_path.exists():
                return {"error": f"File {filename} not found"}
                
            with open(file_path, 'r') as f:
                code = f.read()
            
            # Use Jedi to analyze
            try:
                script = jedi.Script(code, path=str(file_path))
                # Get the line and column from coordinates
                line = coords["line"] + 1  # Jedi is 1-indexed
                col = 0  # Start of line
                
                # Find the exact column by searching for the symbol
                lines = code.split('\n')
                if line <= len(lines):
                    line_content = lines[line - 1]
                    col = line_content.find(symbol)
                    if col == -1:
                        col = 0
                
                definitions = script.infer(line, col)
                
                results = []
                for definition in definitions:
                    results.append({
                        'name': definition.name,
                        'type': definition.type,
                        'module_path': definition.module_path,
                        'line': definition.line,
                        'column': definition.column,
                        'docstring': definition.docstring()
                    })
                return {"type_info": results}
                
            except Exception as e:
                return {"error": f"Jedi analysis failed: {str(e)}"}
                
        except ImportError:
            return {"error": "jedi not installed. Run 'pip install jedi'"}
        except Exception as e:
            return {"error": f"Type inspection failed: {str(e)}"}