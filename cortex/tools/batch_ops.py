"""
Batch Operations - Multi-file editing and intelligent context gathering
"""

import os
import re
from typing import List, Dict, Tuple
from cortex.tools.base import Tools
from cortex.core import UI


class BatchOpsMixin(Tools):
    """Mixin for batch/multi-file operations"""

    def multi_edit(self, edits: List[Dict]) -> Dict:
        """
        Apply multiple edits across multiple files atomically.
        
        Args:
            edits: List of {"filename": str, "old_text": str, "new_text": str}
        
        Returns:
            {"success": True, "results": [...]} or {"success": False, "error": str, "failed_at": int}
        """
        self.next_step(f"Applying {len(edits)} edits across {len(set(e['filename'] for e in edits))} files")
        
        # Pre-validate all edits
        validated = []
        for i, edit in enumerate(edits):
            filename = edit.get('filename')
            old_text = edit.get('old_text')
            new_text = edit.get('new_text')
            
            if not all([filename, old_text is not None, new_text is not None]):
                return {"success": False, "error": f"Edit {i}: Missing required fields", "failed_at": i}
            
            try:
                path = self.workspace._resolve(filename)
                if not os.path.exists(path):
                    return {"success": False, "error": f"Edit {i}: File '{filename}' not found", "failed_at": i}
                
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if old_text not in content:
                    return {"success": False, "error": f"Edit {i}: Text not found in '{filename}'", "failed_at": i}
                
                validated.append((path, filename, old_text, new_text))
            except Exception as e:
                return {"success": False, "error": f"Edit {i}: {str(e)}", "failed_at": i}
        
        # Apply all edits
        results = []
        for path, filename, old_text, new_text in validated:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = content.replace(old_text, new_text, 1)
                
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                results.append({"filename": filename, "status": "success"})
                UI.step_detail(f"✓ {filename}")
            except Exception as e:
                return {"success": False, "error": f"Failed applying edit to '{filename}': {str(e)}", "failed_at": len(results)}
        
        UI.step_done(f"Applied {len(results)} edits")
        return {"success": True, "results": results}

    def smart_context(self, filename: str, depth: int = 2) -> Dict:
        """
        Intelligently gather context for a file by finding related files.
        
        Strategies:
        1. Imports/includes in the file
        2. Files that import this file
        3. Same directory files
        4. Test files
        
        Returns:
            {"success": True, "context_files": [...], "content": {...}}
        """
        self.next_step(f"Gathering smart context for {filename}")
        
        try:
            path = self.workspace._resolve(filename)
            if not os.path.exists(path):
                return {"success": False, "error": f"File '{filename}' not found"}
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            related = set()
            
            # Strategy 1: Find imports
            if filename.endswith('.py'):
                # Python imports
                import_pattern = r'^(?:from|import)\s+([\w.]+)'
                for match in re.finditer(import_pattern, content, re.MULTILINE):
                    module = match.group(1).split('.')[0]
                    # Try to find the module file
                    for ext in ['.py', '/__init__.py']:
                        candidate = module.replace('.', '/') + ext
                        if os.path.exists(self.workspace._resolve(candidate)):
                            related.add(candidate)
                            break
            
            elif filename.endswith('.js') or filename.endswith('.ts'):
                # JS/TS imports
                import_patterns = [
                    r"import\s+.*?\s+from\s+['\"](.+?)['\"]",
                    r"import\s*\(\s*['\"](.+?)['\"]\s*\)",
                    r"require\s*\(\s*['\"](.+?)['\"]\s*\)"
                ]
                for pattern in import_patterns:
                    for match in re.finditer(pattern, content):
                        import_path = match.group(1)
                        if import_path.startswith('.'):
                            # Relative import
                            full_path = os.path.normpath(os.path.join(os.path.dirname(path), import_path))
                            for ext in ['', '.js', '.ts', '.jsx', '.tsx', '/index.js']:
                                candidate = full_path + ext
                                if os.path.exists(candidate):
                                    rel = os.path.relpath(candidate, self.workspace.root_dir)
                                    related.add(rel)
                                    break
            
            # Strategy 2: Same directory
            file_dir = os.path.dirname(filename)
            if file_dir:
                try:
                    dir_path = self.workspace._resolve(file_dir)
                    for item in os.listdir(dir_path):
                        if not item.startswith('.') and item != os.path.basename(filename):
                            rel = os.path.join(file_dir, item)
                            if os.path.isfile(self.workspace._resolve(rel)):
                                related.add(rel)
                except:
                    pass
            
            # Strategy 3: Test files
            basename = os.path.splitext(filename)[0]
            test_candidates = [
                f"test_{os.path.basename(filename)}",
                f"{basename}_test.py",
                f"{basename}.test.js",
                f"{basename}.spec.js",
                f"tests/{os.path.basename(filename)}",
            ]
            for candidate in test_candidates:
                if os.path.exists(self.workspace._resolve(candidate)):
                    related.add(candidate)
            
            # Limit depth
            related = set(list(related)[:depth * 3])  # Limit to depth*3 files
            
            # Read all related files
            context_content = {filename: content}
            for rel_file in related:
                try:
                    with open(self.workspace._resolve(rel_file), 'r', encoding='utf-8') as f:
                        context_content[rel_file] = f.read()
                except:
                    pass
            
            UI.step_done(f"Found {len(related)} related files")
            return {
                "success": True,
                "context_files": list(related),
                "content": context_content
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def batch_read(self, files: List[str]) -> Dict:
        """
        Read multiple files efficiently.
        
        Args:
            files: List of filenames to read
            
        Returns:
            {"success": True, "files": {filename: content, ...}} or {"success": False, "error": str}
        """
        self.next_step(f"Reading {len(files)} files")
        
        results = {}
        errors = []
        
        for filename in files:
            try:
                path = self.workspace._resolve(filename)
                if not os.path.exists(path):
                    errors.append(f"'{filename}' not found")
                    continue
                
                with open(path, 'r', encoding='utf-8') as f:
                    results[filename] = f.read()
            except Exception as e:
                errors.append(f"'{filename}': {str(e)}")
        
        if errors and not results:
            return {"success": False, "error": "; ".join(errors)}
        
        UI.step_done(f"Read {len(results)} files" + (f" ({len(errors)} errors)" if errors else ""))
        return {
            "success": True,
            "files": results,
            "errors": errors if errors else None
        }

    def find_and_replace(self, pattern: str, replacement: str, path: str = ".", file_pattern: str = None, dry_run: bool = True) -> Dict:
        """
        Find and replace across multiple files with preview.
        
        Args:
            pattern: Regex pattern to search for
            replacement: Replacement text
            path: Directory to search in
            file_pattern: Optional glob pattern to filter files
            dry_run: If True, only show what would be changed
            
        Returns:
            {"success": True, "changes": [...], "would_change": int} or {"success": False, "error": str}
        """
        import fnmatch
        
        self.next_step(f"Finding '{pattern}' in {path}")
        
        try:
            target = self.workspace._resolve(path)
            if not os.path.isdir(target):
                return {"success": False, "error": f"'{path}' is not a directory"}
            
            changes = []
            
            for root, dirs, filenames in os.walk(target):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for filename in filenames:
                    if filename.startswith('.'):
                        continue
                    
                    if file_pattern and not fnmatch.fnmatch(filename, file_pattern):
                        continue
                    
                    full_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(full_path, self.workspace.root_dir)
                    
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        matches = list(re.finditer(pattern, content, re.MULTILINE))
                        if matches:
                            for match in matches:
                                line_num = content[:match.start()].count('\n') + 1
                                context = content[max(0, match.start()-30):min(len(content), match.end()+30)]
                                changes.append({
                                    "file": rel_path,
                                    "line": line_num,
                                    "match": match.group(),
                                    "context": context
                                })
                            
                            if not dry_run:
                                new_content = re.sub(pattern, replacement, content)
                                with open(full_path, 'w', encoding='utf-8') as f:
                                    f.write(new_content)
                    except Exception as e:
                        UI.step_detail(f"Error reading {rel_path}: {e}")
            
            UI.step_done(f"Found {len(changes)} matches in {len(set(c['file'] for c in changes))} files")
            return {
                "success": True,
                "changes": changes,
                "would_change": len(changes) if dry_run else 0,
                "dry_run": dry_run
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
