"""
Configuration and constants for Venice CLI
"""

import os

# Default settings
DEFAULT_MODEL = "moonshotai/Kimi-K2.5"
DEFAULT_WORKSPACE = "."  # Current directory by default
# SCRIPT_DIR should point to the parent directory (where venice_cli_v2.py lives)
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))