# Recent Updates - February 5, 2026

## Session Summary
Major reliability improvements and new features added to Gondola v2.2.

---

## 1. Fixed 12 Missing Tools in API

**Problem:** Tools were defined in schema but not mapped in `execute_tool()`, causing "Unknown tool" errors.

**File:** `venice/api.py`

**Tools Added:**
- `append_to_file`
- `replace_lines`
- `insert_at_line`
- `delete_lines`
- `validate_syntax`
- `find_functions`
- `find_classes`
- `remember`
- `recall`
- `forget`
- `save_knowledge`
- `search_file_content`

---

## 2. Error Feedback Loop Improvements

**Problem:** Models would receive `{"success": false}` buried in JSON and ignore it, then call `done()` claiming success.

### 2a. System Prompt Updates
**File:** `venice/prompts/system.py`

Added Rule #5:
```
CHECK TOOL RESULTS: After EVERY tool call, examine the result for
"success": false or "error". If a tool fails, you MUST:
- Acknowledge the failure
- Try an alternative approach OR report the issue
- NEVER call done() claiming success if any tool failed
```

### 2b. Prominent Error Formatting
**File:** `venice-web-ui/server.py`

Errors now display as:
```
╔══════════════════════════════════════════════════════════════╗
║  ❌ TOOL FAILED: append_to_file                              ║
╠══════════════════════════════════════════════════════════════╣
║  Error: Unknown tool                                          ║
╠══════════════════════════════════════════════════════════════╣
║  💡 Try: read_file() → add content → write_file()            ║
╠══════════════════════════════════════════════════════════════╣
║  ⛔ DO NOT call done() claiming success!                     ║
╚══════════════════════════════════════════════════════════════╝
```

### 2c. Alternative Suggestions
When tools fail, suggests alternatives:
- `append_to_file` → "Try: read_file() then write_file() with appended content"
- `edit_file` → "Try: Use read_file() first to see exact text"
- etc.

### 2d. Failed Tool Tracking
**File:** `venice/agent_state.py`

Added:
- `failed_tools` list
- `record_tool_failure(tool_name, args, error)`
- `has_recent_failures()`
- `get_unaddressed_failures()`

### 2e. Block done() on Write Failures
**File:** `venice-web-ui/server.py`

If `write_file`, `edit_file`, `append_to_file`, etc. failed, `done()` is now BLOCKED:
```
⛔ BLOCKED: You cannot call done() because your write operation failed:
  • append_to_file: Unknown tool
You MUST fix this before completing. Try an alternative approach.
```

---

## 3. Auto-Learning System

**Problem:** Knowledge had to be manually saved. User wanted automatic accumulation.

### How It Works
When a task completes successfully with file changes:
1. `agent_state.generate_learning(summary)` extracts knowledge
2. Auto-generates keywords from task + file paths
3. Saves to `.gondola_knowledge/{title}.md`
4. Indexed for semantic search retrieval

**Files:**
- `venice/agent_state.py` - Added `generate_learning()` method
- `venice-web-ui/server.py` - Hooked into `done()` flow

### Filtering
Only triggers when:
- Task made file changes (writes or edits)
- Task took 2+ turns (not trivial)

### Example Output
```markdown
# Add Cyberpunk Theme To

Keywords: cyberpunk, css, theme, lagoon_v1, themes

## Task
add a cyberpunk theme to the themes.css file

## Files Modified
- `lagoon_v1.3/css/themes.css`

## What Was Done
Added Cyberpunk Neon theme with neon colors and glitch effects

## Navigation Hints
- This task involved 1 file(s)
- Completed in 4 turns
- CSS styling in: lagoon_v1.3/css/themes.css
```

---

## 4. Folder Browser Navigation

**Problem:** Workspace selector was a flat dropdown. Couldn't drill into subfolders. Had to verbally tell agent which project.

### New Features

**Breadcrumb Navigation:**
```
gemini-workspace / sandbox1 / my-project
```
Click any part to jump back.

**Folder List:**
- 📂 icon for folders with subfolders
- 📁 icon for leaf folders
- `3📁 12📄` showing subfolder/file counts
- **→** button to drill down
- **✓ Root** button to set as workspace

**Files:**
- `venice-web-ui/server.py` - Added `/api/browse` endpoint
- `venice-web-ui/templates/index.html` - Replaced dropdown with folder browser
- `venice-web-ui/static/style.css` - Added folder browser styles
- `venice-web-ui/static/script.js` - Added `browseFolders()` and `setWorkspaceRoot()`

---

## Files Modified Summary

| File | Changes |
|------|---------|
| `venice/api.py` | Added 12 missing tools to `tool_map` |
| `venice/prompts/system.py` | Added error-checking rule, strengthened VERIFY step |
| `venice/agent_state.py` | Added `failed_tools` tracking + `generate_learning()` |
| `venice-web-ui/server.py` | Error injection, done() blocking, auto-learning hook, `/api/browse` |
| `venice-web-ui/templates/index.html` | Folder browser UI |
| `venice-web-ui/static/style.css` | Folder browser styles |
| `venice-web-ui/static/script.js` | Folder browser logic |

---

## Testing Notes

All changes tested and verified working:
- Missing tools now execute correctly
- Error messages display prominently
- done() blocked when write tools fail
- Auto-learning generates and saves knowledge
- Folder browser navigates and sets workspace root

---

*— Claude Opus - TOP DOG*
