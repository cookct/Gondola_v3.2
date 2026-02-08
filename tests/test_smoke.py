#!/usr/bin/env python3
"""
Gondola v2.2 - Smoke Tests
Quick verification that core functionality works.
"""

import os
import sys
import json
import tempfile
import shutil
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestImports(unittest.TestCase):
    """Test that all modules import correctly"""
    
    def test_core_imports(self):
        """Test core module imports"""
        from venice.core import MODELS, get_model_config
        self.assertIsInstance(MODELS, dict)
        self.assertTrue(len(MODELS) > 0)
    
    def test_workspace_import(self):
        """Test workspace import"""
        from venice.workspace import Workspace
        self.assertTrue(callable(Workspace))
    
    def test_memory_import(self):
        """Test memory import"""
        from venice.memory import Memory
        self.assertTrue(callable(Memory))
    
    def test_tools_import(self):
        """Test tools import"""
        from venice.tools import CombinedTools
        self.assertTrue(callable(CombinedTools))
    
    def test_agent_state_import(self):
        """Test agent state import"""
        from venice.agent_state import AgentState
        self.assertTrue(callable(AgentState))
    
    def test_project_index_import(self):
        """Test project index import"""
        from venice.project_index import ProjectIndex
        self.assertTrue(callable(ProjectIndex))
    
    def test_context_manager_import(self):
        """Test context manager import"""
        from venice.context_manager import ContextManager
        self.assertTrue(callable(ContextManager))


class TestWorkspace(unittest.TestCase):
    """Test workspace sandbox functionality"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from venice.workspace import Workspace
        self.ws = Workspace(self.tmpdir)
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_file_creation(self):
        """Test file creation within workspace"""
        test_file = os.path.join(self.tmpdir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("hello")
        
        resolved = self.ws._resolve("test.txt")
        self.assertTrue(os.path.exists(resolved))
    
    def test_security_blocks_outside_paths(self):
        """Test that outside paths are blocked"""
        with self.assertRaises(ValueError):
            self.ws._resolve("/etc/passwd")
    
    def test_security_blocks_traversal(self):
        """Test that path traversal is blocked"""
        with self.assertRaises(ValueError):
            self.ws._resolve("../../../etc/passwd")


class TestMemory(unittest.TestCase):
    """Test memory persistence"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from venice.memory import Memory
        self.mem = Memory(self.tmpdir)
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_add_note(self):
        """Test adding a note"""
        self.mem.add_note("Test note")
        self.assertTrue(os.path.exists(self.mem.memory_file))
    
    def test_persistence(self):
        """Test that notes persist across instances"""
        from venice.memory import Memory
        self.mem.add_note("Test note")
        
        mem2 = Memory(self.tmpdir)
        self.assertTrue(len(mem2.data["project_notes"]) > 0)


class TestAgentState(unittest.TestCase):
    """Test agent state tracking"""
    
    def setUp(self):
        from venice.agent_state import AgentState
        self.state = AgentState()
    
    def test_task_description(self):
        """Test setting task description"""
        self.state.task_description = "Test task"
        self.assertEqual(self.state.task_description, "Test task")
    
    def test_file_read_tracking(self):
        """Test file read tracking"""
        self.state.record_file_read("test.py", "content", 10)
        self.assertTrue(self.state.was_file_read("test.py"))
    
    def test_turn_counting(self):
        """Test turn counting"""
        self.state.record_turn()
        self.assertEqual(self.state.turn_count, 1)


class TestTools(unittest.TestCase):
    """Test basic tool operations"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from venice.workspace import Workspace
        from venice.tools import CombinedTools
        self.ws = Workspace(self.tmpdir)
        self.tools = CombinedTools(self.ws)
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_list_files(self):
        """Test list_files tool"""
        result = self.tools.list_files(".", recursive=False)
        self.assertTrue(result["success"])
    
    def test_write_file(self):
        """Test write_file tool"""
        result = self.tools.write_file("test.txt", "Hello World")
        self.assertTrue(result["success"])
    
    def test_read_file(self):
        """Test read_file tool"""
        self.tools.write_file("test.txt", "Hello World")
        result = self.tools.read_file("test.txt")
        self.assertTrue(result["success"])
        self.assertEqual(result["content"], "Hello World")


class TestAPIKeys(unittest.TestCase):
    """Test API key loading"""
    
    def test_api_key_loading(self):
        """Test that API key loading doesn't crash"""
        from venice.api import get_api_key, get_together_api_key
        
        # Should return None or placeholder without real keys (not crash)
        key = get_api_key()
        together_key = get_together_api_key()
        
        # Just verify no exception raised - key can be None or placeholder
        self.assertTrue(key is None or isinstance(key, str))


def run_smoke_tests():
    """Run all smoke tests with verbose output"""
    print("=" * 60)
    print("GONDOLA v2.2 - SMOKE TESTS")
    print("=" * 60)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestImports))
    suite.addTests(loader.loadTestsFromTestCase(TestWorkspace))
    suite.addTests(loader.loadTestsFromTestCase(TestMemory))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentState))
    suite.addTests(loader.loadTestsFromTestCase(TestTools))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIKeys))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 60)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_smoke_tests())
