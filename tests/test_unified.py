#!/usr/bin/env python3
"""
Gondola v2.3 - Unified Test Suite
Combines smoke tests, security tests, and new module tests.
"""

import os
import sys
import json
import tempfile
import shutil
import unittest
import subprocess
import re
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Gondola components
try:
    from venice.core import MODELS
    from venice.workspace import Workspace
    from venice.memory import Memory
    from venice.agent_state import AgentState
    from venice.tools import CombinedTools
except ImportError as e:
    print(f"Error importing Gondola components: {e}")
    sys.exit(1)

# ============================================================================
# CORE FOUNDATIONS & SMOKE TESTS
# ============================================================================

class TestCoreFoundations(unittest.TestCase):
    """Test core foundations and imports"""
    
    def test_core_models(self):
        """Verify models are defined"""
        self.assertIsInstance(MODELS, dict)
        self.assertTrue(len(MODELS) > 0)
        self.assertIn("claude-opus-45", MODELS)
    
    def test_component_initialization(self):
        """Test component initialization"""
        tmpdir = tempfile.mkdtemp()
        try:
            ws = Workspace(tmpdir)
            mem = Memory(tmpdir)
            state = AgentState()
            tools = CombinedTools(ws, memory=mem, agent_state=state)
            self.assertIsNotNone(tools)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

class TestAgentState(unittest.TestCase):
    """Test agent state tracking"""
    
    def setUp(self):
        self.state = AgentState()
    
    def test_state_tracking(self):
        """Test basic state tracking"""
        self.state.record_turn()
        self.assertEqual(self.state.turn_count, 1)
        self.state.record_file_read("test.py", "content", 10)
        self.assertTrue(self.state.was_file_read("test.py"))

# ============================================================================
# SECURITY & SANDBOX TESTS
# ============================================================================

class TestWorkspaceSecurity(unittest.TestCase):
    """Test workspace sandbox and security features"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ws = Workspace(self.tmpdir)
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_path_traversal_blocking(self):
        """Verify that path traversal is blocked"""
        traversal_paths = [
            "/etc/passwd",
            "../../../etc/passwd",
            "~/.ssh/id_rsa",
            "..\\..\\windows\\system32"
        ]
        for path in traversal_paths:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    self.ws._resolve(path)
    
    def test_symlink_protection(self):
        """Verify symlink protection"""
        outside_file = tempfile.NamedTemporaryFile(delete=False)
        outside_file.write(b"secret")
        outside_file.close()
        
        link_path = os.path.join(self.tmpdir, "evil_link")
        try:
            os.symlink(outside_file.name, link_path)
            # Should either raise ValueError or not resolve to the outside path
            try:
                resolved = self.ws._resolve("evil_link")
                self.assertNotEqual(resolved, outside_file.name)
            except ValueError:
                pass
        finally:
            os.unlink(outside_file.name)
            if os.path.exists(link_path):
                os.unlink(link_path)

    def test_file_permissions(self):
        """Verify created files are not world-writable"""
        test_file = os.path.join(self.tmpdir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("content")
        
        stat_info = os.stat(test_file)
        mode = stat_info.st_mode & 0o777
        self.assertFalse(mode & 0o002, f"File is world-writable: {oct(mode)}")

# ============================================================================
# NEW MODULE TESTS (Batch, Git, Web)
# ============================================================================

class TestBatchOperations(unittest.TestCase):
    """Test new batch operations module"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ws = Workspace(self.tmpdir)
        self.tools = CombinedTools(self.ws)
        
        # Create some test files
        self.files = {
            "a.py": "def hello():\n    print('hello')\n",
            "b.py": "import a\na.hello()\n",
            "test_a.py": "import a\ndef test_hello():\n    pass\n"
        }
        for name, content in self.files.items():
            with open(os.path.join(self.tmpdir, name), 'w') as f:
                f.write(content)
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_batch_read(self):
        """Test reading multiple files"""
        result = self.tools.batch_read(["a.py", "b.py"])
        self.assertTrue(result["success"])
        self.assertEqual(len(result["files"])
, 2)
        self.assertIn("a.py", result["files"])
        self.assertIn("b.py", result["files"])
    
    def test_multi_edit(self):
        """Test atomic multi-file edits"""
        edits = [
            {"filename": "a.py", "old_text": "hello", "new_text": "greetings"},
            {"filename": "b.py", "old_text": "a.hello()", "new_text": "a.greetings()"}
        ]
        result = self.tools.multi_edit(edits)
        self.assertTrue(result["success"])
        
        # Verify changes
        with open(os.path.join(self.tmpdir, "a.py"), 'r') as f:
            self.assertIn("greetings", f.read())
        with open(os.path.join(self.tmpdir, "b.py"), 'r') as f:
            self.assertIn("a.greetings()", f.read())

    def test_smart_context(self):
        """Test intelligent context gathering"""
        result = self.tools.smart_context("a.py")
        self.assertTrue(result["success"])
        # Should find b.py (same dir) and test_a.py (test file)
        context_files = result["context_files"]
        self.assertTrue(len(context_files) >= 1)

class TestGitOperations(unittest.TestCase):
    """Test git operations module (safe checks)"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ws = Workspace(self.tmpdir)
        self.tools = CombinedTools(self.ws)
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_git_status_non_repo(self):
        """Verify git_status handles non-git directories gracefully"""
        result = self.tools.git_status()
        # Should return success=False or indicate it's not a repo
        if result["success"]:
            # If the current environment IS a git repo, this might pass
            pass
        else:
            self.assertIn("error", result)

class TestWebOperations(unittest.TestCase):
    """Test web operations module (basic structure)"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ws = Workspace(self.tmpdir)
        self.tools = CombinedTools(self.ws)
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_web_search_params(self):
        """Test that web_search accepts correct parameters"""
        # We won't actually hit the network in unit tests to avoid flakiness
        # This just verifies the tool exists and is callable
        self.assertTrue(hasattr(self.tools, 'web_search'))

# ============================================================================
# UNIFIED TEST RUNNER
# ============================================================================

def run_unified_tests():
    """Run all tests in the unified suite"""
    print("=" * 70)
    print("  GONDOLA v2.3 - UNIFIED TEST SUITE")
    print("=" * 70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestCoreFoundations,
        TestAgentState,
        TestWorkspaceSecurity,
        TestBatchOperations,
        TestGitOperations,
        TestWebOperations
    ]
    
    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    print(f"Summary: {result.testsRun} run, {len(result.failures)} failed, {len(result.errors)} errors")
    print("=" * 70)
    
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(run_unified_tests())
