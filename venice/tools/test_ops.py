"""
Test Operations - Run tests, analyze coverage, find bugs
"""

import os
import re
import subprocess
import json
from typing import List, Dict, Optional
from pathlib import Path
from venice.tools.base import Tools
from venice.core import UI


class TestOpsMixin(Tools):
    """Mixin for test operations"""

    def run_tests(self, path: str = ".", pattern: str = None, verbose: bool = False, fail_fast: bool = False) -> Dict:
        """
        Run Python tests using pytest or unittest.
        
        Args:
            path: Directory or file to test
            pattern: Test file pattern (e.g., 'test_*.py')
            verbose: Show detailed output
            fail_fast: Stop on first failure
            
        Returns:
            {"success": True, "passed": int, "failed": int, "output": str} or {"success": False, "error": str}
        """
        self.next_step(f"Running tests in {path}")
        
        try:
            target = self.workspace._resolve(path)
            
            # Check if pytest is available
            result = subprocess.run(
                ["python", "-m", "pytest", "--version"],
                capture_output=True,
                cwd=self.workspace.root_dir
            )
            has_pytest = result.returncode == 0
            
            if has_pytest:
                cmd = ["python", "-m", "pytest"]
                if verbose:
                    cmd.append("-v")
                if fail_fast:
                    cmd.append("-x")
                if pattern:
                    cmd.extend(["-k", pattern])
                cmd.append(target)
            else:
                # Fall back to unittest
                cmd = ["python", "-m", "unittest", "discover", "-s", target]
                if pattern:
                    cmd.extend(["-p", pattern])
                if verbose:
                    cmd.append("-v")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.workspace.root_dir,
                timeout=300  # 5 minute timeout
            )
            
            output = result.stdout + "\n" + result.stderr
            
            # Parse pytest output
            passed = 0
            failed = 0
            errors = 0
            
            # Look for pytest summary
            summary_match = re.search(r'(\d+) passed', output)
            if summary_match:
                passed = int(summary_match.group(1))
            
            failed_match = re.search(r'(\d+) failed', output)
            if failed_match:
                failed = int(failed_match.group(1))
            
            error_match = re.search(r'(\d+) error', output)
            if error_match:
                errors = int(error_match.group(1))
            
            # If no summary found, try to count from output
            if passed == 0 and failed == 0:
                passed = len(re.findall(r'PASSED', output))
                failed = len(re.findall(r'FAILED', output))
            
            status = "passed" if result.returncode == 0 else "failed"
            
            UI.step_done(f"Tests {status}: {passed} passed, {failed} failed, {errors} errors")
            return {
                "success": True,
                "status": status,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "returncode": result.returncode,
                "output": output[-5000:] if len(output) > 5000 else output  # Limit output
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Tests timed out after 5 minutes"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def test_coverage(self, path: str = ".", output_format: str = "text") -> Dict:
        """
        Run tests with coverage analysis.
        
        Args:
            path: Directory to analyze
            output_format: 'text', 'json', or 'html'
            
        Returns:
            {"success": True, "coverage": float, "output": str} or {"success": False, "error": str}
        """
        self.next_step(f"Running coverage analysis on {path}")
        
        try:
            target = self.workspace._resolve(path)
            
            # Check if coverage is available
            result = subprocess.run(
                ["python", "-m", "coverage", "--version"],
                capture_output=True,
                cwd=self.workspace.root_dir
            )
            
            if result.returncode != 0:
                return {"success": False, "error": "coverage.py not installed. Run: pip install coverage"}
            
            # Run tests with coverage
            cmd = [
                "python", "-m", "coverage", "run",
                "--source", target,
                "-m", "pytest", target
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.workspace.root_dir,
                timeout=300
            )
            
            # Generate report
            if output_format == "json":
                report_cmd = ["python", "-m", "coverage", "json", "-o", "-"]
            elif output_format == "html":
                report_cmd = ["python", "-m", "coverage", "html"]
                subprocess.run(report_cmd, cwd=self.workspace.root_dir)
                return {
                    "success": True,
                    "message": "HTML coverage report generated in htmlcov/",
                    "report_path": "htmlcov/index.html"
                }
            else:
                report_cmd = ["python", "-m", "coverage", "report"]
            
            report_result = subprocess.run(
                report_cmd,
                capture_output=True,
                text=True,
                cwd=self.workspace.root_dir
            )
            
            output = report_result.stdout
            
            # Parse coverage percentage
            total_line = None
            for line in output.split('\n'):
                if 'TOTAL' in line or 'total' in line.lower():
                    total_line = line
                    break
            
            coverage_pct = None
            if total_line:
                match = re.search(r'(\d+)%', total_line)
                if match:
                    coverage_pct = int(match.group(1))
            
            UI.step_done(f"Coverage: {coverage_pct}%" if coverage_pct else "Coverage report generated")
            return {
                "success": True,
                "coverage": coverage_pct,
                "output": output,
                "report": output[-2000:] if len(output) > 2000 else output
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Coverage analysis timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def find_test_files(self, path: str = ".") -> Dict:
        """
        Find all test files in a directory.
        
        Returns:
            {"success": True, "test_files": [...], "count": int}
        """
        self.next_step(f"Finding test files in {path}")
        
        try:
            target = self.workspace._resolve(path)
            
            test_files = []
            test_patterns = [
                r'test_.*\.py$',
                r'.*_test\.py$',
                r'.*\.test\.js$',
                r'.*\.spec\.js$',
                r'.*\.test\.ts$',
                r'.*\.spec\.ts$',
                r'.*Test\.java$',
                r'.*Tests\.java$',
            ]
            
            for root, dirs, files in os.walk(target):
                # Skip hidden and common non-test directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.venv']]
                
                for filename in files:
                    for pattern in test_patterns:
                        if re.match(pattern, filename):
                            full_path = os.path.join(root, filename)
                            rel_path = os.path.relpath(full_path, self.workspace.root_dir)
                            test_files.append(rel_path)
                            break
            
            # Sort by path
            test_files.sort()
            
            UI.step_done(f"Found {len(test_files)} test files")
            return {
                "success": True,
                "test_files": test_files,
                "count": len(test_files),
                "by_language": {
                    "python": len([f for f in test_files if f.endswith('.py')]),
                    "javascript": len([f for f in test_files if f.endswith('.js')]),
                    "typescript": len([f for f in test_files if f.endswith('.ts')]),
                    "java": len([f for f in test_files if f.endswith('.java')])
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_test_failures(self, test_output: str) -> Dict:
        """
        Analyze test output and extract failure details.
        
        Args:
            test_output: Raw test output from run_tests
            
        Returns:
            {"success": True, "failures": [...], "summary": str}
        """
        self.next_step("Analyzing test failures")
        
        failures = []
        
        # Parse pytest failures
        # Pattern: FAILED filename::test_name - error message
        pytest_pattern = r'FAILED\s+(\S+)::(\S+)\s+-\s+(.*?)(?=\n\n|\nFAILED|\Z)'
        for match in re.finditer(pytest_pattern, test_output, re.DOTALL):
            failures.append({
                "file": match.group(1),
                "test": match.group(2),
                "error": match.group(3).strip()[:500]
            })
        
        # Parse unittest failures
        # Pattern: FAIL: test_name (__main__.TestClass)
        unittest_pattern = r'FAIL:\s+(\S+)\s+\(([^)]+)\).*?\n(.*?)(?=\n\n[A-Z]|\Z)'
        for match in re.finditer(unittest_pattern, test_output, re.DOTALL):
            failures.append({
                "test": match.group(1),
                "class": match.group(2),
                "error": match.group(3).strip()[:500]
            })
        
        # Parse assertion errors
        assertion_pattern = r'AssertionError:\s+(.*?)(?=\n\n|\Z)'
        for match in re.finditer(assertion_pattern, test_output, re.DOTALL):
            if not any(f.get("error", "").startswith(match.group(1)[:100]) for f in failures):
                failures.append({
                    "type": "AssertionError",
                    "error": match.group(1).strip()[:500]
                })
        
        # Generate summary
        if failures:
            summary = f"Found {len(failures)} failures:\n"
            for i, failure in enumerate(failures[:5], 1):
                summary += f"\n{i}. "
                if "file" in failure:
                    summary += f"{failure['file']}::{failure['test']}\n"
                elif "class" in failure:
                    summary += f"{failure['class']}.{failure['test']}\n"
                else:
                    summary += f"{failure['type']}\n"
                summary += f"   {failure['error'][:200]}...\n"
            
            if len(failures) > 5:
                summary += f"\n... and {len(failures) - 5} more failures"
        else:
            summary = "No specific failures parsed from output"
        
        UI.step_done(f"Analyzed {len(failures)} failures")
        return {
            "success": True,
            "failures": failures,
            "count": len(failures),
            "summary": summary
        }

    def generate_test_stub(self, filename: str, function_name: str = None) -> Dict:
        """
        Generate a test stub for a file.
        
        Args:
            filename: File to generate tests for
            function_name: Specific function to test (optional, tests all if not specified)
            
        Returns:
            {"success": True, "test_code": str, "test_file": str}
        """
        self.next_step(f"Generating test stub for {filename}")
        
        try:
            path = self.workspace._resolve(filename)
            if not os.path.exists(path):
                return {"success": False, "error": f"File '{filename}' not found"}
            
            # Read the file
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Detect language
            if filename.endswith('.py'):
                return self._generate_python_test(filename, content, function_name)
            elif filename.endswith('.js') or filename.endswith('.ts'):
                return self._generate_js_test(filename, content, function_name)
            else:
                return {"success": False, "error": f"Unsupported language for {filename}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _generate_python_test(self, filename: str, content: str, function_name: str = None) -> Dict:
        """Generate Python test stub"""
        import ast
        
        module_name = os.path.splitext(os.path.basename(filename))[0]
        test_filename = f"test_{module_name}.py"
        
        # Parse functions and classes
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return {"success": False, "error": "Could not parse file - syntax error"}
        
        functions = []
        classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith('_'):  # Skip private
                    functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')]
                if methods:
                    classes.append({"name": node.name, "methods": methods})
        
        # Generate test code
        lines = [
            f"\"\"\"Tests for {module_name}\"\"\"",
            f"import pytest",
            f"from {module_name} import *",
            "",
        ]
        
        # Generate function tests
        if function_name:
            if function_name in functions:
                functions = [function_name]
            else:
                return {"success": False, "error": f"Function '{function_name}' not found in {filename}"}
        
        for func in functions:
            lines.extend([
                f"",
                f"def test_{func}():",
                f"    \"\"\"Test {func}\"\"\"",
                f"    # Arrange",
                f"    # TODO: Set up test data",
                f"    ",
                f"    # Act",
                f"    result = {func}()",
                f"    ",
                f"    # Assert",
                f"    # TODO: Add assertions",
                f"    assert result is not None",
            ])
        
        # Generate class tests
        for cls in classes:
            lines.extend([
                f"",
                f"class Test{cls['name']}:",
                f"    \"\"\"Tests for {cls['name']}\"\"\"",
            ])
            
            for method in cls['methods']:
                lines.extend([
                    f"    ",
                    f"    def test_{method}(self):",
                    f"        \"\"\"Test {method}\"\"\"",
                    f"        # Arrange",
                    f"        obj = {cls['name']}()",
                    f"        ",
                    f"        # Act",
                    f"        result = obj.{method}()",
                    f"        ",
                    f"        # Assert",
                    f"        assert result is not None",
                ])
        
        test_code = '\n'.join(lines)
        
        UI.step_done(f"Generated test stub with {len(functions)} functions, {len(classes)} classes")
        return {
            "success": True,
            "test_code": test_code,
            "test_file": test_filename,
            "functions_found": functions,
            "classes_found": [c['name'] for c in classes]
        }

    def _generate_js_test(self, filename: str, content: str, function_name: str = None) -> Dict:
        """Generate JavaScript test stub"""
        # Simple regex-based extraction
        module_name = os.path.splitext(os.path.basename(filename))[0]
        test_filename = f"{module_name}.test.js"
        
        # Find exports
        export_pattern = r'export\s+(?:function|const|let|var)\s+(\w+)|exports\.(\w+)\s*='
        matches = re.findall(export_pattern, content)
        functions = [m[0] or m[1] for m in matches if m[0] or m[1]]
        
        if function_name:
            if function_name in functions:
                functions = [function_name]
            else:
                return {"success": False, "error": f"Function '{function_name}' not found in {filename}"}
        
        lines = [
            f"/** @jest-environment node */",
            f"const {{{', '.join(functions)}}} = require('./{module_name}');",
            "",
        ]
        
        for func in functions:
            lines.extend([
                f"describe('{func}', () => {{",
                f"  test('should work correctly', () => {{",
                f"    // Arrange",
                f"    // TODO: Set up test data",
                f"    ",
                f"    // Act",
                f"    const result = {func}();",
                f"    ",
                f"    // Assert",
                f"    expect(result).toBeDefined();",
                f"  }});",
                f"}});",
                "",
            ])
        
        test_code = '\n'.join(lines)
        
        UI.step_done(f"Generated test stub with {len(functions)} functions")
        return {
            "success": True,
            "test_code": test_code,
            "test_file": test_filename,
            "functions_found": functions
        }
