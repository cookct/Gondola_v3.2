#!/usr/bin/env python3
import inspect
import sys
import os

# Add current directory to path so we can import venice
sys.path.append(os.getcwd())

from venice.tools import CombinedTools
from venice.tools.schema import TOOL_SCHEMAS
from venice.workspace import Workspace

def check_signatures():
    try:
        workspace = Workspace(".")
    except Exception:
        # Create dummy workspace if needed
        workspace = None
        
    # We can inspect the class without instantiating fully if init fails
    # But CombinedTools.__init__ is simple
    try:
        tools = CombinedTools(workspace)
    except Exception as e:
        print(f"Failed to instantiate tools: {e}")
        return

    schema_map = {s['function']['name']: s['function'] for s in TOOL_SCHEMAS}
    
    errors = []
    
    print(f"Checking {len(schema_map)} tools against implementation...")
    
    for tool_name, schema in schema_map.items():
        if not hasattr(tools, tool_name):
            errors.append(f"Method {tool_name} not found in CombinedTools")
            continue
            
        method = getattr(tools, tool_name)
        sig = inspect.signature(method)
        params = sig.parameters
        
        schema_props = schema['parameters'].get('properties', {})
        required_params = schema['parameters'].get('required', [])
        
        # 1. Check Python params vs Schema properties
        for param_name, param in params.items():
            if param_name == 'self': continue
            
            if param_name not in schema_props:
                # print(f"  Note: {tool_name} has extra python param '{param_name}' not in schema")
                continue
                
            is_required_in_schema = param_name in required_params
            has_default_in_python = param.default != inspect.Parameter.empty
            
            if not is_required_in_schema and not has_default_in_python:
                errors.append(f"{tool_name}: '{param_name}' is OPTIONAL in schema but REQUIRED in Python (no default value)")
                
        # 2. Check Schema properties vs Python params
        for prop_name in schema_props:
            if prop_name not in params:
                errors.append(f"{tool_name}: Schema property '{prop_name}' missing from Python method")

    if errors:
        print("\n❌ Signature mismatches found:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n✅ All signatures match schema requirements!")
        sys.exit(0)

if __name__ == "__main__":
    check_signatures()
