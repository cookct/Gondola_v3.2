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
    
    def __init__(self, branch_name="_gondola_shadow"):
        self.branch_name = branch_name
        self.project_root = Path.cwd()
        self._init_branch()
    
    def _init_branch(self):
        """Create hidden branch for state storage if it doesn't exist"""
        try:
            # Check if branch already exists
            result = subprocess.run([
                "git", "show-ref", "--verify", f"refs/heads/{self.branch_name}"
            ], capture_output=True)
            
            if result.returncode == 0:
                # Branch exists, we're good
                return
                
        except FileNotFoundError:
            print("Git not available. Persistence disabled.")
            return
        except Exception as e:
            print(f"Git check failed: {e}")
            return
        
        # Branch doesn't exist, create it with low-level commands
        try:
            # Create initial commit with hash-object and commit-tree
            
            # 1. Create blob for marker file
            marker_content = "This branch stores Gondola's cognitive state\n"
            result = subprocess.run([
                "git", "hash-object", "-w", "--stdin"
            ], input=marker_content.encode(), capture_output=True, check=True)
            blob_hash = result.stdout.decode().strip()
            
            # 2. Create tree object
            result = subprocess.run([
                "git", "mktree"
            ], input=f"100644 blob {blob_hash}	.gondola_necromancer".encode(), 
               capture_output=True, check=True)
            tree_hash = result.stdout.decode().strip()
            
            # 3. Create commit object
            timestamp = str(int(datetime.now().timestamp()))
            commit_msg = "INIT: Necromancer architecture"
            result = subprocess.run([
                "git", "commit-tree", tree_hash, "-m", commit_msg
            ], capture_output=True, check=True)
            commit_hash = result.stdout.decode().strip()
            
            # 4. Create branch reference
            subprocess.run([
                "git", "update-ref", f"refs/heads/{self.branch_name}", commit_hash
            ], check=True)
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else "No error output"
            print(f"Failed to create shadow branch: {error_msg}")
        except Exception as e:
            print(f"Unexpected error creating branch: {e}")

    def checkpoint(self, thought: str, task: str):
        """Create an empty commit with cognitive state using low-level git commands"""
        try:
            timestamp = datetime.now().isoformat()
            commit_msg = f"RESURRECT: {thought} | PENDING: {task} | TIMESTAMP: {timestamp}"
            
            # Get current branch's HEAD commit
            result = subprocess.run([
                "git", "rev-parse", "HEAD"
            ], capture_output=True, check=True)
            current_commit = result.stdout.decode().strip()
            
            # Get the current tree
            result = subprocess.run([
                "git", "rev-parse", "HEAD^{tree}"
            ], capture_output=True, check=True)
            current_tree = result.stdout.decode().strip()
            
            # Create new commit object pointing to same tree
            result = subprocess.run([
                "git", "commit-tree", current_tree, "-p", self.branch_name, "-m", commit_msg
            ], capture_output=True, check=True)
            new_commit = result.stdout.decode().strip()
            
            # Update the shadow branch to point to new commit
            subprocess.run([
                "git", "update-ref", f"refs/heads/{self.branch_name}", new_commit
            ], check=True)
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else "No error output"
            print(f"Checkpoint failed: {error_msg}")
        except Exception as e:
            print(f"Failed to create checkpoint: {e}")

    def get_last_checkpoint(self) -> dict:
        """Parse the last commit message from the shadow branch without checking it out"""
        try:
            # Get the commit hash of the shadow branch
            result = subprocess.run([
                "git", "rev-parse", self.branch_name
            ], capture_output=True, check=True)
            commit_hash = result.stdout.decode().strip()
            
            # Get the commit message
            result = subprocess.run([
                "git", "show", "-s", "--format=%B", commit_hash
            ], capture_output=True, check=True)
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
            error_output = e.stderr.decode() if e.stderr else "No error output"
            print(f"Git operation failed: {error_output}")
            return {"thought": "", "task": "", "message": ""}
        except Exception as e:
            print(f"Failed to get checkpoint: {e}")
            return {"thought": "", "task": "", "message": ""}