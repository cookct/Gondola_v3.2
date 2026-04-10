"""
Base Tools class for Venice AI
"""

from venice.core import UI


class Tools:
    """Base class for all tools"""

    def __init__(self, workspace, memory=None, project_index=None, agent_state=None, **kwargs):
        super().__init__(**kwargs)
        self.workspace = workspace
        self.memory = memory
        self.project_index = project_index
        self.agent_state = agent_state
        self.step_count = 0
        self.total_steps = 0
        self.files_touched = set()  # Track files modified this session

    def set_steps(self, total):
        self.total_steps = total
        self.step_count = 0

    def next_step(self, description):
        self.step_count += 1
        UI.step_start(self.step_count, self.total_steps, description)

    def _track_file(self, filename):
        """Track a file as touched this session"""
        self.files_touched.add(filename)

    def _backup_file(self, path):
        """Create a backup of a file before editing"""
        import os
        import shutil
        from datetime import datetime
        backup_dir = os.path.join(self.workspace.root_dir, '.venice_backups')
        os.makedirs(backup_dir, exist_ok=True)

        filename = os.path.basename(path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}.bak")

        shutil.copy2(path, backup_path)
        return backup_path

    def _calculate_file_hash(self, path):
        """Calculate SHA-256 hash of a file"""
        import hashlib
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _human_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"