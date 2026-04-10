"""
Configuration and constants for Venice CLI
"""

import os

# Default settings

DEFAULT_MODEL = "glm-5"

DEFAULT_WORKSPACE = "."  # Current directory by default

# SCRIPT_DIR should point to the parent directory

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PERSONALITY_FILE = os.path.join(SCRIPT_DIR, '.personality_config')
AVATAR_EXPRESSIONS_FILE = os.path.join(SCRIPT_DIR, '.avatar_expressions_enabled')
EDIT_MODEL_FILE = os.path.join(SCRIPT_DIR, '.edit_model')
