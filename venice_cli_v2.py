#!/usr/bin/env python3
"""
Venice CLI v2 - Modular Entry Point
"""
import sys
import os

# Add current directory to path so 'venice' package is found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from venice.cli import main

if __name__ == "__main__":
    main()
