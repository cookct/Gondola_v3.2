import subprocess
import json
from datetime import datetime
from pathlib import Path
import os

class PersistenceManager:
    """Manages cognitive state persistence using a hidden git branch.
    
    Uses low-level git commands (commit-tree, hash-object) to avoid
    checking out the shadow branch and clobbering the working directory.
    """
    
    def __init__(self, branch_name="_gondola_shadow", project_root=None):
        self.branch_name = branch_name
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd()
        self._init_branch()
    
    def _init_branch(self):
        """Create hidden branch for state storage if it doesn't exist"""
        try:
            # Check if we're in a git repository
            result = subprocess.run([
                "git", "rev-parse", "--is-inside-work-tree"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode != 0:
                # Not a git repo, don't auto-init to avoid cluttering user space
                # unless explicitly allowed? For now, just skip.
                return

            # Check if branch already exists
            result = subprocess.run([
                "git", "show-ref", "--verify", f"refs/heads/{self.branch_name}"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode == 0:
                # Branch exists, we're good
                return
                
        except FileNotFoundError:
            return
        except Exception:
            return
        
        # Branch doesn't exist, create it with low-level commands
        try:
            # 1. Create blob for marker file
            marker_content = "This branch stores Gondola's cognitive state\n"
            result = subprocess.run([
                "git", "hash-object", "-w", "--stdin"
            ], input=marker_content, capture_output=True, text=True, check=True, cwd=self.project_root)
            blob_hash = result.stdout.strip()
            
            # 2. Create tree object
            result = subprocess.run([
                "git", "mktree"
            ], input=f"100644 blob {blob_hash}\t.gondola_necromancer", 
               capture_output=True, text=True, check=True, cwd=self.project_root)
            tree_hash = result.stdout.strip()
            
            # 3. Create commit object
            commit_msg = "INIT: Necromancer architecture"
            result = subprocess.run([
                "git", "commit-tree", tree_hash, "-m", commit_msg
            ], capture_output=True, text=True, check=True, cwd=self.project_root)
            commit_hash = result.stdout.strip()
            
            # 4. Create branch reference
            subprocess.run([
                "git", "update-ref", f"refs/heads/{self.branch_name}", commit_hash
            ], check=True, text=True, cwd=self.project_root)
            
        except Exception:
            pass

    def checkpoint(self, thought: str, task: str):
        """Create an empty commit with cognitive state using low-level git commands"""
        try:
            timestamp = datetime.now().isoformat()
            commit_msg = f"RESURRECT: {thought} | PENDING: {task} | TIMESTAMP: {timestamp}"
            
            # Check if branch exists
            result = subprocess.run([
                "git", "rev-parse", "--verify", self.branch_name
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode != 0:
                # Branch doesn't exist, try to init
                self._init_branch()
                # Re-verify
                result = subprocess.run([
                    "git", "rev-parse", "--verify", self.branch_name
                ], capture_output=True, text=True, cwd=self.project_root)
                if result.returncode != 0:
                    return

            # Get current HEAD tree to snapshot the actual project state
            # This allows "git diff" to actually measure divergence later
            try:
                result = subprocess.run([
                    "git", "rev-parse", "HEAD^{tree}"
                ], capture_output=True, text=True, check=True, cwd=self.project_root)
                current_tree = result.stdout.strip()
            except subprocess.CalledProcessError:
                # Fallback if no HEAD (empty repo), use the branch's existing tree
                result = subprocess.run([
                    "git", "rev-parse", f"{self.branch_name}^{{tree}}"
                ], capture_output=True, text=True, check=True, cwd=self.project_root)
                current_tree = result.stdout.strip()
            
            # Create new commit object pointing to same tree but with shadow branch as parent
            result = subprocess.run([
                "git", "commit-tree", current_tree, "-p", self.branch_name, "-m", commit_msg
            ], capture_output=True, text=True, check=True, cwd=self.project_root)
            new_commit = result.stdout.strip()
            
            # Update the shadow branch to point to new commit
            subprocess.run([
                "git", "update-ref", f"refs/heads/{self.branch_name}", new_commit
            ], check=True, text=True, cwd=self.project_root)
            
        except Exception:
            pass

    def get_last_checkpoint(self) -> dict:
        """Parse the last commit message from the shadow branch without checking it out"""
        try:
            # Get the commit hash of the shadow branch
            result = subprocess.run([
                "git", "rev-parse", self.branch_name
            ], capture_output=True, text=True, check=True, cwd=self.project_root)
            commit_hash = result.stdout.strip()
            
            # Get the commit message
            result = subprocess.run([
                "git", "show", "-s", "--format=%B", commit_hash
            ], capture_output=True, text=True, check=True, cwd=self.project_root)
            message = result.stdout.strip()
            
            # Parse message
            if "RESURRECT:" in message and "PENDING:" in message:
                parts = message.split("|")
                thought = parts[0].replace("RESURRECT:", "").strip()
                task = parts[1].replace("PENDING:", "").strip()
                return {
                    "thought": thought, 
                    "task": task, 
                    "message": message
                }
            return {"thought": "", "task": "", "message": message}
            
        except subprocess.CalledProcessError as e:
            # If text=True, e.stderr is already a string
            error_output = e.stderr if e.stderr else "No error output"
            # Silently fail if branch doesn't exist yet
            return {"thought": "", "task": "", "message": ""}
        except Exception as e:
            # print(f"Failed to get checkpoint: {e}")
            return {"thought": "", "task": "", "message": ""}