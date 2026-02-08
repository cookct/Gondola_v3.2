#!/usr/bin/env python3
"""
Test script to verify Proactive Context Validation in FileOpsMixin
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from venice.workspace import Workspace
from venice.agent_state import AgentState
from venice.tools import CombinedTools as Tools
from venice.core import UI

def test_context_validation():
    print("Testing Proactive Context Validation...")
    
    # Setup temporary workspace
    test_dir = Path("/home/anonymous/.gemini/tmp/test_context_val")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = test_dir / "app.py"
    initial_content = "def hello():\n    print('hello')\n"
    test_file.write_text(initial_content)
    
    workspace = Workspace(str(test_dir))
    agent_state = AgentState()
    tools = Tools(workspace, agent_state=agent_state)
    
    # 1. Read the file (simulated tool call)
    print("Step 1: Reading file...")
    result = tools.read_file("app.py")
    assert result["success"] is True
    
    # Record in agent state (as cli.py would do)
    agent_state.record_file_read("app.py", result["content"], full_hash=result["hash"])
    print(f"✓ Recorded hash: {result['hash'][:8]}")
    
    # 2. Verify edit works when file hasn't changed
    print("Step 2: Editing file (no change)...")
    edit_result = tools.edit_file("app.py", "print('hello')", "print('world')")
    assert edit_result["success"] is True
    print("✓ Edit successful as expected")
    
    # Re-read to update state after successful edit (as cli.py would typically see or the model should do)
    # Actually cli.py invalidates read on edit
    agent_state.record_file_edit("app.py")
    result = tools.read_file("app.py")
    agent_state.record_file_read("app.py", result["content"], full_hash=result["hash"])
    
    # 3. Modify file externally
    print("Step 3: Modifying file externally...")
    with open(test_file, "a") as f:
        f.write("# External change\n")
    
    # 4. Attempt to edit (should fail)
    print("Step 4: Attempting edit after external change...")
    fail_result = tools.edit_file("app.py", "print('world')", "print('fail')")
    
    assert fail_result["success"] is False
    assert "WARNING: File 'app.py' has changed on disk" in fail_result["error"]
    print("✓ Context validation caught the external change!")
    
    # 5. Verify replace_lines also fails
    print("Step 5: Attempting replace_lines after external change...")
    fail_result2 = tools.replace_lines("app.py", 1, 1, "print('fail')")
    assert fail_result2["success"] is False
    assert "WARNING: File 'app.py' has changed on disk" in fail_result2["error"]
    print("✓ Context validation caught the change for replace_lines!")

    # Cleanup
    os.remove(test_file)
    test_dir.rmdir()

if __name__ == "__main__":
    try:
        test_context_validation()
        print("\nALL TESTS PASSED!")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
