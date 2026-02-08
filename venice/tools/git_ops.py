"""
Git Operations - Intelligent version control integration
"""

import os
import subprocess
import re
from typing import List, Dict, Optional
from venice.tools.base import Tools
from venice.core import UI


class GitOpsMixin(Tools):
    """Mixin for git operations"""

    def _run_git(self, args: List[str], cwd: str = None) -> tuple:
        """Run git command and return (returncode, stdout, stderr)"""
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                cwd=cwd or self.workspace.root_dir
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return -1, "", "git not found"
        except Exception as e:
            return -1, "", str(e)

    def git_status(self) -> Dict:
        """Get git repository status"""
        self.next_step("Checking git status")
        
        returncode, stdout, stderr = self._run_git(["status", "--porcelain", "-b"])
        
        if returncode != 0:
            return {"success": False, "error": stderr or "Not a git repository"}
        
        # Parse status
        staged = []
        unstaged = []
        untracked = []
        branch = None
        ahead_behind = None
        
        for line in stdout.strip().split('\n'):
            if not line:
                continue
            
            # Branch info line
            if line.startswith('##'):
                parts = line[3:].split('...')
                branch = parts[0]
                if len(parts) > 1:
                    # Parse ahead/behind
                    match = re.search(r'\[ahead (\d+)(?:, behind (\d+))?\]', line)
                    if match:
                        ahead = int(match.group(1))
                        behind = int(match.group(2)) if match.group(2) else 0
                        ahead_behind = {"ahead": ahead, "behind": behind}
                continue
            
            # File status
            if len(line) >= 2:
                index_status = line[0]
                worktree_status = line[1]
                filename = line[3:]
                
                if index_status != ' ':
                    staged.append({"file": filename, "status": index_status})
                elif worktree_status != ' ':
                    unstaged.append({"file": filename, "status": worktree_status})
                else:
                    untracked.append(filename)
        
        UI.step_done(f"Branch: {branch}, {len(staged)} staged, {len(unstaged)} unstaged")
        return {
            "success": True,
            "branch": branch,
            "ahead_behind": ahead_behind,
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
            "is_clean": len(staged) == 0 and len(unstaged) == 0 and len(untracked) == 0
        }

    def git_diff(self, staged: bool = False, file: str = None) -> Dict:
        """Get git diff"""
        self.next_step(f"Getting git diff{' (staged)' if staged else ''}")
        
        args = ["diff"]
        if staged:
            args.append("--staged")
        if file:
            args.append(file)
        
        returncode, stdout, stderr = self._run_git(args)
        
        if returncode != 0:
            return {"success": False, "error": stderr}
        
        # Parse diff stats
        files_changed = []
        current_file = None
        additions = 0
        deletions = 0
        
        for line in stdout.split('\n'):
            if line.startswith('diff --git'):
                if current_file:
                    files_changed.append(current_file)
                current_file = {"additions": 0, "deletions": 0, "chunks": []}
            elif line.startswith('+') and not line.startswith('+++'):
                if current_file:
                    current_file["additions"] += 1
                    additions += 1
            elif line.startswith('-') and not line.startswith('---'):
                if current_file:
                    current_file["deletions"] += 1
                    deletions += 1
            elif line.startswith('@@'):
                if current_file:
                    current_file["chunks"].append(line)
        
        if current_file:
            files_changed.append(current_file)
        
        UI.step_done(f"{len(files_changed)} files, +{additions}/-{deletions}")
        return {
            "success": True,
            "diff": stdout,
            "files_changed": len(files_changed),
            "additions": additions,
            "deletions": deletions,
            "summary": f"+{additions}/-{deletions} in {len(files_changed)} files"
        }

    def git_log(self, n: int = 10, file: str = None, author: str = None) -> Dict:
        """Get git log"""
        self.next_step(f"Getting last {n} commits")
        
        args = [
            "log",
            f"-{n}",
            "--pretty=format:%H|%an|%ae|%ad|%s",
            "--date=short"
        ]
        
        if file:
            args.append("--")
            args.append(file)
        
        if author:
            args.insert(1, f"--author={author}")
        
        returncode, stdout, stderr = self._run_git(args)
        
        if returncode != 0:
            return {"success": False, "error": stderr}
        
        commits = []
        for line in stdout.strip().split('\n'):
            if '|' in line:
                parts = line.split('|', 4)
                if len(parts) >= 5:
                    commits.append({
                        "hash": parts[0][:8],
                        "full_hash": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "date": parts[3],
                        "message": parts[4]
                    })
        
        UI.step_done(f"Found {len(commits)} commits")
        return {
            "success": True,
            "commits": commits,
            "count": len(commits)
        }

    def git_blame(self, filename: str, start_line: int = None, end_line: int = None) -> Dict:
        """Get git blame for file or lines"""
        self.next_step(f"Blaming {filename}")
        
        args = ["blame", "--porcelain"]
        
        if start_line and end_line:
            args.extend(["-L", f"{start_line},{end_line}"])
        
        args.append(filename)
        
        returncode, stdout, stderr = self._run_git(args)
        
        if returncode != 0:
            return {"success": False, "error": stderr}
        
        # Parse porcelain blame output
        lines = []
        current_commit = {}
        
        for line in stdout.split('\n'):
            if line.startswith('\t'):
                # Line content
                content = line[1:]
                lines.append({
                    **current_commit,
                    "content": content
                })
                current_commit = {}
            elif ' ' in line:
                key, value = line.split(' ', 1)
                if key == 'author-time':
                    import datetime
                    value = datetime.datetime.fromtimestamp(int(value)).strftime('%Y-%m-%d')
                current_commit[key] = value
        
        # Group by author
        authors = {}
        for line in lines:
            author = line.get('author', 'Unknown')
            if author not in authors:
                authors[author] = {"lines": 0, "commits": set()}
            authors[author]["lines"] += 1
            authors[author]["commits"].add(line.get('sha', 'unknown'))
        
        # Convert sets to counts
        for author in authors:
            authors[author]["commits"] = len(authors[author]["commits"])
        
        UI.step_done(f"{len(lines)} lines from {len(authors)} authors")
        return {
            "success": True,
            "lines": lines,
            "authors": authors,
            "total_lines": len(lines)
        }

    def git_branch(self) -> Dict:
        """List branches"""
        self.next_step("Listing branches")
        
        returncode, stdout, stderr = self._run_git(["branch", "-vv"])
        
        if returncode != 0:
            return {"success": False, "error": stderr}
        
        branches = []
        current = None
        
        for line in stdout.strip().split('\n'):
            if line.startswith('*'):
                current = line[2:].split()[0]
                branches.append({"name": current, "current": True})
            elif line.strip():
                name = line.strip().split()[0]
                branches.append({"name": name, "current": False})
        
        UI.step_done(f"{len(branches)} branches, current: {current}")
        return {
            "success": True,
            "branches": branches,
            "current": current
        }

    def git_show(self, commit: str = "HEAD", stat: bool = True) -> Dict:
        """Show commit details"""
        self.next_step(f"Showing commit {commit[:8]}")
        
        args = ["show", "--stat" if stat else "--no-patch", commit]
        returncode, stdout, stderr = self._run_git(args)
        
        if returncode != 0:
            return {"success": False, "error": stderr}
        
        UI.step_done("Commit retrieved")
        return {
            "success": True,
            "commit": commit,
            "output": stdout
        }

    def git_stash(self, message: str = None, list_all: bool = False) -> Dict:
        """Stash operations"""
        if list_all:
            self.next_step("Listing stashes")
            returncode, stdout, stderr = self._run_git(["stash", "list"])
            
            if returncode != 0:
                return {"success": False, "error": stderr}
            
            stashes = []
            for line in stdout.strip().split('\n'):
                if line:
                    # Parse: stash@{n}: WIP on branch: message
                    match = re.match(r'stash@\{(\d+)\}: (.+)', line)
                    if match:
                        stashes.append({
                            "index": int(match.group(1)),
                            "message": match.group(2)
                        })
            
            UI.step_done(f"{len(stashes)} stashes")
            return {"success": True, "stashes": stashes}
        
        else:
            self.next_step("Creating stash")
            args = ["stash", "push"]
            if message:
                args.extend(["-m", message])
            
            returncode, stdout, stderr = self._run_git(args)
            
            if returncode != 0:
                return {"success": False, "error": stderr}
            
            UI.step_done("Changes stashed")
            return {"success": True, "message": stdout or "Stashed successfully"}

    def suggest_commit_message(self, files: List[str] = None) -> Dict:
        """Analyze changes and suggest a commit message"""
        self.next_step("Analyzing changes for commit message")
        
        # Get diff stats
        diff_result = self.git_diff(staged=True if not files else False)
        if not diff_result.get("success"):
            return {"success": False, "error": diff_result.get("error")}
        
        additions = diff_result.get("additions", 0)
        deletions = diff_result.get("deletions", 0)
        files_changed = diff_result.get("files_changed", 0)
        
        # Analyze what changed
        diff = diff_result.get("diff", "")
        
        # Look for patterns
        patterns = {
            "test": r'\+.*def test_|\+.*class.*Test',
            "fix": r'fix|bug|error|issue',
            "feature": r'add|new|implement|feature',
            "refactor": r'refactor|clean|simplify',
            "docs": r'doc|comment|readme',
            "config": r'config|setting|\.json|\.yml|\.yaml'
        }
        
        matches = {}
        for category, pattern in patterns.items():
            matches[category] = len(re.findall(pattern, diff, re.IGNORECASE))
        
        # Determine primary type
        primary_type = max(matches, key=matches.get) if matches else "update"
        if matches.get(primary_type, 0) == 0:
            primary_type = "update"
        
        # Build message
        if primary_type == "test":
            message = f"Add tests for {files_changed} files (+{additions}/-{deletions})"
        elif primary_type == "fix":
            message = f"Fix issues in {files_changed} files (+{additions}/-{deletions})"
        elif primary_type == "feature":
            message = f"Add features to {files_changed} files (+{additions}/-{deletions})"
        elif primary_type == "refactor":
            message = f"Refactor {files_changed} files (+{additions}/-{deletions})"
        elif primary_type == "docs":
            message = f"Update documentation (+{additions}/-{deletions})"
        elif primary_type == "config":
            message = f"Update configuration files (+{additions}/-{deletions})"
        else:
            message = f"Update {files_changed} files (+{additions}/-{deletions})"
        
        UI.step_done(f"Suggested: '{message}'")
        return {
            "success": True,
            "suggestion": message,
            "type": primary_type,
            "stats": {
                "files": files_changed,
                "additions": additions,
                "deletions": deletions
            },
            "alternatives": [
                f"{primary_type}: {message}",
                f"[{primary_type.upper()}] {message}",
                message
            ]
        }
