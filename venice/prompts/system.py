"""
Dynamic system prompt builder for Venice agent.

Builds context-aware prompts that include:
- Project structure overview
- Explicit stopping criteria
- Model-specific guidance
"""


BASE_SYSTEM_PROMPT = """You are an autonomous AI coding agent.

## MANDATES:
1. **COMMUNICATE**: Always provide a natural language response in the chat window explaining what you did or providing your final answer BEFORE calling `done()`. Do not just call the tool silently.
2. **COMPLETE YOUR TASK**: Call `done()` with your final summary only after you have provided your textual response to the user.
3. **EFFICIENCY**: Read files ONCE. No duplicate reads.
4. **VERIFY**: Check tool results for `"success": false`. Fix errors immediately.
5. **STOP**: If you have the answer, explain it to the user and then call `done()`. Don't keep exploring.

## TOOLS:
- `list_files(path, pattern)`
- `read_file(filename)`
- `search_file_content(pattern, path)`
- `get_skeleton(filename)`: Get file structure
- `symbol_jump(symbol_name)`: Jump to definition
- `inspect_type(filename, symbol)`: Signature/type info
- `write_file(filename, content)`
- `edit_file(filename, old_text, new_text)`
- `run_command(command)`
- `done(summary)`: **REQUIRED** to finish

## EDIT PROTOCOL:
High-risk edits are BLOCKED. If blocked, verify (e.g., `read_file`) then retry with `verify_risk=true`.
"""


STOPPING_CRITERIA = """
## STOP:
Call `done()` when you have answered, completed changes, or have enough info.
"""


MODEL_SPECIFIC_GUIDANCE = {
    "google-gemma-3-27b-it": """
## SPECIAL INSTRUCTIONS (Gemma):

When you want to use a tool, you MUST format it as a JSON object, not as a function call.
Example: {"tool": "read_file", "filename": "main.py"}

**CRITICAL for write_file:**
- You MUST include the FULL, COMPLETE content in the "content" field
- Do NOT use placeholders like "<!-- content from above -->" or "// code here"
- Do NOT reference content written elsewhere - put the ACTUAL content in the JSON
- If content is long, that's OK - include ALL of it

BAD: {"tool": "write_file", "filename": "x.html", "content": "<!-- see above -->"}
GOOD: {"tool": "write_file", "filename": "x.html", "content": "<!DOCTYPE html><html>...</html>"}

Do NOT write out what you think files contain. Wait for actual tool results.
Do NOT hallucinate or imagine tool outputs - they will be provided to you.
""",

    "qwen3-235b-a22b-instruct-2507": """
## SPECIAL INSTRUCTIONS (Qwen):

Be concise and direct. After reading a few key files, you should have enough context.
Do NOT read every file in the project - focus on what's relevant to the task.
Call done() as soon as you can answer or have made the required changes.

**CRITICAL - Follow Instructions Exactly**:
- Re-read the user's request before making changes
- If user says "put X in the settings menu" - put it IN the settings menu, not somewhere else
- If user specifies a location, use THAT location - do not improvise
- If unsure where something goes, ASK - don't guess
- Do not add extra modals, buttons, or UI elements the user didn't request

**Communication**: Briefly explain what you're doing as you work. For example:
- "I'll check the settings file to find the toggle options."
- "Found it. I'll add the new toggle now."
- "Done! I added X to Y."
Keep explanations short (1 sentence) but keep the user informed.

**IMPORTANT - Always Check In When Finished**:
- After completing a task, ALWAYS call done() with a summary
- Tell the user WHAT you did and WHERE you put it
- Example: done("Added font size slider to the settings menu in index.html, lines 150-165")
- Do NOT silently finish - the user needs confirmation
""",

    "llama-3.3-70b": """
## SPECIAL INSTRUCTIONS (Llama):

Focus on the specific task. Avoid exploring unrelated files.
Make your tool calls count - read only what you need.
Respond promptly once you have sufficient information.
"""
}


PLANNING_MODE_PROMPT = """
## PLANNING MODE:
1. **READ-ONLY**: No writes/edits allowed.
2. **GOAL**: Gather context and provide a implementation plan.
3. **FINISH**: Call `done()` with your proposed plan.
"""


def build_system_prompt(
    model_id: str = None,
    project_context: str = None,
    turn_count: int = 0,
    max_turns: int = 20,
    files_already_read: list = None,
    resurrection_context: str = None,
    planning_mode: bool = False,
    memory_context: str = None
) -> str:
    """
    Build a dynamic system prompt with context.

    Args:
        model_id: The model being used (for model-specific guidance)
        project_context: Compressed project overview from ProjectIndex
        turn_count: Current turn number (for urgency)
        max_turns: Maximum allowed turns
        files_already_read: List of files already read this session
        resurrection_context: Information about the last interrupted state
        planning_mode: If True, restricts agent to planning only
        memory_context: Information from previous sessions
    """
    parts = [BASE_SYSTEM_PROMPT]

    # Add planning mode instructions early to override default workflow
    if planning_mode:
        parts.append(PLANNING_MODE_PROMPT)

    # Add memory context if available
    if memory_context:
        parts.append(f"\n## MEMORY:\n\n{memory_context}")

    # Add resurrection context if available
    if resurrection_context:
        parts.append(f"\n## RESURRECTION POINT:\n\n{resurrection_context}\n\nAcknowledge this state and continue where you left off.")

    # Add stopping criteria
    parts.append(STOPPING_CRITERIA)

    # Add model-specific guidance
    if model_id and model_id in MODEL_SPECIFIC_GUIDANCE:
        parts.append(MODEL_SPECIFIC_GUIDANCE[model_id])

    # Add project context if available
    if project_context:
        parts.append(f"\n## PROJECT OVERVIEW:\n\n{project_context}")

    # Add turn awareness for models that need it
    if turn_count > 0:
        remaining = max_turns - turn_count
        if remaining <= 5:
            parts.append(f"\n## TURN LIMIT WARNING:\n\nYou have {remaining} turns remaining. Complete your task and call done() soon.")
        elif remaining <= 10:
            parts.append(f"\n(Turn {turn_count}/{max_turns})")

    # Add already-read files reminder
    if files_already_read and len(files_already_read) > 0:
        files_list = ', '.join(files_already_read[:10])
        parts.append(f"\n## FILES ALREADY READ:\n\n{files_list}\n\nDo not read these files again.")

    return '\n'.join(parts)


def get_checkpoint_message(turn_count: int, model_id: str = None) -> str:
    """
    Get a checkpoint reminder message for the current turn.
    """
    messages = {
        10: "Turn 10: You're making good progress. Continue if needed, or wrap up if ready.",
        20: "Turn 20: Halfway through your limit. Keep going if the task requires more work.",
        30: "Turn 30: Getting close to limit. Start thinking about completing soon.",
        40: "Turn 40: Almost at max turns. Finish up in the next few turns.",
        45: "Turn 45: FINAL WARNING. Complete your task and call done() soon.",
        48: "Turn 48: CRITICAL - You have 2 turns left. Call done() on your next turn."
    }

    return messages.get(turn_count, None)


# Legacy export for backwards compatibility
SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + STOPPING_CRITERIA
