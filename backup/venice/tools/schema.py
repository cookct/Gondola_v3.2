"""
OpenAI-compatible function schemas for Venice native tool use
"""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory with optional recursion and pattern matching.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list (default '.')"},
                    "pattern": {"type": "string", "description": "Optional substring to filter filenames"},
                    "recursive": {"type": "boolean", "description": "Whether to list subdirectories (default true)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file with optional line range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file"},
                    "start_line": {"type": "integer", "description": "Starting line number (1-indexed)"},
                    "end_line": {"type": "integer", "description": "Ending line number"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get file metadata including size, modification time, and line count.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_content",
            "description": "Search for text patterns in files using regex.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "Directory path to search in (default '.')"},
                    "file_pattern": {"type": "string", "description": "Optional filename filter"},
                    "ignore_case": {"type": "boolean", "description": "Case-insensitive search (default true)"}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_constant",
            "description": "Recommended for writing code. Saves a string to a Python file as a variable. Handles escaping automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File to write to (e.g. 'script.py')"},
                    "variable_name": {"type": "string", "description": "Variable name (e.g. 'CODE')"},
                    "value": {"type": "string", "description": "The raw code/text content."}
                },
                "required": ["filename", "variable_name", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with automatic syntax verification for Python and JSON.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to save the file"},
                    "content": {"type": "string", "description": "The file content."}
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Laser-targeted edit with strict matching and automatic verification. Searches for old_text and replaces with new_text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file"},
                    "old_text": {"type": "string", "description": "Exact text to find (must be unique)"},
                    "new_text": {"type": "string", "description": "Replacement text"},
                    "occurrence": {"type": "integer", "description": "Which occurrence to replace (default 1, 0 for all)"},
                    "expected_hash": {"type": "string", "description": "Optional file hash for verification"},
                    "dry_run": {"type": "boolean", "description": "Preview changes without saving (default false)"}
                },
                "required": ["filename", "old_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_lines",
            "description": "Replace specific line range in a file with new content. More reliable than text matching.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file"},
                    "start_line": {"type": "integer", "description": "Starting line number (1-indexed)"},
                    "end_line": {"type": "integer", "description": "Ending line number (inclusive)"},
                    "new_content": {"type": "string", "description": "New content to insert"},
                    "expected_hash": {"type": "string", "description": "Optional file hash for verification"},
                    "dry_run": {"type": "boolean", "description": "Preview changes without saving (default false)"}
                },
                "required": ["filename", "start_line", "end_line", "new_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "insert_at_line",
            "description": "Insert content at a specific line number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file"},
                    "line_number": {"type": "integer", "description": "Line number to insert at (1-indexed)"},
                    "content": {"type": "string", "description": "Content to insert"}
                },
                "required": ["filename", "line_number", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_lines",
            "description": "Delete specific lines from a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file"},
                    "start_line": {"type": "integer", "description": "Starting line number (1-indexed)"},
                    "end_line": {"type": "integer", "description": "Ending line number (default: same as start_line)"}
                },
                "required": ["filename", "start_line"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_file",
            "description": "Append content to the end of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to append"}
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file to delete"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Move or rename a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source file path"},
                    "destination": {"type": "string", "description": "Destination file path"}
                },
                "required": ["source", "destination"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copy a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source file/directory path"},
                    "destination": {"type": "string", "description": "Destination file/directory path"}
                },
                "required": ["source", "destination"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "make_directory",
            "description": "Create a directory (creates parent directories as needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to create"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_directory",
            "description": "Delete a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to delete"},
                    "recursive": {"type": "boolean", "description": "Delete contents recursively (default false)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command in the workspace with environment awareness.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to run"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_syntax",
            "description": "Check if a file has valid syntax (supports Python, JSON, JavaScript).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file to validate"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_functions",
            "description": "List all functions in a Python or JavaScript file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_classes",
            "description": "List all classes in a Python file or selectors in a CSS file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "map_project",
            "description": "Generate a structural tree of the project with symbol summaries (classes/funcs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_depth": {"type": "integer", "description": "Recursion depth (default 2)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_symbol",
            "description": "Robustly extract a variable, function, or class from a Python file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_file": {"type": "string", "description": "Path to the source file"},
                    "symbol_name": {"type": "string", "description": "Name of the symbol to extract"},
                    "target_file": {"type": "string", "description": "Optional path to save extracted code to"}
                },
                "required": ["source_file", "symbol_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save a note to persistent memory for future sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note": {"type": "string", "description": "Note to remember"}
                },
                "required": ["note"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Recall all stored memories from previous sessions.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "forget",
            "description": "Clear stored memories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "clear_all": {"type": "boolean", "description": "Clear all memories including preferences (default false)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_preference",
            "description": "Set a user preference that persists across sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Preference key"},
                    "value": {"type": "string", "description": "Preference value"}
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_backups",
            "description": "List available backup files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Optional: filter backups for specific file"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "restore_backup",
            "description": "Restore a file from a backup.",
            "parameters": {
                "type": "object",
                "properties": {
                    "backup_name": {"type": "string", "description": "Name of the backup file"},
                    "target_filename": {"type": "string", "description": "Optional: target filename to restore to"}
                },
                "required": ["backup_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "undo_edit",
            "description": "Restore the most recent backup of a file (quick undo).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File to undo changes for"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Signal that the requested task is fully complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Short summary of work done"}
                },
                "required": ["summary"]
            }
        }
    }
]
