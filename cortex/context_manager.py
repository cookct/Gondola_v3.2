"""
Context Manager - Token-aware context building for cheap models.

Manages conversation context to stay within model token limits while
preserving the most important information for task completion.
"""

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """Model-specific configuration for context management."""
    name: str
    context_limit: int
    native_function_calling: bool = True
    max_agent_turns: int = 20
    stream_timeout: int = 120

    # Rough token budget allocation
    @property
    def system_prompt_budget(self) -> int:
        return min(4000, self.context_limit // 8)

    @property
    def project_context_budget(self) -> int:
        return min(2000, self.context_limit // 10)

    @property
    def conversation_budget(self) -> int:
        return self.context_limit - self.system_prompt_budget - self.project_context_budget - 2000


@dataclass
class ContextManager:
    """
    Manages context for a single conversation session.

    Key responsibilities:
    - Track token usage
    - Compress large tool results
    - Implement sliding window for long conversations
    - Inject project context efficiently
    - Track truncation so model knows what was cut
    """
    model_config: ModelConfig
    project_context: str = ""  # Cached project index overview

    # Track what we've included
    messages: List[Dict[str, Any]] = field(default_factory=list)
    total_tokens_estimate: int = 0

    # Compression settings
    MAX_TOOL_RESULT_CHARS: int = 20000
    MAX_FILE_CONTENT_CHARS: int = 20000
    KEEP_RECENT_MESSAGES: int = 4  # Keep last N messages in full

    # TRUNCATION AWARENESS: Track what was cut so model knows
    truncation_notices: List[str] = field(default_factory=list)

    def clear_truncation_notices(self):
        """Clear truncation notices at start of new turn."""
        self.truncation_notices = []

    def add_truncation_notice(self, notice: str):
        """Add a truncation notice."""
        if notice not in self.truncation_notices:
            self.truncation_notices.append(notice)

    def get_truncation_warning(self) -> Optional[str]:
        """Get a warning message about truncated content, or None if nothing was truncated."""
        if not self.truncation_notices:
            return None
        return (
            "⚠️ CONTEXT NOTICE: The following content was truncated to fit token limits. "
            "Do NOT reference content that may have been cut:\n• " +
            "\n• ".join(self.truncation_notices)
        )

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate (4 chars = 1 token on average)."""
        if not text:
            return 0
        return len(text) // 4

    def set_project_context(self, context: str):
        """Set the project index context to include in system prompt."""
        self.project_context = context
        # Truncate if too long
        budget = self.model_config.project_context_budget * 4  # chars
        if len(self.project_context) > budget:
            self.project_context = self.project_context[:budget] + "\n... (truncated)"

    def compress_tool_result(self, tool_name: str, result: Any) -> str:
        """
        Compress a tool result to fit within limits.
        Different strategies for different tool types.
        """
        if isinstance(result, dict):
            result_str = json.dumps(result, indent=2)
        else:
            result_str = str(result)

        # Check if compression needed
        if len(result_str) <= self.MAX_TOOL_RESULT_CHARS:
            return result_str

        # Apply tool-specific compression
        if tool_name == 'read_file':
            return self._compress_file_content(result)
        elif tool_name == 'list_files':
            return self._compress_file_list(result)
        elif tool_name in ('search_content', 'search_file_content'):
            return self._compress_search_results(result)
        elif tool_name == 'run_command':
            return self._compress_command_output(result)
        elif tool_name == 'map_project':
            return self._compress_project_map(result)
        else:
            # Generic truncation with awareness
            self.add_truncation_notice(f"Tool '{tool_name}': result truncated from {len(result_str)} to {self.MAX_TOOL_RESULT_CHARS} chars")
            return result_str[:self.MAX_TOOL_RESULT_CHARS] + "\n... (truncated)"

    def _compress_file_content(self, result: Any) -> str:
        """Compress file read results - keep structure, truncate middle."""
        if isinstance(result, dict):
            content = result.get('content', str(result))
            filename = result.get('filename', 'file')
        else:
            content = str(result)
            filename = 'file'

        if len(content) <= self.MAX_FILE_CONTENT_CHARS:
            return content

        lines = content.split('\n')
        total_lines = len(lines)

        # Keep first 50 and last 30 lines for code files
        if total_lines > 80:
            head = '\n'.join(lines[:50])
            tail = '\n'.join(lines[-30:])
            omitted = total_lines - 80
            # TRUNCATION AWARENESS: Track what was cut
            self.add_truncation_notice(f"File '{filename}': lines 51-{total_lines - 30} were omitted ({omitted} lines)")
            return f"{head}\n\n... [{omitted} lines omitted from middle - lines 51 to {total_lines - 30}] ...\n\n{tail}"

        # Simple truncation for other cases
        self.add_truncation_notice(f"File '{filename}': content truncated to {self.MAX_FILE_CONTENT_CHARS} chars")
        return content[:self.MAX_FILE_CONTENT_CHARS] + f"\n... (truncated, {total_lines} total lines)"

    def _compress_file_list(self, result: Any) -> str:
        """Compress file listing - group by directory, limit count."""
        if isinstance(result, dict):
            files = result.get('files', [])
        elif isinstance(result, list):
            files = result
        else:
            return str(result)[:self.MAX_TOOL_RESULT_CHARS]

        if len(files) <= 50:
            return json.dumps({'files': files, 'count': len(files)}, indent=2)

        # TRUNCATION AWARENESS
        self.add_truncation_notice(f"File listing: summarized {len(files)} files (showing directory groups)")

        # Group by directory and summarize
        by_dir: Dict[str, List[str]] = {}
        for f in files:
            parts = f.rsplit('/', 1)
            if len(parts) == 2:
                dir_name, file_name = parts
            else:
                dir_name, file_name = '.', parts[0]

            if dir_name not in by_dir:
                by_dir[dir_name] = []
            by_dir[dir_name].append(file_name)

        summary_lines = [f"Found {len(files)} files (summarized - use pattern filter for specific files):\n"]
        for dir_name in sorted(by_dir.keys())[:20]:
            dir_files = by_dir[dir_name]
            if len(dir_files) > 5:
                sample = dir_files[:3]
                summary_lines.append(f"  {dir_name}/: {', '.join(sample)} ... +{len(dir_files)-3} more")
            else:
                summary_lines.append(f"  {dir_name}/: {', '.join(dir_files)}")

        if len(by_dir) > 20:
            summary_lines.append(f"  ... +{len(by_dir) - 20} more directories")

        return '\n'.join(summary_lines)

    def _compress_search_results(self, result: Any) -> str:
        """Compress search results - keep top matches, summarize rest."""
        if isinstance(result, dict):
            matches = result.get('matches', [])
            pattern = result.get('pattern', 'search')
        elif isinstance(result, list):
            matches = result
            pattern = 'search'
        else:
            return str(result)[:self.MAX_TOOL_RESULT_CHARS]

        if len(matches) <= 10:
            return json.dumps(result, indent=2)

        # TRUNCATION AWARENESS: Track what was cut
        self.add_truncation_notice(f"Search results: showing 10 of {len(matches)} matches")

        # Keep first 10 matches in full
        summary = {
            'matches': matches[:10],
            'total_matches': len(matches),
            'showing': 10,
            'note': f'Showing top 10 of {len(matches)} matches. Use more specific search if needed.',
            'additional_files': list(set(m.get('file', m) if isinstance(m, dict) else str(m)
                                         for m in matches[10:]))[:20]
        }
        return json.dumps(summary, indent=2)

    def _compress_command_output(self, result: Any) -> str:
        """Compress command output - keep errors in full, truncate verbose output."""
        if isinstance(result, dict):
            output = result.get('output', '') or result.get('stdout', '')
            stderr = result.get('stderr', '')
            exit_code = result.get('exit_code', result.get('returncode', 0))
            command = result.get('command', 'command')
        else:
            output = str(result)
            stderr = ''
            exit_code = 0
            command = 'command'

        # Always keep stderr in full (usually contains errors)
        if stderr:
            stderr_section = f"\nSTDERR:\n{stderr[:2000]}"
        else:
            stderr_section = ""

        original_len = len(output)
        # Truncate stdout if very long
        if len(output) > self.MAX_TOOL_RESULT_CHARS - len(stderr_section):
            truncate_at = self.MAX_TOOL_RESULT_CHARS - len(stderr_section) - 100
            output = output[:truncate_at]
            output += "\n... (output truncated)"
            # TRUNCATION AWARENESS
            self.add_truncation_notice(f"Command output: truncated from {original_len} to {truncate_at} chars")

        return f"Exit code: {exit_code}\n{output}{stderr_section}"

    def _compress_project_map(self, result: Any) -> str:
        """Compress project map - keep structure, limit depth."""
        if isinstance(result, str):
            if len(result) <= self.MAX_TOOL_RESULT_CHARS:
                return result
            # Truncate tree output
            lines = result.split('\n')
            return '\n'.join(lines[:100]) + f"\n... (+{len(lines)-100} more entries)"

        return json.dumps(result, indent=2)[:self.MAX_TOOL_RESULT_CHARS]

    def build_messages(self, messages: List[Dict], include_project_context: bool = True) -> List[Dict]:
        """
        Build optimized message list for API call.

        Strategy:
        1. Keep system message with project context
        2. Keep all recent messages (last N)
        3. Summarize older messages
        4. Compress large tool results
        """
        if not messages:
            return []

        optimized = []
        total_tokens = 0

        # Separate system message from rest
        system_msg = None
        conversation = []

        for msg in messages:
            if msg.get('role') == 'system':
                system_msg = msg
            else:
                conversation.append(msg)

        # Build system message with project context
        if system_msg:
            system_content = system_msg.get('content', '')
            if include_project_context and self.project_context:
                system_content = f"{system_content}\n\n{self.project_context}"

            # Enforce budget
            budget_chars = self.model_config.system_prompt_budget * 4
            if len(system_content) > budget_chars:
                system_content = system_content[:budget_chars] + "\n... (system prompt truncated)"

            optimized.append({'role': 'system', 'content': system_content})
            total_tokens += self.estimate_tokens(system_content)

        # Process conversation messages
        budget_tokens = self.model_config.conversation_budget

        # Always keep recent messages
        recent = conversation[-self.KEEP_RECENT_MESSAGES:]
        older = conversation[:-self.KEEP_RECENT_MESSAGES] if len(conversation) > self.KEEP_RECENT_MESSAGES else []

        # Add older messages (compressed/summarized)
        for msg in older:
            compressed = self._compress_message(msg)
            msg_tokens = self.estimate_tokens(json.dumps(compressed))

            if total_tokens + msg_tokens > budget_tokens * 0.5:
                # We're using too much on old messages, start dropping
                continue

            optimized.append(compressed)
            total_tokens += msg_tokens

        # Add recent messages
        for msg in recent:
            compressed = self._compress_message(msg)
            optimized.append(compressed)
            total_tokens += self.estimate_tokens(json.dumps(compressed))

        self.total_tokens_estimate = total_tokens
        return optimized

    def _compress_message(self, msg: Dict) -> Dict:
        """Compress a single message, handling tool results."""
        role = msg.get('role', '')
        content = msg.get('content', '')

        # Handle tool results in content
        if isinstance(content, list):
            compressed_content = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'tool_result':
                    # Compress tool result
                    tool_content = item.get('content', '')
                    if len(str(tool_content)) > self.MAX_TOOL_RESULT_CHARS:
                        item = dict(item)
                        item['content'] = self.compress_tool_result('unknown', tool_content)
                compressed_content.append(item)
            return {'role': role, 'content': compressed_content}

        # Handle string content
        if isinstance(content, str) and len(content) > self.MAX_TOOL_RESULT_CHARS:
            # Check if it's a tool result message pattern
            content = content[:self.MAX_TOOL_RESULT_CHARS] + "\n... (truncated)"

        return {'role': role, 'content': content}

    def inject_checkpoint(self, turn_number: int) -> Optional[str]:
        """
        Generate checkpoint reminder message based on turn number.
        Returns None if no checkpoint needed.
        """
        checkpoints = {
            5: "You've completed 5 turns. Review your progress - if you have enough information, call done() with your response.",
            10: "Turn 10 reached. You should have enough context now. Time to complete the task and call done().",
            15: "Warning: Turn 15. You MUST complete the task now. Call done() with your best response."
        }

        return checkpoints.get(turn_number)

    def should_stop(self, turn_number: int) -> bool:
        """Check if we should force-stop the agent."""
        return turn_number >= self.model_config.max_agent_turns

    def get_force_stop_message(self) -> str:
        """Message to return when force-stopping."""
        return (
            f"Agent reached maximum turns ({self.model_config.max_agent_turns}). "
            "Task was not completed within the allowed iterations. "
            "Please try a more specific request or use a more capable model."
        )
