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

    def record_turn(self) -> int:
        """Increment and return turn count."""
        self.turn_count += 1
        return self.turn_count

    def record_file_read(self, filepath: str, content: str) -> Optional[str]:
        """
        Record a file read. Returns cached content hash if file was already read.
        """
        content_hash = hashlib.md5(content.encode()[:5000]).hexdigest()[:12]

        if filepath in self.files_read:
            prev = self.files_read[filepath]
            if prev.content_hash == content_hash:
                # Same file, same content - this is a duplicate read
                return f"DUPLICATE: You already read this file at turn {self.turn_count - 1}. Content unchanged."
            else:
                # File changed since last read
                self.files_read[filepath] = FileReadRecord(
                    filepath=filepath,
                    content_hash=content_hash,
                    timestamp=time.time(),
                    line_count=len(content.split('\n'))
                )
                return None

        self.files_read[filepath] = FileReadRecord(
            filepath=filepath,
            content_hash=content_hash,
            timestamp=time.time(),
            line_count=len(content.split('\n'))
        )
        return None

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

    def detect_loop_pattern(self) -> Optional[str]:
        """
        Detect if the agent is stuck in a loop pattern.
        Returns warning message if loop detected.
        """
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

        # If we've done 5+ exploration actions without any writes or done, warn
        if exploration_count >= 5 and write_count == 0 and done_count == 0:
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
