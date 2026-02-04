# Gondola v2.1 (Necromancer Edition)

## Overview
Gondola v2.1 introduces the **Necromancer Architecture**: a stateless, resilient, and high-precision system designed to survive process deaths, interruptions, and "implementation amnesia."

---

## Key Architectural Upgrades

### 1. Cognitive Resurrection (Git Heartbeat)
*   **Module:** `venice/persistence.py`
*   **Mechanism:** Uses low-level Git commands (`commit-tree`, `update-ref`) to store the agent's "Working Memory" in a hidden `_gondola_shadow` branch.
*   **Benefit:** The agent can resume mid-thought after a crash or manual restart by reading the last resurrection point from the Git log.

### 2. Stateless Structuralism (Tree-sitter)
*   **Module:** `venice/tools/undead_ops.py`
*   **Tools:** `get_skeleton`, `get_symbol_coordinates`
*   **Benefit:** Provides instant Abstract Syntax Tree (AST) analysis without a long-running Language Server. The agent can see exact function line ranges and class structures with 0 latency.

### 3. Global Symbol Navigation (Ctags)
*   **Mechanism:** Triggers background `ctags` indexing on startup.
*   **Tool:** `symbol_jump`
*   **Benefit:** Project-wide navigation that survives power cycles. The agent can leap to any symbol definition across the entire codebase instantly.

### 4. Surgical Autopsy (Lazy LSP)
*   **Module:** `venice/undead_manager.py`
*   **Engine:** `jedi`
*   **Tool:** `inspect_type`
*   **Benefit:** Deep type-inference and documentation lookup performed by spawning temporary worker processes that are killed immediately after the query. 0% idle RAM usage.

### 5. Passive Diagnostics (The Observation Portal)
*   **Mechanism:** Fire-and-forget background linting triggered by file edits.
*   **Engine:** `ruff`
*   **Benefit:** Diagnostic errors are injected into the agent's context at the start of every turn, allowing for immediate self-correction without blocking the thinking loop.

---

## Recent Improvements (v2.1)

### Complete Tool Schema Coverage
*   **File:** `venice/tools/schema.py`
*   **Impact:** All 30 tools now have proper OpenAI-compatible schemas
*   **Tools Available:**
    - File Operations: read, write, edit, search, info
    - File Management: copy, move, delete, directories
    - Code Analysis: syntax validation, function/class finding, project mapping
    - Memory: persistent notes and preferences
    - Backup: list, restore, undo operations
    - Shell: command execution with environment awareness
    - Undead Ops: get_skeleton, symbol_jump, inspect_type

### Thread-Safe UI Operations
*   **File:** `venice/core.py`
*   **Fix:** Resolved race condition in `UI.print()` that could cause output corruption
*   **Benefit:** Reliable multi-threaded performance in web UI and CLI modes

---

## Architecture Core Principles

1. **Resurrection over Persistence:** Assume the process will die. Use Git to store cognitive state.
2. **Stateless Structuralism:** Use Tree-sitter and Ctags for instant, 0-RAM navigation.
3. **Surgical Autopsy:** Use LSPs (Jedi) as "temporary workers"—spawn, query, and kill immediately.
4. **Passive Safety:** Use fire-and-forget background linting injected at the start of turns.

---

## The Necromancer Workflow

The agent follows this discovery strategy:

1. **Resurrection:** Check Git log for last checkpoint on startup
2. **Structural Discovery:** Use `get_skeleton` to see a file's structure before reading the whole thing
3. **Cross-File Leaps:** Use `symbol_jump` to instantly find symbol definitions across the project
4. **Surgical Autopsy:** Use `inspect_type` for deep type-inference when needed
5. **Passive Safety:** Watch for diagnostic errors injected at turn-start for self-correction

---

## Integration Details

*   **Web UI Port:** 5040
*   **Launcher:** Integrated into the Venice Launcher (`command/main.py`)
*   **Environment:** Powered by `litellm_venv`
*   **Git Branch:** Uses `_gondola_shadow` for cognitive persistence

---

## Quick Start

### Installation
```bash
cd gondola_v2.0_dev
source litellm_venv/bin/activate
```

### Launch Web UI
```bash
./start_gondola.sh
# Access at http://localhost:5040
```

### Verify Installation
```bash
# Check tool schemas
python3 -c "from venice.tools.schema import TOOL_SCHEMAS; print(f'✓ {len(TOOL_SCHEMAS)} tools loaded')"

# Expected output: ✓ 30 tools loaded
```

---

## Testing

```bash
# Test tool schema
python3 test_tool_schema.py

# Test thread safety
python3 test_race_condition.py
```

Expected output:
```
✓ ALL SCHEMA TESTS PASSED
✓ ALL TESTS PASSED
```

---

## Documentation

- **`NECROMANCER_IMPLEMENTATION_PLAN.md`** - Architecture blueprint
- **`README_FIXES.md`** - Recent improvements and fixes
- **`PROPOSAL_SEMANTIC_SEARCH.md`** - Future semantic search integration

---

*Gondola v2.1: Built for resurrection, not persistence.*
