"""
Tools package for Venice CLI
"""

from venice.tools.base import Tools
from venice.tools.file_ops import FileOpsMixin
from venice.tools.shell_ops import ShellOpsMixin
from venice.tools.code_ops import CodeOpsMixin


class CombinedTools(FileOpsMixin, ShellOpsMixin, CodeOpsMixin):
    """Combined tools class with all operations"""
    
    def __init__(self, workspace, memory=None):
        # Initialize base class
        super().__init__(workspace, memory)


# Export for convenience
__all__ = ['Tools', 'CombinedTools', 'FileOpsMixin', 'ShellOpsMixin', 'CodeOpsMixin']