# 🎯 TASK: Refactor the Test Suite

**Objective:** Merge `test_smoke.py` and `test_security.py` into a unified test suite, then add tests for the new modules.

---

## 📋 STEP-BY-STEP

### Step 1: Find Related Files
**Tool to use:** `smart_context`

Ask the AI:
```
"Find all files related to test_smoke.py and test_security.py"
```

This will discover:
- What files import these tests
- What modules they test
- Related test utilities

---

### Step 2: Read Both Test Files
**Tool to use:** `batch_read`

Ask the AI:
```
"Read test_smoke.py and test_security.py in one operation"
```

This loads both files so you can see their structure.

---

### Step 3: Create Unified Test Suite
**Tool to use:** `write_file`

Create `test_unified.py` that:
- Combines smoke tests and security tests
- Adds a unified test runner
- Includes proper test categorization

---

### Step 4: Generate Tests for New Modules
**Tool to use:** `generate_test_stub`

Ask the AI:
```
"Generate test stubs for venice/tools/batch_ops.py"
```

This auto-generates pytest scaffolding for the new batch operations.

---

### Step 5: Check Git Status
**Tool to use:** `git_status`

See what files you've modified and what's staged.

---

### Step 6: Run the Tests
**Tool to use:** `run_tests`

Ask the AI:
```
"Run all tests with verbose output"
```

Verify everything works.

---

### Step 7: Get Commit Message
**Tool to use:** `suggest_commit_message`

Let the AI analyze your changes and suggest a commit message.

---

## 🏆 BONUS: Add Web Research

**Tools to use:** `search_stackoverflow`, `fetch_url`

Ask the AI:
```
"Search Stack Overflow for Python pytest best practices"
```

Then:
```
"Fetch the top result URL"
```

Incorporate best practices into your test suite.

---

## 🎬 START HERE

Copy-paste this to the AI:

```
"I want to refactor the test suite. Start by using smart_context 
to find all files related to test_smoke.py and test_security.py, 
then use batch_read to load both files so I can see their structure."
```

**Watch it use:**
- ✅ smart_context (finds related files)
- ✅ batch_read (loads multiple files)
- ✅ git_status (shows changes)
- ✅ generate_test_stub (creates tests)
- ✅ run_tests (validates)
- ✅ suggest_commit_message (commits)

---

**Ready? Paste the command above and let's see the magic!** 🚀
