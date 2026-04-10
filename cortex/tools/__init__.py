"""
Tools package for Cortex AI
"""

from cortex.tools.base import Tools
from cortex.tools.file_ops import FileOpsMixin
from cortex.tools.shell_ops import ShellOpsMixin
from cortex.tools.code_ops import CodeOpsMixin
from cortex.tools.knowledge_ops import KnowledgeOpsMixin
from cortex.tools.undead_ops import UndeadOpsMixin
from cortex.tools.batch_ops import BatchOpsMixin
from cortex.tools.git_ops import GitOpsMixin
from cortex.tools.web_ops import WebOpsMixin
from cortex.tools.test_ops import TestOpsMixin
from cortex.tools.image_ops import ImageOpsMixin


class CombinedTools(FileOpsMixin, ShellOpsMixin, CodeOpsMixin, UndeadOpsMixin, KnowledgeOpsMixin, BatchOpsMixin, GitOpsMixin, WebOpsMixin, TestOpsMixin, ImageOpsMixin):
    """Combined tools class with all operations"""
    
    def __init__(self, workspace, memory=None, project_index=None, agent_state=None):
        # Initialize base class
        super().__init__(workspace=workspace, memory=memory, project_index=project_index, agent_state=agent_state)


# Export for convenience
__all__ = ['Tools', 'CombinedTools', 'FileOpsMixin', 'ShellOpsMixin', 'CodeOpsMixin', 'BatchOpsMixin', 'GitOpsMixin']