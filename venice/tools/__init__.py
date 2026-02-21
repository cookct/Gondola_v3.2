"""
Tools package for Venice CLI
"""

from venice.tools.base import Tools
from venice.tools.file_ops import FileOpsMixin
from venice.tools.shell_ops import ShellOpsMixin
from venice.tools.code_ops import CodeOpsMixin
from venice.tools.knowledge_ops import KnowledgeOpsMixin
from venice.tools.undead_ops import UndeadOpsMixin
from venice.tools.batch_ops import BatchOpsMixin
from venice.tools.git_ops import GitOpsMixin
from venice.tools.web_ops import WebOpsMixin
from venice.tools.test_ops import TestOpsMixin
from venice.tools.image_ops import ImageOpsMixin


class CombinedTools(FileOpsMixin, ShellOpsMixin, CodeOpsMixin, UndeadOpsMixin, KnowledgeOpsMixin, BatchOpsMixin, GitOpsMixin, WebOpsMixin, TestOpsMixin, ImageOpsMixin):
    """Combined tools class with all operations"""
    
    def __init__(self, workspace, memory=None, project_index=None, agent_state=None):
        # Initialize base class
        super().__init__(workspace=workspace, memory=memory, project_index=project_index, agent_state=agent_state)


# Export for convenience
__all__ = ['Tools', 'CombinedTools', 'FileOpsMixin', 'ShellOpsMixin', 'CodeOpsMixin', 'BatchOpsMixin', 'GitOpsMixin']