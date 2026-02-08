import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath('.'))

from venice.workspace import Workspace
from venice.tools.file_ops import FileOpsMixin
from venice.agent_state import AgentState

class MockCombinedTools(FileOpsMixin):
    def __init__(self, workspace, agent_state=None):
        super().__init__(workspace=workspace, agent_state=agent_state)

workspace = Workspace('.')
state = AgentState()
tools = MockCombinedTools(workspace, agent_state=state)

test_file = "test_append_file.txt"
if os.path.exists(test_file):
    os.remove(test_file)

try:
    print("--- Test 1: Direct append ---")
    tools.append_to_file(test_file, "Line 1\n")
    with open(test_file, 'r') as f:
        print(f"Content: {repr(f.read())}")
    
    print("\n--- Test 2: Transactional append ---")
    tools.begin_transaction()
    tools.append_to_file(test_file, "Line 2\n")
    print(f"Staged changes: {state.staged_changes}")
    
    with open(test_file, 'r') as f:
        print(f"Content on disk (should be Line 1): {repr(f.read())}")
        
    tools.commit_transaction()
    with open(test_file, 'r') as f:
        print(f"Content on disk after commit: {repr(f.read())}")

    print("\nSuccess!")
finally:
    if os.path.exists(test_file):
        os.remove(test_file)
