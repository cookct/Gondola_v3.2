"""
File read/write/edit operations for Venice CLI
"""

import os
import re
import shutil
import ast
import json
from datetime import datetime

from venice.core import UI, Colors
from venice.tools.base import Tools


class FileOpsMixin(Tools):
    """Mixin for file read/write/edit operations"""

    def __init__(self, workspace, memory=None, project_index=None, **kwargs):
        super().__init__(workspace=workspace, memory=memory, project_index=project_index, **kwargs)

    # ---- File Reading ----

    def list_files(self, path=".", pattern=None, recursive=True):
        """List files in directory"""
        self.next_step(f"Listing files in {path}")

        try:
            target = self.workspace._resolve(path)
            if not os.path.isdir(target):
                UI.step_error(f"Not a directory: {path}")
                return {"success": False, "error": f"'{path}' is not a directory"}

            files = []
            if recursive:
                for root, dirs, filenames in os.walk(target):
                    # Skip hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for f in filenames:
                        if not f.startswith('.'):
                            rel = os.path.relpath(os.path.join(root, f), self.workspace.root_dir)
                            if pattern is None or pattern in rel:
                                files.append(rel)
            else:
                for item in os.listdir(target):
                    if not item.startswith('.'):
                        full = os.path.join(target, item)
                        rel = os.path.relpath(full, self.workspace.root_dir)
                        if os.path.isdir(full):
                            rel += "/"
                        if pattern is None or pattern in rel:
                            files.append(rel)

            UI.file_tree(files)
            UI.step_done(f"{len(files)} items")
            return {"success": True, "files": files, "count": len(files)}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def read_file(self, filename, start_line=None, end_line=None):
        """Read file contents"""
        self.next_step(f"Reading {filename}")

        try:
            path = self.workspace._resolve(filename)
            if not os.path.exists(path):
                UI.step_error(f"File not found: {filename}")
                return {"success": False, "error": f"File '{filename}' does not exist"}

            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Handle line range
            if start_line is not None or end_line is not None:
                start = (start_line or 1) - 1
                end = end_line or total_lines
                lines = lines[start:end]
                UI.step_detail(f"Lines {start+1}-{end} of {total_lines}")

            content = ''.join(lines)
            file_hash = self._calculate_file_hash(path)

            # Preview
            preview_lines = content.split('\n')[:10]
            for line in preview_lines:
                UI.step_detail(f"{Colors.GREY}{line[:80]}{Colors.RESET}")
            if len(content.split('\n')) > 10:
                UI.step_detail(f"{Colors.GREY}... ({total_lines} lines total){Colors.RESET}")

            UI.step_done(f"{total_lines} lines")
            return {"success": True, "content": content, "lines": total_lines, "hash": file_hash}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def get_file_info(self, filename):
        """Get file metadata"""
        self.next_step(f"Getting info for {filename}")

        try:
            path = self.workspace._resolve(filename)
            if not os.path.exists(path):
                UI.step_error(f"File not found: {filename}")
                return {"success": False, "error": f"File '{filename}' does not exist"}

            stat = os.stat(path)
            info = {
                "success": True,
                "size": stat.st_size,
                "size_human": self._human_size(stat.st_size),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "is_file": os.path.isfile(path),
                "is_dir": os.path.isdir(path),
                "extension": os.path.splitext(filename)[1],
            }

            # Line count for text files
            if os.path.isfile(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        info["line_count"] = sum(1 for _ in f)
                except:
                    pass

            UI.step_detail(f"Size: {info['size_human']}")
            UI.step_detail(f"Modified: {info['modified']}")
            if 'line_count' in info:
                UI.step_detail(f"Lines: {info['line_count']}")

            UI.step_done()
            return info

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def search_content(self, pattern, path=".", file_pattern=None, ignore_case=True):
        """Search for text in files"""
        self.next_step(f"Searching for '{pattern}'")

        try:
            target = self.workspace._resolve(path)
            results = []
            flags = re.IGNORECASE if ignore_case else 0
            regex = re.compile(pattern, flags)

            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for filename in files:
                    if filename.startswith('.'):
                        continue
                    if file_pattern and file_pattern not in filename:
                        continue

                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, self.workspace.root_dir)

                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                            for line_num, line in enumerate(f, 1):
                                if regex.search(line):
                                    results.append({
                                        "file": rel_path,
                                        "line": line_num,
                                        "content": line.strip()[:100]
                                    })
                                if len(results) >= 50:
                                    break
                    except:
                        continue

                    if len(results) >= 50:
                        break
                if len(results) >= 50:
                    break

            for r in results[:20]:
                UI.step_detail(f"{Colors.CYAN}{r['file']}:{r['line']}{Colors.RESET} {r['content'][:60]}")

            if len(results) > 20:
                UI.step_detail(f"{Colors.GREY}... and {len(results) - 20} more matches{Colors.RESET}")

            UI.step_done(f"{len(results)} matches")
            return {"success": True, "matches": results, "count": len(results)}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def search_file_content(self, pattern, path=".", include=None, ignore_case=True, context=0, before=0, after=0):
        """FAST, optimized search powered by ripgrep (rg)"""
        self.next_step(f"Searching for '{pattern}' via ripgrep")

        try:
            # 1. Build rg command
            cmd = ["rg", "--json"]
            
            if ignore_case:
                cmd.append("-i")
            
            # Context settings
            if context > 0:
                cmd.extend(["-C", str(context)])
            if before > 0:
                cmd.extend(["-B", str(before)])
            if after > 0:
                cmd.extend(["-A", str(after)])
                
            # Include pattern
            if include:
                cmd.extend(["-g", include])
                
            # Pattern and path
            cmd.append(pattern)
            cmd.append(self.workspace._resolve(path))
            
            # 2. Run ripgrep
            import subprocess
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 2: # Error
                UI.step_error(result.stderr)
                return {"success": False, "error": result.stderr}
                
            # 3. Parse JSON output
            import json
            matches = []
            
            for line in result.stdout.splitlines():
                if not line: continue
                try:
                    data = json.loads(line)
                    if data.get('type') == 'match':
                        match_data = data['data']
                        matches.append({
                            "file": os.path.relpath(match_data['path']['text'], self.workspace.root_dir),
                            "line": match_data['line_number'],
                            "content": match_data['lines']['text'].strip(),
                            "context": [] # Simplified for now
                        })
                    elif data.get('type') == 'context':
                        # Context lines (if requested)
                        ctx_data = data['data']
                        if matches:
                            matches[-1]["context"].append({
                                "line": ctx_data['line_number'],
                                "content": ctx_data['lines']['text'].strip()
                            })
                except: continue
                
                # Safety cap
                if len(matches) >= 100: break
                
            # 4. Display & Return
            for m in matches[:10]:
                UI.step_detail(f"{Colors.CYAN}{m['file']}:{m['line']}{Colors.RESET} {m['content'][:60]}")
                
            if len(matches) > 10:
                UI.step_detail(f"{Colors.GREY}... and {len(matches) - 10} more matches{Colors.RESET}")
                
            UI.step_done(f"{len(matches)} matches")
            return {"success": True, "matches": matches, "count": len(matches)}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    # ---- File Writing ----

    def _verify_syntax(self, filename, content):
        """Internal helper to verify syntax before saving"""
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.py':
            try:
                ast.parse(content)
            except SyntaxError as e:
                return f"Syntax Error: {e.msg} (line {e.lineno})"
        elif ext == '.json':
            try:
                json.loads(content)
            except Exception as e:
                return f"Invalid JSON: {str(e)}"
        return None

    def write_file(self, filename, content):
        """Create or overwrite a file with automatic syntax verification"""
        self.next_step(f"Writing {filename}")

        try:
            path = self.workspace._resolve(filename)
            
            # Verify syntax before writing
            syntax_error = self._verify_syntax(filename, content)
            if syntax_error:
                UI.step_error(f"Write rejected: {syntax_error}")
                return {
                    "success": False,
                    "error": f"{syntax_error}. File NOT saved. Fix your code and try again."
                }

            os.makedirs(os.path.dirname(path), exist_ok=True)
            is_new = not os.path.exists(path)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Phase 5: Trigger background diagnostics
            if filename.endswith(".py"):
                import subprocess
                diag_path = os.path.join(self.workspace.root_dir, ".gondola_diagnostics.json")
                cmd = f"ruff check --format json {path} > {diag_path} 2>/dev/null &"
                subprocess.Popen(cmd, shell=True)

            lines = content.count('\n') + 1
            action = "Created" if is_new else "Wrote"

            UI.step_detail(f"{action} {lines} lines")
            UI.step_done(f"{action} {filename}")
            self._track_file(filename)
            return {"success": True, "action": action.lower(), "lines": lines}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def _normalize_whitespace(self, text):
        """Normalize whitespace for fuzzy matching"""
        # Replace tabs with spaces, collapse multiple spaces
        return re.sub(r'[ \t]+', ' ', text)

    def _find_fuzzy_match(self, content, search_text):
        """Find text with whitespace-normalized matching, return actual matched text"""
        # First try exact match
        if search_text in content:
            return search_text, content.find(search_text)

        # Try normalized matching
        norm_search = self._normalize_whitespace(search_text)
        lines = content.split('\n')
        search_lines = search_text.split('\n')

        # Slide through content looking for normalized match
        for i in range(len(lines) - len(search_lines) + 1):
            chunk = '\n'.join(lines[i:i + len(search_lines)])
            if self._normalize_whitespace(chunk) == norm_search:
                # Found it - return the actual text from the file
                start_pos = len('\n'.join(lines[:i])) + (1 if i > 0 else 0)
                return chunk, start_pos

        return None, -1

    def edit_file(self, filename, old_text, new_text, occurrence=1, expected_hash=None, dry_run=False):
        """Laser-targeted edit with strict matching and automatic verification"""
        self.next_step(f"Editing {filename}")

        try:
            path = self.workspace._resolve(filename)
            if not os.path.exists(path):
                return {"success": False, "error": f"File '{filename}' does not exist"}

            # Read current content
            with open(path, 'r', encoding='utf-8') as f:
                original = f.read()

            # 1. Strict Uniqueness Check
            matches = original.count(old_text)
            
            if matches == 0:
                # Try fuzzy matching as a fallback (normalized whitespace)
                actual_old_text, match_pos = self._find_fuzzy_match(original, old_text)
                if actual_old_text is None:
                    UI.step_error("Search block not found in file")
                    return {
                        "success": False, 
                        "error": "The <search> block provided does not exist in the file exactly as written. Verify whitespace and context lines."
                    }
                old_text_to_replace = actual_old_text
            else:
                old_text_to_replace = old_text

            # 2. Prevent ambiguous edits
            total_matches = original.count(old_text_to_replace)
            if total_matches > 1 and occurrence != 0:
                UI.step_error(f"Ambiguous edit: found {total_matches} matches")
                return {
                    "success": False,
                    "error": f"Found {total_matches} matches for the search block. Please provide more context lines (before/after) to make the search unique."
                }

            # 3. Create backup
            backup_path = self._backup_file(path)
            
            # 4. Perform replacement
            if occurrence == 0:
                new_content = original.replace(old_text_to_replace, new_text)
                replaced_count = total_matches
            else:
                new_content = original.replace(old_text_to_replace, new_text, 1)
                replaced_count = 1

            # 5. AUTOMATIC VERIFICATION
            syntax_error = self._verify_syntax(filename, new_content)
            if syntax_error:
                UI.step_error("Edit rejected: " + syntax_error)
                return {
                    "success": False,
                    "error": f"{syntax_error}. Your edit was NOT saved to protect the file. Fix indentation/syntax and try again."
                }

            # Show diff
            UI.diff(original.splitlines(), new_content.splitlines(), filename)

            if dry_run:
                UI.step_done("Dry run complete")
                return {"success": True, "dry_run": True}

            # Save
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # Phase 5: Trigger background diagnostics
            if filename.endswith(".py"):
                import subprocess
                diag_path = os.path.join(self.workspace.root_dir, ".gondola_diagnostics.json")
                cmd = f"ruff check --format json {path} > {diag_path} 2>/dev/null &"
                subprocess.Popen(cmd, shell=True)

            UI.step_done(f"Successfully applied edit ({replaced_count} replacement)")
            self._track_file(filename)
            return {"success": True, "replaced": replaced_count}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def replace_lines(self, filename, start_line, end_line, new_content, expected_hash=None, dry_run=False):
        """Replace specific lines in a file (more reliable than text matching)"""
        self.next_step(f"Replacing lines {start_line}-{end_line} in {filename}")

        try:
            path = self.workspace._resolve(filename)
            if not os.path.exists(path):
                UI.step_error(f"File not found: {filename}")
                return {"success": False, "error": f"File '{filename}' does not exist"}

            # Check hash if provided
            if expected_hash:
                current_hash = self._calculate_file_hash(path)
                if current_hash != expected_hash:
                    UI.step_error(f"Hash mismatch! Expected {expected_hash[:8]}..., got {current_hash[:8]}...")
                    return {
                        "success": False, 
                        "error": "File changed since last read (hash mismatch). Please read again.",
                        "current_hash": current_hash
                    }

            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            total_lines = len(lines)
            if start_line < 1 or end_line > total_lines:
                UI.step_error(f"Line range {start_line}-{end_line} out of bounds (file has {total_lines} lines)")
                return {"success": False, "error": f"Line range out of bounds (1-{total_lines})"}

            # Create backup
            backup_path = self._backup_file(path)
            UI.step_detail(f"{Colors.GREY}Backup: {os.path.basename(backup_path)}{Colors.RESET}")

            # Show what's being replaced
            old_content = ''.join(lines[start_line-1:end_line])
            UI.step_detail(f"{Colors.RED}Removing lines {start_line}-{end_line}:{Colors.RESET}")
            for i, line in enumerate(lines[start_line-1:end_line][:5], start=start_line):
                UI.step_detail(f" {Colors.RED}- {i}: {line.rstrip()[:60]}{Colors.RESET}")
            if end_line - start_line + 1 > 5:
                UI.step_detail(f" {Colors.GREY}... and {end_line - start_line - 4} more lines{Colors.RESET}")

            # Build new content
            new_lines = new_content.split('\n')
            # Ensure each line ends with newline
            new_lines = [line + '\n' if not line.endswith('\n') else line for line in new_lines]
            # Fix last line if original didn't have trailing newline
            if new_lines and lines and not lines[-1].endswith('\n'):
                new_lines[-1] = new_lines[-1].rstrip('\n')

            UI.step_detail(f"{Colors.GREEN}Adding {len(new_lines)} new lines:{Colors.RESET}")
            for i, line in enumerate(new_lines[:5], start=start_line):
                UI.step_detail(f" {Colors.GREEN}+ {i}: {line.rstrip()[:60]}{Colors.RESET}")
            if len(new_lines) > 5:
                UI.step_detail(f"{Colors.GREY}... and {len(new_lines) - 5} more lines{Colors.RESET}")

            # Perform replacement
            result_lines = lines[:start_line-1] + new_lines + lines[end_line:]
            new_content_str = ''.join(result_lines)

            # AUTOMATIC VERIFICATION
            syntax_error = self._verify_syntax(filename, new_content_str)
            if syntax_error:
                UI.step_error("Replacement rejected: " + syntax_error)
                return {
                    "success": False,
                    "error": f"{syntax_error}. Your changes were NOT saved. Please check line numbers and indentation."
                }

            if dry_run:
                UI.diff([''.join(lines)], [new_content_str], filename)
                UI.step_done("Dry run completed (no changes made)")
                return {
                    "success": True, 
                    "dry_run": True,
                    "lines_removed": end_line - start_line + 1,
                    "lines_added": len(new_lines)
                }

            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content_str)

            lines_removed = end_line - start_line + 1
            lines_added = len(new_lines)
            UI.step_done(f"Replaced {lines_removed} lines with {lines_added} lines")
            self._track_file(filename)

            return {
                "success": True,
                "lines_removed": lines_removed,
                "lines_added": lines_added,
                "new_total_lines": len(result_lines)
            }

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def insert_at_line(self, filename, line_number, content):
        """Insert content at a specific line"""
        self.next_step(f"Inserting at line {line_number} in {filename}")

        try:
            path = self.workspace._resolve(filename)
            if not os.path.exists(path):
                UI.step_error(f"File not found: {filename}")
                return {"success": False, "error": f"File '{filename}' does not exist"}

            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Insert
            idx = max(0, min(line_number - 1, len(lines)))
            new_lines = content.split('\n')

            original = lines.copy()
            for i, new_line in enumerate(new_lines):
                lines.insert(idx + i, new_line + '\n')

            # Show diff
            UI.diff([''.join(original)], [''.join(lines)], filename)

            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            UI.step_done(f"Inserted {len(new_lines)} lines")
            return {"success": True, "inserted_lines": len(new_lines)}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def delete_lines(self, filename, start_line, end_line=None):
        """Delete lines from a file"""
        end_line = end_line or start_line
        self.next_step(f"Deleting lines {start_line}-{end_line} from {filename}")

        try:
            path = self.workspace._resolve(filename)
            if not os.path.exists(path):
                UI.step_error(f"File not found: {filename}")
                return {"success": False, "error": f"File '{filename}' does not exist"}

            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            original = lines.copy()
            del lines[start_line-1:end_line]

            # Show diff
            UI.diff([''.join(original)], [''.join(lines)], filename)

            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            deleted = end_line - start_line + 1
            UI.step_done(f"Deleted {deleted} lines")
            return {"success": True, "deleted_lines": deleted}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def append_to_file(self, filename, content):
        """Append content to end of file"""
        self.next_step(f"Appending to {filename}")

        try:
            path = self.workspace._resolve(filename)

            with open(path, 'a', encoding='utf-8') as f:
                f.write(content)

            lines = content.count('\n') + 1
            UI.step_detail(f"Added {lines} lines to end of file")
            UI.step_done()
            return {"success": True, "appended_lines": lines}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}