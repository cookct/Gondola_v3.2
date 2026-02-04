"""
Workspace sandbox for secure file operations
"""

import os


class Workspace:
    """Secure workspace for file operations"""

    def __init__(self, root_dir, symlink_handler=None):
        self.root_dir = os.path.abspath(root_dir)
        # Default handler prompts interactively in CLI mode
        self.symlink_handler = symlink_handler or self._default_symlink_prompt
        if not os.path.exists(self.root_dir):
            try:
                os.makedirs(self.root_dir)
            except PermissionError:
                raise PermissionError(f"Cannot create workspace at '{self.root_dir}' - permission denied. Try a different path.")

    def _default_symlink_prompt(self, link_path, real_target, inside_workspace):
        """Default handler: allow internal, prompt for external in CLI"""
        from venice.core import UI
        if inside_workspace:
            return True
        return UI.confirm(f"Security: Tool tried to access symlink pointing outside workspace: {real_target}. Allow?")

    def _resolve(self, path):
        """Resolve path and ensure it's within workspace, with symlink protection"""
        if os.path.isabs(path):
            full_path = os.path.abspath(path)
        else:
            full_path = os.path.abspath(os.path.join(self.root_dir, path))

        # Basic security check - path must be within workspace
        if not full_path.startswith(self.root_dir + os.sep) and full_path != self.root_dir:
            raise ValueError(f"Access denied: '{path}' is outside workspace")

        # Symlink security check
        if os.path.islink(full_path):
            # Get the real target of the symlink
            real_target = os.path.realpath(full_path)
            inside_workspace = real_target.startswith(self.root_dir + os.sep) or real_target == self.root_dir
            
            # Ask the handler whether to allow this symlink
            if not self.symlink_handler(full_path, real_target, inside_workspace):
                raise ValueError(f"Access denied: Symlink '{path}' points outside workspace to '{real_target}'")
            
            # If allowed and following symlinks, return the real path
            return real_target

        return full_path

    def _relative(self, full_path):
        """Get path relative to workspace"""
        return os.path.relpath(full_path, self.root_dir)