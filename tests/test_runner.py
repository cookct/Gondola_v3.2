#!/usr/bin/env python3
"""
Gondola v2.2 - Unified Test Runner
Runs all tests with proper structure and reporting.
"""

import os
import sys
import subprocess
import unittest
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class GitIntegration:
    """Git integration for test suite"""
    
    @staticmethod
    def get_modified_files():
        """Get list of modified files from git status"""
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                check=True
            )
            
            modified = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    status = line[:2]
                    filename = line[3:]
                    modified.append({
                        'status': status.strip(),
                        'filename': filename
                    })
            return modified
        except subprocess.CalledProcessError:
            return []
    
    @staticmethod
    def get_untracked_files():
        """Get list of untracked files"""
        try:
            result = subprocess.run(
                ['git', 'ls-files', '--others', '--exclude-standard'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip().split('\n') if result.stdout.strip() else []
        except subprocess.CalledProcessError:
            return []
    
    @staticmethod
    def get_last_commit():
        """Get last commit info"""
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--oneline'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "No git history"
    
    @staticmethod
    def get_branch():
        """Get current git branch"""
        try:
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "unknown"


class TestReporter:
    """Custom test reporter with enhanced output"""
    
    def __init__(self, stream=sys.stdout, verbosity=2):
        self.stream = stream
        self.verbosity = verbosity
        self.results = []
    
    def print_header(self, title):
        """Print a formatted header"""
        self.stream.write("\n" + "=" * 70 + "\n")
        self.stream.write(f"  {title}\n")
        self.stream.write("=" * 70 + "\n")
    
    def print_section(self, title):
        """Print a section header"""
        self.stream.write("\n" + "-" * 70 + "\n")
        self.stream.write(f"  {title}\n")
        self.stream.write("-" * 70 + "\n")
    
    def print_git_status(self):
        """Print git status information"""
        self.print_section("GIT INTEGRATION")
        
        git = GitIntegration()
        
        # Branch info
        branch = git.get_branch()
        last_commit = git.get_last_commit()
        self.stream.write(f"\nBranch: {branch}\n")
        self.stream.write(f"Last commit: {last_commit}\n")
        
        # Modified files
        modified = git.get_modified_files()
        if modified:
            self.stream.write(f"\nModified files ({len(modified)}):\n")
            for file in modified[:10]:  # Show first 10
                status_map = {
                    'M': 'Modified',
                    'A': 'Added',
                    'D': 'Deleted',
                    'R': 'Renamed',
                    'C': 'Copied',
                    'U': 'Updated',
                    '??': 'Untracked'
                }
                status_desc = status_map.get(file['status'], file['status'])
                self.stream.write(f"  [{status_desc:10}] {file['filename']}\n")
            if len(modified) > 10:
                self.stream.write(f"  ... and {len(modified) - 10} more\n")
        else:
            self.stream.write("\nNo modified files\n")
        
        # Untracked files
        untracked = git.get_untracked_files()
        if untracked and untracked[0]:  # Check if not empty string
            self.stream.write(f"\nUntracked files: {len(untracked)}\n")


def discover_and_run_tests(test_dir='tests', pattern='test_*.py', verbosity=2, failfast=False):
    """Discover and run all tests"""
    
    reporter = TestReporter(verbosity=verbosity)
    
    # Print header
    reporter.print_header("GONDOLA v2.2 - UNIFIED TEST SUITE")
    reporter.stream.write(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Git integration
    reporter.print_git_status()
    
    # Discover tests
    reporter.print_section("DISCOVERING TESTS")
    
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    
    suite = loader.discover(start_dir, pattern=pattern)
    
    # Count tests
    test_count = suite.countTestCases()
    reporter.stream.write(f"\nFound {test_count} tests\n")
    
    if test_count == 0:
        reporter.stream.write("\n⚠️  No tests found!\n")
        return 1
    
    # Run tests
    reporter.print_section("RUNNING TESTS")
    
    runner = unittest.TextTestRunner(verbosity=verbosity, failfast=failfast)
    result = runner.run(suite)
    
    # Print summary
    reporter.print_section("TEST SUMMARY")
    reporter.stream.write(f"\nTests run: {result.testsRun}\n")
    reporter.stream.write(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}\n")
    reporter.stream.write(f"Failures: {len(result.failures)}\n")
    reporter.stream.write(f"Errors: {len(result.errors)}\n")
    reporter.stream.write(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}\n")
    
    # Print failures and errors in detail
    if result.failures:
        reporter.print_section("FAILURES")
        for test, traceback in result.failures:
            reporter.stream.write(f"\n{test}\n")
            reporter.stream.write(f"{traceback}\n")
    
    if result.errors:
        reporter.print_section("ERRORS")
        for test, traceback in result.errors:
            reporter.stream.write(f"\n{test}\n")
            reporter.stream.write(f"{traceback}\n")
    
    # Final status
    reporter.print_header("FINAL STATUS")
    if result.wasSuccessful():
        reporter.stream.write("\n✓ ALL TESTS PASSED\n")
        reporter.stream.write("🎉 Gondola v2.2 is ready for action!\n\n")
        return 0
    else:
        reporter.stream.write("\n✗ SOME TESTS FAILED\n")
        reporter.stream.write("⚠️  Please review the failures above\n\n")
        return 1


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Gondola v2.2 - Unified Test Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/test_runner.py           # Run all tests
  python tests/test_runner.py -v        # Verbose output
  python tests/test_runner.py --failfast # Stop on first failure
  python -m tests                       # Run as module
        """
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--failfast',
        action='store_true',
        help='Stop on first failure'
    )
    parser.add_argument(
        '--pattern',
        default='test_*.py',
        help='Test file pattern (default: test_*.py)'
    )
    
    args = parser.parse_args()
    
    verbosity = 2 if args.verbose else 1
    
    return discover_and_run_tests(
        pattern=args.pattern,
        verbosity=verbosity,
        failfast=args.failfast
    )


if __name__ == "__main__":
    sys.exit(main())
