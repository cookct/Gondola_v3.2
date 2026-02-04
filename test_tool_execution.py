#!/usr/bin/env python3
import os
import shutil
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from venice.tools import CombinedTools
from venice.workspace import Workspace

def test_execution():
    test_dir = "test_workspace_exec"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    
    try:
        workspace = Workspace(test_dir)
        tools = CombinedTools(workspace)
        
        print("Testing tool execution...")
        
        # 1. list_files (defaults)
        print("- list_files (defaults)...")
        res = tools.list_files()
        if not res["success"]: print(f"FAILED: {res}")
        assert res["success"]
        
        # 2. write_file
        print("- write_file...")
        res = tools.write_file("test.txt", "Hello world\nLine 2\nLine 3")
        if not res["success"]: print(f"FAILED: {res}")
        assert res["success"]
        
        # 3. read_file (defaults)
        print("- read_file (defaults)...")
        res = tools.read_file("test.txt")
        if not res["success"]: print(f"FAILED: {res}")
        assert res["success"]
        assert "Hello world" in res["content"]
        
        # 4. read_file (optional args)
        print("- read_file (start_line=2)...")
        res = tools.read_file("test.txt", start_line=2)
        if not res["success"]: print(f"FAILED: {res}")
        assert res["success"]
        assert res["content"] == "Line 2\nLine 3"
        
        # 5. run_command (defaults)
        print("- run_command (defaults)...")
        res = tools.run_command("echo test")
        if not res["success"]: print(f"FAILED: {res}")
        assert res["success"]
        assert "test" in res["stdout"]
        
        # 6. run_command (with timeout)
        print("- run_command (timeout arg)...")
        res = tools.run_command("echo test", timeout=5)
        if not res["success"]: print(f"FAILED: {res}")
        assert res["success"]

        # 7. map_project (defaults)
        print("- map_project (defaults)...")
        res = tools.map_project()
        if not res["success"]: print(f"FAILED: {res}")
        assert res["success"]

        # 8. map_project (max_depth arg)
        print("- map_project (max_depth=1)...")
        res = tools.map_project(max_depth=1)
        if not res["success"]: print(f"FAILED: {res}")
        assert res["success"]

        print("\n✅ All execution tests passed!")
        
    finally:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

if __name__ == "__main__":
    test_execution()
