# Gondola v2.2: The Necromancer Architecture
## Master Implementation Blueprint for Claude

This document outlines the transition of Gondola from a state-heavy LSP model to a **Stateless, Resilient, and Atomic** architecture.

---

## **Architecture Core Principles**
1.  **Resurrection over Persistence:** Assume the process will die. Use Git to store cognitive state.
2.  **Stateless Structuralism:** Use Tree-sitter and Ctags for instant, 0-RAM navigation.
3.  **Surgical Autopsy:** Use LSPs (Jedi) as "temporary workers"—spawn, query, and kill immediately.
4.  **Passive Safety:** Use fire-and-forget background linting injected at the start of turns.

---

## **Phase 1: Cognitive Persistence (The Git Heartbeat)**
*Goal: Restore the agent's "Working Memory" across restarts.*

### **1.1 Create `venice/persistence.py`**
*   Create a `PersistenceManager` class.
*   **Logic:**
    *   Initialize a hidden git branch `_gondola_shadow`.
    *   `checkpoint(thought, task)`: Execute an empty commit: `git commit --allow-empty -m "RESURRECT: {thought} | PENDING: {task}"`.
    *   `get_last_checkpoint()`: Parse the last commit message from `_gondola_shadow`.

### **1.2 CLI Integration (`venice/cli.py`)**
*   **Startup:** On `main()` init, fetch the last checkpoint.
*   **Injection:** Prepend a system message: `"RESURRECTION POINT: Your last thought was [X]. You were about to [Y]. Resume."`

---

## **Phase 2: Instant Structural Awareness (Tree-sitter)**
*Goal: Deterministic file mapping without a running server.*

### **2.1 Create `venice/tools/undead_ops.py`**
*   Define `UndeadOpsMixin`.
*   **Tool: `get_skeleton(filename)`:**
    *   Use `tree-sitter-python` (and JS) to return a JSON tree of Classes, Methods, and their **exact line ranges**.
*   **Utility: `get_symbol_coordinates`:**
    *   Use AST nodes to map a symbol name to `Line:Column` coordinates for the autopsy phase.

---

## **Phase 3: Global Symbol Map (Stateless Ctags)**
*Goal: Fast, project-wide navigation.*

### **3.1 Background Indexing**
*   In `venice/project_index.py`, trigger a background `ctags` scan:
    *   `ctags -R --fields=+l --languages=Python,JavaScript -f .gondola_tags`
*   **Tool: `symbol_jump(name)`:**
    *   Fast-search `.gondola_tags`. Return `{"filename": "x.py", "line": 100}`.

---

## **Phase 4: Surgical Autopsy (Lazy LSP via Jedi)**
*Goal: Deep type-inference with 0% idle RAM.*

### **4.1 The "Surgical" Worker (`venice/undead_manager.py`)**
*   **Logic:**
    *   Spawn a `jedi` worker process on demand.
    *   Query the exact coordinate (provided by Tree-sitter) for type info/docstrings.
    *   **SIGKILL** the worker immediately after the result is returned.
*   **Tool: `inspect_type(filename, symbol)`:**
    *   The agent uses this to understand complex objects without reading the whole file.

---

## **Phase 5: Passive Diagnostics (The Observation Portal)**
*Goal: Catch errors without a blocking wait.*

### **5.1 Fire-and-Forget Linting**
*   In `file_ops.py`, after a successful `write_file` or `edit_file`, spawn:
    *   `ruff check --format json > .gondola_diagnostics.json 2>/dev/null &`
*   **Turn-Start Sentry (`cli.py`):**
    *   At the start of every turn, read `.gondola_diagnostics.json`.
    *   If errors exist, inject as a system observation: `"Your last edit introduced a syntax error on line 12."`

---

## **Phase 6: The Necromancer Workflow (System Prompt)**
*Goal: Train the agent to use its new powers.*

### **6.1 Update `venice/prompts/system.py`**
*   **The Strategy:**
    1.  **Resurrect:** Check the git log first.
    2.  **Skeleton:** Use `get_skeleton` to see a file's shape before reading.
    3.  **Jump:** Use `symbol_jump` to move across the project.
    4.  **Autopsy:** Use `inspect_type` only for deep confusion.
    5.  **Watch:** Observe the Diagnostics Portal for self-correction.

---

## **File Change Checklist**
- [ ] `venice/persistence.py` (New)
- [ ] `venice/undead_manager.py` (New)
- [ ] `venice/tools/undead_ops.py` (New)
- [ ] `venice/cli.py` (Modified: Injection/Cleanup)
- [ ] `venice/project_index.py` (Modified: Ctags trigger)
- [ ] `venice/tools/__init__.py` (Modified: Mixin registration)
- [ ] `venice/prompts/system.py` (Modified: Workflow instructions)
