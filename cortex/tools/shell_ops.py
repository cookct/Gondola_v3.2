"""
Shell commands, backup, and file management operations for Cortex AI
"""

import os
import shutil
import subprocess
from datetime import datetime

from cortex.core import UI, Colors
from cortex.tools.base import Tools


class ShellOpsMixin(Tools):
    """Mixin for shell commands and file management operations"""

    def __init__(self, workspace, memory=None, project_index=None, **kwargs):
        super().__init__(workspace=workspace, memory=memory, project_index=project_index, **kwargs)

    # ---- File Management ----

    def delete_file(self, filename):
        """Delete a file"""
        self.next_step(f"Deleting {filename}")

        try:
            path = self.workspace._resolve(filename)
            if not os.path.exists(path):
                UI.step_error(f"File not found: {filename}")
                return {"success": False, "error": f"File '{filename}' does not exist"}

            if os.path.isdir(path):
                UI.step_error("Use delete_directory for directories")
                return {"success": False, "error": "Path is a directory, use delete_directory"}

            os.remove(path)
            UI.step_done(f"Deleted {filename}")
            return {"success": True}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def move_file(self, source, destination):
        """Move or rename a file"""
        self.next_step(f"Moving {source} → {destination}")

        try:
            src_path = self.workspace._resolve(source)
            dst_path = self.workspace._resolve(destination)

            if not os.path.exists(src_path):
                UI.step_error(f"Source not found: {source}")
                return {"success": False, "error": f"Source '{source}' does not exist"}

            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.move(src_path, dst_path)

            UI.step_done(f"Moved to {destination}")
            return {"success": True}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def copy_file(self, source, destination):
        """Copy a file"""
        self.next_step(f"Copying {source} → {destination}")

        try:
            src_path = self.workspace._resolve(source)
            dst_path = self.workspace._resolve(destination)

            if not os.path.exists(src_path):
                UI.step_error(f"Source not found: {source}")
                return {"success": False, "error": f"Source '{source}' does not exist"}

            os.makedirs(os.path.dirname(dst_path), exist_ok=True)

            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path)
            else:
                shutil.copy2(src_path, dst_path)

            UI.step_done(f"Copied to {destination}")
            return {"success": True}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def make_directory(self, path):
        """Create a directory"""
        self.next_step(f"Creating directory {path}")

        try:
            full_path = self.workspace._resolve(path)
            os.makedirs(full_path, exist_ok=True)

            UI.step_done(f"Created {path}")
            return {"success": True}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def delete_directory(self, path, recursive=False):
        """Delete a directory"""
        self.next_step(f"Deleting directory {path}")

        try:
            full_path = self.workspace._resolve(path)

            if not os.path.isdir(full_path):
                UI.step_error("Not a directory")
                return {"success": False, "error": "Path is not a directory"}

            if recursive:
                shutil.rmtree(full_path)
            else:
                os.rmdir(full_path)  # Only works if empty

            UI.step_done(f"Deleted {path}")
            return {"success": True}

        except OSError as e:
            if "not empty" in str(e).lower() or "directory not empty" in str(e).lower():
                UI.step_error("Directory not empty. Use recursive=true to delete contents.")
            else:
                UI.step_error(str(e))
            return {"success": False, "error": str(e)}
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    # ---- Shell Commands ----

    def run_command(self, command, timeout=30):
        """Run a shell command with environment awareness (venv, python3 aliases)"""
        self.next_step(f"Running: {command}")

        try:
            # 1. Prepare Environment
            env = os.environ.copy()

            # 2. Inject Venv if it exists in the project root
            venv_path = os.path.expanduser("~/.cortex/litellm_venv")
            if os.path.exists(venv_path):
                venv_bin = os.path.join(venv_path, "bin")
                env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
                env["VIRTUAL_ENV"] = venv_path
                env.pop("PYTHONHOME", None)

            # 3. Handle python -> python3 alias if python doesn't exist
            if "python " in command or command.strip() == "python":
                if not shutil.which("python") and shutil.which("python3"):
                    command = f"alias python=python3 && {command}"

            # Use Popen to stream output
            process = subprocess.Popen(
                command,
                shell=True,
                executable="/bin/bash",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.workspace.root_dir,
                env=env,
                bufsize=1,
                universal_newlines=True
            )

            full_output = []

            # Read output line by line as it happens
            for line in process.stdout:
                UI.print(line, end="")
                full_output.append(line)

            process.wait(timeout=timeout)
            exit_code = process.returncode
            output = "".join(full_output)

            if exit_code == 0:
                UI.step_done(f"Exit code: {exit_code}")
            else:
                UI.step_error(f"Exit code: {exit_code}")

            return {
                "success": exit_code == 0,
                "exit_code": exit_code,
                "stdout": output,
                "stderr": ""
            }

        except subprocess.TimeoutExpired:
            process.kill()
            UI.step_error(f"Command timed out after {timeout}s")
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    # ---- Backup Recovery ----

    def list_backups(self, filename=None):
        """List available backups"""
        self.next_step("Listing backups")

        try:
            backup_dir = os.path.join(self.workspace.root_dir, '.cortex_backups')
            if not os.path.exists(backup_dir):
                UI.step_detail("No backups found")
                UI.step_done()
                return {"success": True, "backups": []}

            backups = []
            for f in sorted(os.listdir(backup_dir), reverse=True):
                if f.endswith('.bak'):
                    if filename is None or filename in f:
                        full_path = os.path.join(backup_dir, f)
                        stat = os.stat(full_path)
                        backups.append({
                            "name": f,
                            "size": self._human_size(stat.st_size),
                            "modified": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        })

            for b in backups[:10]:
                UI.step_detail(f"{b['name']} ({b['size']}, {b['modified']})")
            if len(backups) > 10:
                UI.step_detail(f"{Colors.GREY}... and {len(backups) - 10} more{Colors.RESET}")

            UI.step_done(f"{len(backups)} backups")
            return {"success": True, "backups": backups}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def restore_backup(self, backup_name, target_filename=None):
        """Restore a file from backup"""
        self.next_step(f"Restoring {backup_name}")

        try:
            backup_dir = os.path.join(self.workspace.root_dir, '.cortex_backups')
            backup_path = os.path.join(backup_dir, backup_name)

            if not os.path.exists(backup_path):
                UI.step_error(f"Backup not found: {backup_name}")
                return {"success": False, "error": f"Backup '{backup_name}' does not exist"}

            # Parse original filename from backup name (format: filename.timestamp.bak)
            if target_filename is None:
                # Extract original filename: "app.py.20240115_143022.bak" -> "app.py"
                parts = backup_name.rsplit('.', 2)
                if len(parts) >= 3:
                    target_filename = parts[0]
                else:
                    UI.step_error("Could not determine target filename from backup name")
                    return {"success": False, "error": "Specify target_filename"}

            target_path = self.workspace._resolve(target_filename)

            # Show what we're restoring
            UI.step_detail(f"Restoring to: {target_filename}")

            shutil.copy2(backup_path, target_path)

            UI.step_done(f"Restored {target_filename}")
            return {"success": True, "restored_to": target_filename}

        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}