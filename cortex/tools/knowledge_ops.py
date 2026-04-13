"""
Knowledge Operations Mixin for Cortex AI
Handles saving and retrieving knowledge nuggets for AI models.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from cortex.tools.base import Tools

class KnowledgeOpsMixin(Tools):
    """
    Mixin class for knowledge operations.
    Provides methods to save and retrieve knowledge for AI models.
    """

    def __init__(self, workspace, memory=None, project_index=None, **kwargs):
        super().__init__(workspace=workspace, memory=memory, project_index=project_index, **kwargs)
        # Initialize knowledge system after parent classes set workspace
        workspace_path = self.workspace.root_dir if hasattr(self.workspace, 'root_dir') else self.workspace
        self.knowledge_dir = Path(workspace_path) / ".cortex_knowledge"
        self.knowledge_dir.mkdir(exist_ok=True)
        self.knowledge_index = self._load_knowledge_index()

    def _load_knowledge_index(self) -> Dict[str, Dict]:
        """Load the knowledge index from file."""
        index_file = self.knowledge_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_knowledge_index(self):
        """Save the knowledge index to file."""
        index_file = self.knowledge_dir / "index.json"
        try:
            with open(index_file, 'w') as f:
                json.dump(self.knowledge_index, f, indent=2)
        except Exception as e:
            print(f"Error saving knowledge index: {e}")

    def save_knowledge(self, keywords: List[str], content: str, title: Optional[str] = None) -> str:
        """
        Save a knowledge nugget that can be retrieved by keywords.

        Args:
            keywords: List of keywords that trigger this knowledge
            content: The knowledge content/instructions
            title: Optional title for the knowledge entry

        Returns:
            Path to the saved knowledge file
        """
        if not title:
            title = "_".join(keywords[:3]).lower().replace(" ", "_")

        filename = f"{title}.md"
        filepath = self.knowledge_dir / filename
        workspace_path = self.workspace.root_dir if hasattr(self.workspace, 'root_dir') else self.workspace

        # Write the knowledge file
        with open(filepath, 'w') as f:
            f.write(f"# {title.replace('_', ' ').title()}\n\n")
            f.write("Keywords: " + ", ".join(keywords) + "\n\n")
            f.write(content)

        # Update index
        self.knowledge_index[title] = {
            "keywords": keywords,
            "file": str(filepath.relative_to(workspace_path)),
            "title": title
        }
        self._save_knowledge_index()
        
        # Trigger re-index so semantic search can find this knowledge
        if self.project_index:
            try:
                self.project_index.invalidate_file(str(filepath.relative_to(workspace_path)))
                self.project_index.build_index()  # Incremental re-index
            except Exception:
                pass  # Index update is optional

        return str(filepath)

    def get_relevant_knowledge(self, query: str) -> List[Dict]:
        """
        Get knowledge entries relevant to the query.

        Args:
            query: The query string

        Returns:
            List of relevant knowledge entries
        """
        query_lower = query.lower()
        relevant = []
        workspace_path = self.workspace.root_dir if hasattr(self.workspace, 'root_dir') else self.workspace

        for entry in self.knowledge_index.values():
            if any(keyword.lower() in query_lower for keyword in entry["keywords"]):
                filepath = Path(workspace_path) / entry["file"]
                if filepath.exists():
                    try:
                        with open(filepath, 'r') as f:
                            content = f.read()
                        relevant.append({
                            "title": entry["title"],
                            "content": content,
                            "keywords": entry["keywords"]
                        })
                    except Exception:
                        continue

        return relevant

    def list_knowledge(self) -> List[Dict]:
        """List all saved knowledge entries."""
        return list(self.knowledge_index.values())