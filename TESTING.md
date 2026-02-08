# Gondola v2.3 - Testing Checklist

**Status: PRE-RELEASE TESTING**

---

## Critical Path Tests (Must Pass)

### 1. Installation & Setup
- [ ] Fresh clone installs without errors
- [ ] `pip install -r requirements.txt` succeeds
- [ ] Missing API keys show helpful error messages
- [ ] Environment variables work
- [ ] Config file method works
- [ ] Docker build succeeds
- [ ] Docker compose up works

### 2. Basic Connectivity
- [ ] Web UI loads at localhost:5040
- [ ] CLI starts without errors
- [ ] API key validation works
- [ ] Model list populates
- [ ] Can select different models

### 3. Core Chat Functionality
- [ ] Simple message sends and receives response
- [ ] Streaming works (tokens appear progressively)
- [ ] Stop button interrupts generation
- [ ] Multiple turns work (back-and-forth)
- [ ] Context persists across turns
- [ ] Conversation saves to disk

### 4. Tool Execution
- [ ] `list_files` works
- [ ] `read_file` works
- [ ] `write_file` works
- [ ] `edit_file` works
- [ ] `search_file_content` works
- [ ] `run_command` works
- [ ] `done()` completes task

### 5. Error Handling
- [ ] Invalid tool calls show errors
- [ ] Missing files show clear errors
- [ ] Syntax errors in written files are caught
- [ ] API errors are handled gracefully
- [ ] Rate limits are handled

---

## Security Tests (Must Pass)

### 6. Workspace Sandbox
- [ ] Cannot read files outside workspace
- [ ] Cannot write files outside workspace
- [ ] Symlinks outside workspace are blocked
- [ ] Path traversal attempts are blocked

### 7. API Key Handling
- [ ] Keys not logged to console
- [ ] Keys not in error messages
- [ ] Template config doesn't contain real keys
- [ ] `.gitignore` excludes config files

---

## Stress Tests (Should Pass)

### 8. Large Files
- [ ] Can read 10MB file
- [ ] Can read 50MB file
- [ ] Context compression works for large files
- [ ] Token counting is accurate

### 9. Long Conversations
- [ ] 20+ turn conversation works
- [ ] Context summarization triggers
- [ ] Conversation recovery after crash
- [ ] Memory doesn't leak

### 10. Concurrent Usage
- [ ] Multiple tabs work (Web UI)
- [ ] Interrupt doesn't crash server
- [ ] Rapid successive requests work

---

## Edge Cases (Nice to Have)

### 11. Special Characters
- [ ] Unicode in filenames works
- [ ] Unicode in file contents works
- [ ] Special characters in paths work

### 12. Binary Files
- [ ] Binary files are handled gracefully
- [ ] Images don't crash the system

### 13. Network Issues
- [ ] Timeout handling works
- [ ] Retry logic works
- [ ] Offline mode shows appropriate error

---

## Test Scripts

Run these to verify functionality:

```bash
# 1. Basic smoke test
python test_smoke.py

# 2. Tool execution test
python test_tools.py

# 3. Security test
python test_security.py

# 4. Load test
python test_load.py
```

---

## Known Issues

- [ ] Image editing removed for v1.0
- [ ] Claude models require Venice AI (not Together)
- [ ] Qwen models may need explicit stop prompts

---

## Sign-off

- [ ] All critical tests pass
- [ ] Security tests pass
- [ ] Documentation is accurate
- [ ] README matches actual behavior
- [ ] Ready for GitHub release

**Release Blockers:**
- None identified yet

**Release Date:** TBD
