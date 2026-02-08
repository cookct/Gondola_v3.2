#!/usr/bin/env python3
"""
Gondola v2.3 - Security Tests
Verify sandbox and security features work.
"""

import os
import sys
import tempfile
import shutil
import unittest
import stat

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPathTraversal(unittest.TestCase):
    """Test that path traversal is blocked"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from venice.workspace import Workspace
        self.ws = Workspace(self.tmpdir)
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_blocks_absolute_unix_paths(self):
        """Test blocking absolute Unix paths"""
        with self.assertRaises(ValueError):
            self.ws._resolve("/etc/passwd")
    
    def test_blocks_traversal_unix(self):
        """Test blocking Unix path traversal"""
        with self.assertRaises(ValueError):
            self.ws._resolve("../../../etc/passwd")
    
    def test_blocks_traversal_windows(self):
        """Test blocking Windows path traversal"""
        with self.assertRaises(ValueError):
            self.ws._resolve("..\\..\\..\\windows\\system32\\config\\sam")
    
    def test_blocks_ssh_key_access(self):
        """Test blocking SSH key access"""
        with self.assertRaises(ValueError):
            self.ws._resolve("~/.ssh/id_rsa")
    
    def test_blocks_root_config(self):
        """Test blocking root config access"""
        with self.assertRaises(ValueError):
            self.ws._resolve("/root/.bashrc")


class TestSymlinkProtection(unittest.TestCase):
    """Test symlink handling"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.outside_file = tempfile.NamedTemporaryFile(delete=False)
        self.outside_file.write(b"secret")
        self.outside_file.close()
        
        from venice.workspace import Workspace
        self.ws = Workspace(self.tmpdir)
        
        # Create symlink inside pointing outside
        self.link_path = os.path.join(self.tmpdir, "evil_link")
        os.symlink(self.outside_file.name, self.link_path)
    
    def tearDown(self):
        os.unlink(self.outside_file.name)
        if os.path.exists(self.link_path):
            os.unlink(self.link_path)
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_symlink_not_resolved_to_outside(self):
        """Test that symlink doesn't resolve to outside path"""
        try:
            resolved = self.ws._resolve("evil_link")
            # If we get here, check if it resolved to outside
            self.assertNotEqual(resolved, self.outside_file.name,
                              "Symlink resolved to outside path")
        except ValueError:
            # This is also acceptable - symlink was blocked
            pass


class TestAPIKeyExposure(unittest.TestCase):
    """Test that API keys aren't exposed"""
    
    def test_template_uses_placeholders(self):
        """Check app_config.json.template uses placeholder keys"""
        template_path = "app_config.json.template"
        if not os.path.exists(template_path):
            self.skipTest("Template file not found")
        
        with open(template_path) as f:
            content = f.read()
        
        # Check for placeholder patterns
        has_placeholder = (
            "YOUR_" in content or 
            "placeholder" in content.lower() or
            "YOUR_API_KEY" in content or
            "YOUR_VENICE_API_KEY" in content
        )
        self.assertTrue(has_placeholder, 
                       "Template should use placeholder keys")


class TestGitignore(unittest.TestCase):
    """Test that secrets are in .gitignore"""
    
    def setUp(self):
        if not os.path.exists(".gitignore"):
            self.skipTest("No .gitignore file")
        
        with open(".gitignore") as f:
            self.gitignore = f.read()
    
    def test_app_config_ignored(self):
        """Test app_config.json is ignored"""
        self.assertIn("app_config.json", self.gitignore,
                     "app_config.json should be in .gitignore")
    
    def test_env_ignored(self):
        """Test .env is ignored"""
        self.assertIn(".env", self.gitignore,
                     ".env should be in .gitignore")
    
    def test_key_files_ignored(self):
        """Test key files are ignored"""
        self.assertIn("*.key", self.gitignore,
                     "*.key should be in .gitignore")
    
    def test_pem_files_ignored(self):
        """Test PEM files are ignored"""
        self.assertIn("*.pem", self.gitignore,
                     "*.pem should be in .gitignore")


class TestFilePermissions(unittest.TestCase):
    """Test that created files have reasonable permissions"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from venice.workspace import Workspace
        from venice.tools import CombinedTools
        self.ws = Workspace(self.tmpdir)
        self.tools = CombinedTools(self.ws)
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_file_not_world_writable(self):
        """Test that files are not world-writable"""
        self.tools.write_file("test.txt", "content")
        
        file_path = os.path.join(self.tmpdir, "test.txt")
        self.assertTrue(os.path.exists(file_path), "File not created")
        
        stat_info = os.stat(file_path)
        mode = stat_info.st_mode & 0o777
        
        self.assertFalse(mode & 0o002,
                        f"File is world-writable: {oct(mode)}")


class TestWorkspaceSecurity(unittest.TestCase):
    """Additional workspace security tests"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from venice.workspace import Workspace
        self.ws = Workspace(self.tmpdir)
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_relative_path_allowed(self):
        """Test that relative paths within workspace are allowed"""
        # This should work fine
        resolved = self.ws._resolve("subdir/file.txt")
        expected = os.path.join(self.tmpdir, "subdir/file.txt")
        self.assertEqual(resolved, expected)
    
    def test_current_directory_allowed(self):
        """Test that current directory is allowed"""
        resolved = self.ws._resolve(".")
        self.assertEqual(resolved, self.tmpdir)


def run_security_tests():
    """Run all security tests with verbose output"""
    print("=" * 60)
    print("GONDOLA v2.3 - SECURITY TESTS")
    print("=" * 60)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPathTraversal))
    suite.addTests(loader.loadTestsFromTestCase(TestSymlinkProtection))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIKeyExposure))
    suite.addTests(loader.loadTestsFromTestCase(TestGitignore))
    suite.addTests(loader.loadTestsFromTestCase(TestFilePermissions))
    suite.addTests(loader.loadTestsFromTestCase(TestWorkspaceSecurity))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 60)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_security_tests())
