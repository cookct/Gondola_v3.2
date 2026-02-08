import os
import sys
import json

# Setup paths
project_root = os.path.abspath(".")
sys.path.insert(0, project_root)

from venice.workspace import Workspace
from venice.memory import Memory
from venice.agent_state import AgentState
from venice.project_index import ProjectIndex
from venice.tools import CombinedTools
from venice.core import UI

def test_risk_gate():
    # 1. Setup Environment
    workspace = Workspace(os.path.join(project_root, "test_workspace"))
    memory = Memory(workspace.root_dir)
    project_index = ProjectIndex(workspace.root_dir)
    agent_state = AgentState()
    agent_state.model_id = "qwen3-235b-a22b-instruct-2507" # Threshold 90
    
    tools = CombinedTools(workspace, memory, project_index, agent_state=agent_state)
    
    filename = "risk_test.py"
    content = "def old_function():\n    return 'old'\n"
    
    print("\n--- STEP 1: Creating file risk_test.py ---")
    res = tools.write_file(filename, content)
    print(json.dumps(res, indent=2))
    
    print("\n--- STEP 2: Attempting edit WITHOUT reading (Should be BLOCKED) ---")
    # This should trigger "FILE NEVER READ" which is 100 points (CRITICAL)
    # Threshold for Qwen is 90.
    res = tools.edit_file(
        filename=filename,
        old_text="return 'old'",
        new_text="return 'new'",
        thought="Testing the risk gate block"
    )
    print("\nRESULT:")
    print(json.dumps(res, indent=2))
    
    if res.get("error") == "HIGH_RISK_EDIT_BLOCKED":
        print("\n✅ SUCCESS: Risk gate blocked the edit as expected.")
    else:
        print("\n❌ FAILURE: Risk gate did not block the edit.")
        return

    print("\n--- STEP 3: Reading file to satisfy requirement ---")
    read_res = tools.read_file(filename)
    agent_state.record_file_read(filename, read_res["content"], full_hash=read_res["hash"])
    print("File read recorded.")

    print("\n--- STEP 4: Retrying edit WITH verify_risk=True ---")
    res = tools.edit_file(
        filename=filename,
        old_text="return 'old'",
        new_text="return 'new'",
        thought="Retrying after verification",
        verify_risk=True
    )
    print("\nRESULT:")
    print(json.dumps(res, indent=2))
    
    if res.get("success"):
        print("\n✅ SUCCESS: Edit applied with override.")
    else:
        print("\n❌ FAILURE: Edit failed even with override.")

if __name__ == "__main__":
    if not os.path.exists("test_workspace"):
        os.makedirs("test_workspace")
    test_risk_gate()
