"""
Agent State - Session state tracking to prevent infinite loops.

Tracks what the agent has done during a session to:
- Prevent reading the same file multiple times
- Detect loop patterns
- Track progress toward task completion
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from collections import Counter


@dataclass
class FileReadRecord:
    """Record of a file read operation."""
    filepath: str
    content_hash: str
    timestamp: float
    line_count: int
    turn: int = 0
    full_hash: Optional[str] = None


@dataclass
class ToolCallRecord:
    """Record of a tool call."""
    tool_name: str
    args_hash: str
    timestamp: float
    result_summary: str


@dataclass
class AgentState:
    """
    Tracks agent state during a single task session.

    Used to:
    - Detect duplicate file reads
    - Detect tool call loops
    - Track turn count
    - Monitor task progress
    """

    # Session info
    task_description: str = ""
    model_id: str = ""
    session_start: float = field(default_factory=time.time)

    # Turn tracking
    turn_count: int = 0
    max_turns: int = 20

    # File tracking
    files_read: Dict[str, FileReadRecord] = field(default_factory=dict)
    files_written: Set[str] = field(default_factory=set)
    files_edited: Set[str] = field(default_factory=set)

    # Tool tracking
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    tool_call_counts: Counter = field(default_factory=Counter)

    # Loop detection
    recent_actions: List[str] = field(default_factory=list)  # Last 10 action signatures
    MAX_RECENT_ACTIONS: int = 10

    # Task progress
    task_phase: str = "exploring"  # exploring, planning, acting, completing
    done_called: bool = False

    # Failed tool tracking
    failed_tools: List[Dict[str, Any]] = field(default_factory=list)  # Track tools that returned errors

    # Staging area for multi-file transactions
    staged_changes: Dict[str, str] = field(default_factory=dict)  # filepath -> new_content
    transaction_active: bool = False

    # EXPLORATION BUDGET: Limit exploration for cheap models
    exploration_budget: int = 8  # Max exploration actions before requiring action/done
    exploration_count: int = 0   # Current exploration action count
    last_productive_turn: int = 0  # Last turn where a write/edit/done occurred

    # REASONING ENFORCEMENT: Track if model is explaining itself
    last_response_had_text: bool = False  # Did last response include explanation text?
    silent_tool_calls: int = 0  # Consecutive tool calls without explanation

    def start_transaction(self):
        """Start a new multi-file transaction."""
        self.staged_changes.clear()
        self.transaction_active = True

    def stage_change(self, filepath: str, content: str):
        """Stage a change to a file."""
        self.staged_changes[filepath] = content

    def commit_transaction(self):
        """Commit all staged changes."""
        self.staged_changes.clear()
        self.transaction_active = False

    def rollback_transaction(self):
        """Rollback all staged changes."""
        self.staged_changes.clear()
        self.transaction_active = False

    def record_turn(self) -> int:
        """Increment and return turn count."""
        self.turn_count += 1
        return self.turn_count

    def record_file_read(self, filepath: str, content: str, full_hash: str = None) -> Optional[str]:
        """
        Record a file read. Returns cached content hash if file was already read.
        """
        content_hash = hashlib.md5(content.encode()[:5000]).hexdigest()[:12]

        if filepath in self.files_read:
            prev = self.files_read[filepath]
            if prev.content_hash == content_hash:
                # Same file, same content - this is a duplicate read
                return f"DUPLICATE: You already read this file at turn {prev.turn}. Content unchanged."
            else:
                # File changed since last read
                self.files_read[filepath] = FileReadRecord(
                    filepath=filepath,
                    content_hash=content_hash,
                    timestamp=time.time(),
                    line_count=len(content.split('\n')),
                    turn=self.turn_count,
                    full_hash=full_hash
                )
                return None

        self.files_read[filepath] = FileReadRecord(
            filepath=filepath,
            content_hash=content_hash,
            timestamp=time.time(),
            line_count=len(content.split('\n')),
            turn=self.turn_count,
            full_hash=full_hash
        )
        return None

    def get_last_read_turn(self, filepath: str) -> Optional[int]:
        """Get the turn number when a file was last read."""
        if filepath in self.files_read:
            return self.files_read[filepath].turn
        return None

    def file_modified_externally(self, filepath: str, current_hash: Optional[str]) -> bool:
        """Check if a file was modified externally since it was last read."""
        if filepath not in self.files_read:
            return False
            
        last_read = self.files_read[filepath]
        if not last_read.full_hash or not current_hash:
            return False
            
        return last_read.full_hash != current_hash

    def record_file_write(self, filepath: str):
        """Record a file write."""
        self.files_written.add(filepath)
        # Writing invalidates previous read
        if filepath in self.files_read:
            del self.files_read[filepath]

    def record_file_edit(self, filepath: str):
        """Record a file edit."""
        self.files_edited.add(filepath)
        # Editing invalidates previous read
        if filepath in self.files_read:
            del self.files_read[filepath]

    def record_tool_call(self, tool_name: str, args: Dict[str, Any], result: Any) -> Optional[str]:
        """
        Record a tool call. Returns warning if loop detected.
        """
        # Create signature for this call
        args_str = str(sorted(args.items()))
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
        action_sig = f"{tool_name}:{args_hash}"

        # Check for exact duplicate in recent actions
        if action_sig in self.recent_actions:
            return f"WARNING: You already made this exact call ({tool_name}). Consider a different approach."

        # Record the call
        result_summary = str(result)[:100] if result else ""
        self.tool_calls.append(ToolCallRecord(
            tool_name=tool_name,
            args_hash=args_hash,
            timestamp=time.time(),
            result_summary=result_summary
        ))
        self.tool_call_counts[tool_name] += 1

        # Update recent actions (sliding window)
        self.recent_actions.append(action_sig)
        if len(self.recent_actions) > self.MAX_RECENT_ACTIONS:
            self.recent_actions.pop(0)

        return None

    def record_done(self, summary: str):
        """Record that done() was called."""
        self.done_called = True
        self.task_phase = "completed"

    def record_tool_failure(self, tool_name: str, args: Dict[str, Any], error: str):
        """Record a tool that returned an error."""
        self.failed_tools.append({
            "tool": tool_name,
            "args": args,
            "error": error,
            "turn": self.turn_count,
            "timestamp": time.time()
        })

    def get_unaddressed_failures(self) -> List[Dict[str, Any]]:
        """Get list of tool failures from the current session."""
        return self.failed_tools

    def has_recent_failures(self) -> bool:
        """Check if there are any tool failures this session."""
        return len(self.failed_tools) > 0

    def clear_failures(self):
        """Clear failure tracking (e.g., after user acknowledges)."""
        self.failed_tools.clear()

    def generate_learning(self, done_summary: str) -> Optional[Dict[str, Any]]:
        """
        Generate knowledge from a completed task for auto-learning.
        Returns None if not worth saving (no file changes, or too simple).
        """
        # Only learn from tasks that made file changes
        if not self.files_written and not self.files_edited:
            return None

        # Skip trivial tasks (less than 2 turns)
        if self.turn_count < 2:
            return None

        # Extract keywords from task description and file paths
        keywords = set()

        # Keywords from task description
        if self.task_description:
            # Extract meaningful words (skip common words)
            stop_words = {'a', 'an', 'the', 'to', 'in', 'for', 'of', 'and', 'or', 'is', 'it', 'this', 'that', 'with', 'on', 'at', 'by', 'from', 'as', 'be', 'was', 'are', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'i', 'you', 'we', 'they', 'he', 'she', 'me', 'my', 'your', 'our', 'their', 'add', 'make', 'create', 'update', 'change', 'please', 'want', 'need', 'like', 'help'}
            words = self.task_description.lower().replace(',', ' ').replace('.', ' ').split()
            for word in words:
                if len(word) > 2 and word not in stop_words:
                    keywords.add(word)

        # Keywords from file paths
        all_files = list(self.files_written) + list(self.files_edited)
        for filepath in all_files:
            # Extract directory names and file name parts
            parts = filepath.replace('\\', '/').split('/')
            for part in parts:
                # Get name without extension
                name = part.rsplit('.', 1)[0] if '.' in part else part
                if len(name) > 2:
                    keywords.add(name.lower())
                # Also add extension type
                if '.' in part:
                    ext = part.rsplit('.', 1)[1].lower()
                    keywords.add(ext)

        # Generate a title from the task
        title_words = []
        if self.task_description:
            # Take first few meaningful words
            for word in self.task_description.split()[:6]:
                clean = ''.join(c for c in word if c.isalnum())
                if clean and len(clean) > 1:
                    title_words.append(clean.lower())
        title = '_'.join(title_words[:4]) if title_words else f"task_{int(time.time())}"

        # Build the knowledge content
        content_lines = [
            f"## Task",
            f"{self.task_description}",
            "",
            f"## Files Modified",
        ]
        for f in sorted(all_files):
            content_lines.append(f"- `{f}`")

        content_lines.extend([
            "",
            f"## What Was Done",
            done_summary,
            "",
            f"## Navigation Hints",
            f"- This task involved {len(all_files)} file(s)",
            f"- Completed in {self.turn_count} turns",
        ])

        # Add file-type specific hints
        css_files = [f for f in all_files if f.endswith('.css')]
        js_files = [f for f in all_files if f.endswith('.js')]
        py_files = [f for f in all_files if f.endswith('.py')]
        html_files = [f for f in all_files if f.endswith('.html')]

        if css_files:
            content_lines.append(f"- CSS styling in: {', '.join(css_files)}")
        if js_files:
            content_lines.append(f"- JavaScript logic in: {', '.join(js_files)}")
        if py_files:
            content_lines.append(f"- Python code in: {', '.join(py_files)}")
        if html_files:
            content_lines.append(f"- HTML templates in: {', '.join(html_files)}")

        return {
            "title": title,
            "keywords": list(keywords),
            "content": '\n'.join(content_lines),
            "files": all_files,
            "turns": self.turn_count
        }

    def detect_loop_pattern(self) -> Optional[str]:
        """
        Detect if the agent is stuck in a loop pattern.
        Returns warning message if loop detected.
        """
        # Disable loop detection for Claude and GLM models
        if "claude" in self.model_id.lower() or "glm" in self.model_id.lower():
            return None

        # Check for exploration loops earlier (after just 4 calls)
        if len(self.tool_calls) >= 4:
            # Check if last 2 calls repeat a pattern from earlier
            recent_2 = [t.tool_name for t in self.tool_calls[-2:]]
            earlier_2 = [t.tool_name for t in self.tool_calls[-4:-2]]
            
            if recent_2 == earlier_2:
                # Same tool types repeating - likely a loop
                return (
                    "LOOP DETECTED: You're repeating the same types of actions. "
                    "STOP exploring and call done() NOW with your response."
                )

        if len(self.tool_calls) >= 6:
            # Check if last 3 calls repeat a pattern from earlier (exact match)
            recent_3 = [f"{t.tool_name}:{t.args_hash}" for t in self.tool_calls[-3:]]
            earlier_3 = [f"{t.tool_name}:{t.args_hash}" for t in self.tool_calls[-6:-3]]

            if recent_3 == earlier_3:
                return (
                    "EXACT LOOP DETECTED: You're repeating the exact same sequence. "
                    "You MUST call done() NOW with your response."
                )

        # Check for excessive reads without action - lowered threshold
        read_count = self.tool_call_counts.get('read_file', 0)
        search_count = self.tool_call_counts.get('search_content', 0)
        list_count = self.tool_call_counts.get('list_files', 0)
        exploration_count = read_count + search_count + list_count
        write_count = self.tool_call_counts.get('write_file', 0) + self.tool_call_counts.get('edit_file', 0)
        done_count = self.tool_call_counts.get('done', 0)

        # If we've done 15+ exploration actions without any writes or done, warn
        if exploration_count >= 15 and write_count == 0 and done_count == 0:
            return (
                f"EXPLORATION LOOP: You've done {exploration_count} exploration actions "
                f"(reads/searches/lists) without making changes or completing. "
                "Call done() NOW with your findings."
            )

        return None

    def get_progress_summary(self) -> str:
        """Get a summary of current progress for checkpoint injection."""
        lines = [f"Progress after {self.turn_count} turns:"]

        if self.files_read:
            lines.append(f"- Files read: {len(self.files_read)}")
        if self.files_written:
            lines.append(f"- Files written: {len(self.files_written)}")
        if self.files_edited:
            lines.append(f"- Files edited: {len(self.files_edited)}")

        if self.tool_call_counts:
            top_tools = self.tool_call_counts.most_common(3)
            lines.append(f"- Top tools used: {', '.join(f'{t}({c})' for t, c in top_tools)}")

        return '\n'.join(lines)

    def should_force_complete(self) -> bool:
        """Check if we should force the agent to complete."""
        # Over turn limit
        if self.turn_count >= self.max_turns:
            return True

        # Stuck in a loop for too long
        if len(self.tool_calls) > 15:
            loop = self.detect_loop_pattern()
            if loop:
                return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """Get current state as dictionary for debugging/logging."""
        return {
            'turn_count': self.turn_count,
            'max_turns': self.max_turns,
            'files_read': len(self.files_read),
            'files_written': len(self.files_written),
            'files_edited': len(self.files_edited),
            'total_tool_calls': len(self.tool_calls),
            'task_phase': self.task_phase,
            'done_called': self.done_called,
            'elapsed_seconds': time.time() - self.session_start
        }

    def get_files_read_list(self) -> List[str]:
        """Return list of files that have been read."""
        return list(self.files_read.keys())

    def was_file_read(self, filepath: str) -> bool:
        """Check if a file was already read."""
        return filepath in self.files_read

    def reset(self):
        """Reset state for a new task."""
        self.turn_count = 0
        self.files_read.clear()
        self.files_written.clear()
        self.files_edited.clear()
        self.tool_calls.clear()
        self.tool_call_counts.clear()
        self.recent_actions.clear()
        self.task_phase = "exploring"
        self.done_called = False
        self.session_start = time.time()
        self.exploration_count = 0
        self.last_productive_turn = 0
        self.silent_tool_calls = 0
        self.last_response_had_text = False

    # ============================================================================
    # EXPLORATION BUDGET ENFORCEMENT
    # ============================================================================

    def set_exploration_budget(self, budget: int):
        """Set exploration budget based on model capability."""
        self.exploration_budget = budget

    def record_exploration_action(self, tool_name: str) -> Optional[str]:
        """
        Record an exploration action (read, search, list).
        Returns warning if budget exceeded.
        """
        exploration_tools = {'read_file', 'list_files', 'search_content', 'search_file_content',
                            'map_project', 'get_skeleton', 'get_file_info', 'symbol_jump'}

        if tool_name in exploration_tools:
            self.exploration_count += 1

            if self.exploration_count > self.exploration_budget:
                over_budget = self.exploration_count - self.exploration_budget
                return (
                    f"⚠️ EXPLORATION BUDGET EXCEEDED: You've used {self.exploration_count} exploration actions "
                    f"(budget: {self.exploration_budget}). You are {over_budget} over budget. "
                    f"STOP exploring and either: (1) Make your changes, or (2) Call done() with your answer. "
                    f"Do NOT call more read/search/list tools."
                )
            elif self.exploration_count == self.exploration_budget:
                return (
                    f"⚠️ EXPLORATION BUDGET REACHED: You've used all {self.exploration_budget} exploration actions. "
                    f"Your next action MUST be a write, edit, or done() call."
                )

        return None

    def record_productive_action(self, tool_name: str):
        """Record a productive action (write, edit, done) - resets exploration pressure."""
        productive_tools = {'write_file', 'edit_file', 'replace_lines', 'insert_at_line',
                           'delete_lines', 'append_to_file', 'done'}

        if tool_name in productive_tools:
            self.last_productive_turn = self.turn_count
            # Give back some exploration budget after being productive
            self.exploration_count = max(0, self.exploration_count - 3)

    def get_exploration_status(self) -> Dict[str, Any]:
        """Get exploration budget status."""
        return {
            'budget': self.exploration_budget,
            'used': self.exploration_count,
            'remaining': max(0, self.exploration_budget - self.exploration_count),
            'over_budget': self.exploration_count > self.exploration_budget,
            'turns_since_productive': self.turn_count - self.last_productive_turn
        }

    # ============================================================================
    # REASONING ENFORCEMENT
    # ============================================================================

    def record_response_quality(self, had_text: bool, had_tool_calls: bool):
        """
        Track whether the model is explaining itself.
        Returns warning if model is being too silent.
        """
        self.last_response_had_text = had_text

        if had_tool_calls and not had_text:
            self.silent_tool_calls += 1
        else:
            self.silent_tool_calls = 0

    def get_reasoning_warning(self) -> Optional[str]:
        """Get warning if model is making silent tool calls."""
        if self.silent_tool_calls >= 2:
            return (
                "⚠️ SILENT OPERATION WARNING: You've made tool calls without explaining your reasoning. "
                "Before your next tool call, briefly explain what you're doing and why. "
                "Example: 'I'll check the config file to find the database settings.' then call the tool."
            )
        return None

    def check_reasoning_before_action(self, response_text: str, tool_name: str) -> Optional[str]:
        """
        Check if model explained reasoning before calling a tool.
        For cheap models, enforce "think before act" pattern.
        """
        # Skip enforcement for Claude models (they're good at this)
        if "claude" in self.model_id.lower():
            return None

        # Skip for simple/quick tools
        quick_tools = {'done', 'get_file_info'}
        if tool_name in quick_tools:
            return None

        # Check if response had substantive text before tool call
        # Strip whitespace and check for meaningful content
        text = response_text.strip() if response_text else ""

        # Require at least some explanation (10+ chars of actual text)
        if len(text) < 10:
            return (
                f"💭 THINK FIRST: Before calling `{tool_name}`, briefly explain your intent. "
                f"Example: 'I need to find the configuration settings, so I'll search for config files.'"
            )

        return None
