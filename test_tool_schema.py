#!/usr/bin/env python3
"""
Test script to verify the tool schema is complete and valid
"""

import sys
from venice.tools.schema import TOOL_SCHEMAS
from venice.tools import CombinedTools
from venice.workspace import Workspace
from venice.core import Colors

def test_schema_completeness():
    """Verify all public methods have schema entries"""
    print("Testing schema completeness...\n")
    
    # Get all public methods from CombinedTools
    workspace = Workspace(".")
    tools = CombinedTools(workspace)
    
    public_methods = [
        method for method in dir(tools)
        if not method.startswith('_') and callable(getattr(tools, method))
    ]
    
    # Filter out internal helpers
    internal_methods = {'set_steps', 'next_step'}
    public_methods = [m for m in public_methods if m not in internal_methods]
    
    # Get schema tool names
    schema_tools = {schema['function']['name'] for schema in TOOL_SCHEMAS}
    
    print(f"Public methods in CombinedTools: {len(public_methods)}")
    print(f"Tools in schema: {len(schema_tools)}")
    
    # Check for missing schemas
    missing = set(public_methods) - schema_tools
    if missing:
        print(f"\n{Colors.RED}✗ Missing schemas for:{Colors.RESET}")
        for m in sorted(missing):
            print(f"  - {m}")
        return False
    
    # Check for extra schemas
    extra = schema_tools - set(public_methods)
    if extra:
        print(f"\n{Colors.YELLOW}⚠ Extra schemas (not implemented):{Colors.RESET}")
        for m in sorted(extra):
            print(f"  - {m}")
    
    print(f"\n{Colors.GREEN}✓ All public methods have schemas!{Colors.RESET}")
    return True

def test_schema_structure():
    """Verify schema structure is valid"""
    print("\nTesting schema structure...\n")
    
    required_keys = ['type', 'function']
    function_keys = ['name', 'description', 'parameters']
    param_keys = ['type', 'properties']
    
    errors = []
    
    for i, schema in enumerate(TOOL_SCHEMAS):
        tool_name = schema.get('function', {}).get('name', f'Tool #{i}')
        
        # Check top-level structure
        for key in required_keys:
            if key not in schema:
                errors.append(f"{tool_name}: Missing '{key}' at top level")
        
        if 'function' not in schema:
            continue
            
        func = schema['function']
        
        # Check function structure
        for key in function_keys:
            if key not in func:
                errors.append(f"{tool_name}: Missing '{key}' in function")
        
        if 'parameters' not in func:
            continue
            
        params = func['parameters']
        
        # Check parameters structure
        for key in param_keys:
            if key not in params:
                errors.append(f"{tool_name}: Missing '{key}' in parameters")
        
        # Check properties exist
        if 'properties' in params and not params['properties']:
            # It's OK to have empty properties (no parameters)
            pass
    
    if errors:
        print(f"{Colors.RED}✗ Schema structure errors:{Colors.RESET}")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print(f"{Colors.GREEN}✓ All schemas have valid structure!{Colors.RESET}")
    return True

def test_schema_details():
    """Print detailed schema information"""
    print("\nSchema Details:\n")
    print("=" * 70)
    
    # Group by category
    categories = {
        'File Reading': ['list_files', 'read_file', 'get_file_info', 'search_content'],
        'File Writing': ['write_file', 'write_constant', 'edit_file', 'replace_lines', 
                        'insert_at_line', 'delete_lines', 'append_to_file'],
        'File Management': ['delete_file', 'move_file', 'copy_file', 'make_directory', 
                           'delete_directory'],
        'Code Analysis': ['validate_syntax', 'find_functions', 'find_classes', 
                         'map_project', 'extract_symbol'],
        'Shell': ['run_command'],
        'Memory': ['remember', 'recall', 'forget', 'set_preference'],
        'Backup': ['list_backups', 'restore_backup', 'undo_edit'],
        'Control': ['done']
    }
    
    schema_map = {s['function']['name']: s for s in TOOL_SCHEMAS}
    
    for category, tools in categories.items():
        print(f"\n{Colors.CYAN}{Colors.BOLD}{category}:{Colors.RESET}")
        for tool in tools:
            if tool in schema_map:
                schema = schema_map[tool]
                desc = schema['function']['description']
                params = schema['function']['parameters'].get('properties', {})
                required = schema['function']['parameters'].get('required', [])
                
                print(f"  • {Colors.BOLD}{tool}{Colors.RESET}")
                print(f"    {desc}")
                if params:
                    req_str = f" ({len(required)} required)" if required else ""
                    print(f"    Parameters: {len(params)}{req_str}")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    print("=" * 70)
    print("Tool Schema Verification Test")
    print("=" * 70)
    print()
    
    try:
        result1 = test_schema_completeness()
        result2 = test_schema_structure()
        test_schema_details()
        
        if result1 and result2:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ ALL SCHEMA TESTS PASSED{Colors.RESET}")
            print("\nThe tool schema is complete and valid!")
            sys.exit(0)
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}✗ SOME TESTS FAILED{Colors.RESET}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n{Colors.RED}✗ TEST ERROR: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
