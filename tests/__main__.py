#!/usr/bin/env python3
"""
Allow running tests as a module: python -m tests
"""

from tests.test_runner import main

if __name__ == "__main__":
    import sys
    sys.exit(main())
