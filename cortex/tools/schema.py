"""
OpenAI-compatible function schemas for Cortex native tool use
"""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "save_knowledge",
            "description": "Save knowledge or solutions for later retrieval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "knowledge": {"type": "string", "description": "The knowledge or solution to save"},
                    "keywords": {"type": "string", "description": "Keywords or tags for the knowledge"}
                },
                "required": ["knowledge", "keywords"]
            }
        }
    },
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
            "name": "search_file_content",
            "description": "FAST, optimized search powered by `ripgrep`. Returns matches with optional context lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "The pattern to search for (regex supported)"},
                    "path": {"type": "string", "description": "Directory or file to search (default '.')"},
                    "include": {"type": "string", "description": "Glob pattern to filter files (e.g. '*.ts', 'src/**')"},
                    "ignore_case": {"type": "boolean", "description": "If true, search is case-insensitive (default true)"},
                    "context": {"type": "integer", "description": "Number of context lines to show around matches"},
                    "before": {"type": "integer", "description": "Number of lines before each match"},
                    "after": {"type": "integer", "description": "Number of lines after each match"}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "begin_transaction",
            "description": "Start a multi-file atomic transaction. All subsequent edits (write_file, edit_file, replace_lines) will be buffered in a staging area and NOT applied to disk until commit_transaction is called.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "commit_transaction",
            "description": "Apply all buffered changes from the current transaction to disk simultaneously. Verifies syntax for ALL files before applying any. If one file fails validation, the entire transaction is rolled back.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dry_run": {"type": "boolean", "description": "Preview changes without applying them (default false)"}
                }
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
                    "thought": {"type": "string", "description": "Your reasoning for this edit (e.g. 'fixing the bug in the auth loop'). Used for better error reporting on failure."},
                    "expected_hash": {"type": "string", "description": "Optional file hash for verification"},
                    "dry_run": {"type": "boolean", "description": "Preview changes without saving (default false)"},
                    "verify_risk": {"type": "boolean", "description": "NEW: Override flag to proceed with high-risk edits after manual verification (default false)"}
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
                    "thought": {"type": "string", "description": "Your reasoning for this edit. Used for better error reporting on failure."},
                    "expected_hash": {"type": "string", "description": "Optional file hash for verification"},
                    "dry_run": {"type": "boolean", "description": "Preview changes without saving (default false)"},
                    "verify_risk": {"type": "boolean", "description": "NEW: Override flag to proceed with high-risk edits after manual verification (default false)"}
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
            "name": "semantic_search",
            "description": "Find files by meaning rather than keywords. Best for 'conceptual' searches (e.g. 'where is auth handled?').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Conceptual search query (e.g. 'how are themes applied?')"},
                    "max_results": {"type": "integer", "description": "Maximum number of files to return (default 5)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_skeleton",
            "description": "Get structural map of a file (classes/methods) with exact line ranges using Tree-sitter.",
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
            "name": "symbol_jump",
            "description": "Project-wide search for a symbol definition (class/function) using Ctags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol_name": {"type": "string", "description": "Name of the symbol to find"}
                },
                "required": ["symbol_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_symbol_coordinates",
            "description": "Find exact line:column coordinates for a symbol (class, function, variable) using Tree-sitter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file"},
                    "symbol_name": {"type": "string", "description": "Name of the symbol to find"}
                },
                "required": ["filename", "symbol_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_type",
            "description": "Perform a deep 'autopsy' on a symbol to find its type, signature, and docstrings using Jedi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file"},
                    "symbol": {"type": "string", "description": "Symbol name to inspect"}
                },
                "required": ["filename", "symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Signal that a multi-step CODING task is fully complete. IMPORTANT: You MUST provide a natural language summary of your work in the chat window BEFORE calling this tool. Do NOT use for simple questions - just respond with text. For conversations and questions, respond directly without calling any tools.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Short summary of coding work completed (files created/edited)"}
                },
                "required": ["summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "multi_edit",
            "description": "Apply multiple edits across multiple files atomically. All edits succeed or all fail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "edits": {
                        "type": "array",
                        "description": "List of edit operations",
                        "items": {
                            "type": "object",
                            "properties": {
                                "filename": {"type": "string", "description": "File to edit"},
                                "old_text": {"type": "string", "description": "Text to find and replace"},
                                "new_text": {"type": "string", "description": "Replacement text"}
                            },
                            "required": ["filename", "old_text", "new_text"]
                        }
                    }
                },
                "required": ["edits"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "smart_context",
            "description": "Intelligently gather context for a file by finding related files (imports, same directory, tests).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File to gather context for"},
                    "depth": {"type": "integer", "description": "How many related files to include (default 2)"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "batch_read",
            "description": "Read multiple files efficiently in one operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "description": "List of filenames to read",
                        "items": {"type": "string"}
                    }
                },
                "required": ["files"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_and_replace",
            "description": "Find and replace across multiple files with preview. Use dry_run=True first to see what would change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "replacement": {"type": "string", "description": "Replacement text"},
                    "path": {"type": "string", "description": "Directory to search in (default '.')"},
                    "file_pattern": {"type": "string", "description": "Optional glob pattern to filter files (e.g. '*.py')"},
                    "dry_run": {"type": "boolean", "description": "If True, only show what would be changed (default True)"}
                },
                "required": ["pattern", "replacement"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Get git repository status including staged, unstaged, and untracked files.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Get git diff showing changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "staged": {"type": "boolean", "description": "Show staged changes (default False)"},
                    "file": {"type": "string", "description": "Show diff for specific file only"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Get git commit history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "description": "Number of commits to show (default 10)"},
                    "file": {"type": "string", "description": "Show commits affecting this file only"},
                    "author": {"type": "string", "description": "Filter by author"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_blame",
            "description": "Get git blame showing who wrote each line.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File to blame"},
                    "start_line": {"type": "integer", "description": "Start line number"},
                    "end_line": {"type": "integer", "description": "End line number"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_commit_message",
            "description": "Analyze staged changes and suggest a commit message.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information using DuckDuckGo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "n_results": {"type": "integer", "description": "Number of results (default 5)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch and extract content from a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "max_length": {"type": "integer", "description": "Max characters to return (default 10000)"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "Search documentation for popular libraries (Python, React, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "library": {"type": "string", "description": "Library name (e.g., 'python', 'react', 'numpy')"},
                    "query": {"type": "string", "description": "What to search for"},
                    "version": {"type": "string", "description": "Specific version (optional)"}
                },
                "required": ["library", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_stackoverflow",
            "description": "Search Stack Overflow for solutions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags to filter by"},
                    "n_results": {"type": "integer", "description": "Number of results (default 5)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_github",
            "description": "Search GitHub repositories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "language": {"type": "string", "description": "Filter by language"},
                    "sort": {"type": "string", "enum": ["stars", "updated", "best-match"], "description": "Sort by"},
                    "n_results": {"type": "integer", "description": "Number of results (default 5)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "image_search",
            "description": "Search for images on the web.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "n_results": {"type": "integer", "description": "Number of results (default 10)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "download_image",
            "description": "Download an image from any direct URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Direct URL to the image"},
                    "filename": {"type": "string", "description": "Optional: filename to save as (e.g. 'photo.jpg')"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "download_placeholder_image",
            "description": "Download a placeholder image for web design from free placeholder services. Supports picsum (random photos), placehold (solid color with text), and via (custom text).",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Optional keyword for image selection or text overlay"},
                    "width": {"type": "integer", "description": "Image width in pixels (default 800, max 4000)"},
                    "height": {"type": "integer", "description": "Image height in pixels (default 600, max 4000)"},
                    "service": {"type": "string", "enum": ["picsum", "placehold", "via"], "description": "Placeholder service (default 'picsum')"},
                    "filename": {"type": "string", "description": "Output filename (default: 'placeholder_{width}x{height}.jpg')"},
                    "grayscale": {"type": "boolean", "description": "Convert to grayscale (picsum only)"},
                    "blur": {"type": "integer", "description": "Blur amount 1-10 (picsum only)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run Python tests using pytest or unittest.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory or file to test (default '.')"},
                    "pattern": {"type": "string", "description": "Test file pattern (e.g., 'test_*.py')"},
                    "verbose": {"type": "boolean", "description": "Show detailed output"},
                    "fail_fast": {"type": "boolean", "description": "Stop on first failure"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "test_coverage",
            "description": "Run tests with coverage analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to analyze (default '.')"},
                    "output_format": {"type": "string", "enum": ["text", "json", "html"], "description": "Output format"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_test_files",
            "description": "Find all test files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search (default '.')"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_test_stub",
            "description": "Generate a test stub for a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File to generate tests for"},
                    "function_name": {"type": "string", "description": "Specific function to test (optional)"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
                            "name": "generate_image",
                            "description": "Generate an AI image using Cortex seedream-v4 model. The image will be saved to the workspace images directory.",
            
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Text description of the image to generate"},
                    "filename": {"type": "string", "description": "Output filename (auto-generated if not provided)"},
                    "width": {"type": "integer", "description": "Image width in pixels (default 1024)"},
                    "height": {"type": "integer", "description": "Image height in pixels (default 1024)"}
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_image",
            "description": "Generate an expression image. Just provide a prompt like 'happy smile' or 'shocked expression'. Uses avatar.png automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Expression description (e.g. 'happy smile', 'winking', 'shocked')"}
                },
                "required": ["prompt"]
            }
        }
    }
]
