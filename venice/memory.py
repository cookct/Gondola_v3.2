"""
Memory system for persistent storage across sessions
"""

import os
import json
from datetime import datetime


class Memory:
    """Persistent memory across sessions"""

    def __init__(self, workspace_root):
        self.memory_file = os.path.join(workspace_root, '.venice_memory.json')
        self.data = self._load()

    def _load(self):
        """Load memory from file"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self._default()
        return self._default()

    def _default(self):
        return {
            "project_notes": [],  # Important things to remember
            "session_history": [],  # Summary of past sessions
            "key_files": [],  # Files frequently worked on
            "user_preferences": {},  # Learned preferences
        }

    def save(self):
        """Save memory to file"""
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)

    def add_note(self, note):
        """Add a project note"""
        entry = {
            "note": note,
            "timestamp": datetime.now().isoformat()
        }
        self.data["project_notes"].append(entry)
        # Keep last 50 notes
        self.data["project_notes"] = self.data["project_notes"][-50:]
        self.save()

    def add_session_summary(self, summary, files_touched):
        """Record a session summary"""
        entry = {
            "summary": summary,
            "files": files_touched,
            "timestamp": datetime.now().isoformat()
        }
        self.data["session_history"].append(entry)
        # Keep last 20 sessions
        self.data["session_history"] = self.data["session_history"][-20:]

        # Update key files
        for f in files_touched:
            if f not in self.data["key_files"]:
                self.data["key_files"].append(f)
            self.data["key_files"] = self.data["key_files"][-30:]

        self.save()

    def set_preference(self, key, value):
        """Set a user preference"""
        self.data["user_preferences"][key] = value
        self.save()

    def get_context(self):
        """Generate context string for system prompt"""
        lines = []

        if self.data["project_notes"]:
            lines.append("## PROJECT NOTES (things to remember):")
            for note in self.data["project_notes"][-10:]:
                lines.append(f"- {note['note']}")
            lines.append("")

        if self.data["session_history"]:
            lines.append("## RECENT SESSIONS:")
            for session in self.data["session_history"][-5:]:
                date = session['timestamp'][:10]
                lines.append(f"- [{date}] {session['summary']}")
                if session.get('files'):
                    lines.append(f" Files: {', '.join(session['files'][:5])}")
            lines.append("")

        if self.data["key_files"]:
            lines.append(f"## KEY FILES: {', '.join(self.data['key_files'][-10:])}")
            lines.append("")

        if self.data["user_preferences"]:
            lines.append("## USER PREFERENCES:")
            for k, v in self.data["user_preferences"].items():
                lines.append(f"- {k}: {v}")
            lines.append("")

        return "\n".join(lines) if lines else ""

    def clear_notes(self):
        """Clear all project notes"""
        self.data["project_notes"] = []
        self.save()