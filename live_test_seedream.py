#!/usr/bin/env python3
import os
import sys
import json

# Add current directory to path so we can import venice
sys.path.append(os.getcwd())

from venice.tools import CombinedTools
from venice.workspace import Workspace
from venice.core import UI

def live_test():
    print("Starting Live Test for Seedream Image Generation...")
    
    test_dir = "test_workspace_live"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    
    workspace = Workspace(test_dir)
    tools = CombinedTools(workspace)
    
    # Test 1: Generate Image
    prompt = "A small, simple 2D pixel art icon of a red apple on a white background."
    filename = "test_seedream_gen.png"
    
    print(f"Calling generate_image with prompt: '{prompt}'")
    result = tools.generate_image(prompt=prompt, filename=filename)
    
    print("\nResult:")
    print(json.dumps(result, indent=2))
    
    if result.get("success"):
        image_path = result.get("path")
        if image_path and os.path.exists(image_path):
            print(f"\n✅ SUCCESS: Image generated and saved to {image_path}")
            print(f"File size: {os.path.getsize(image_path)} bytes")
        else:
            print(f"\n❌ FAILURE: API said success but file not found at {image_path}")
    else:
        print(f"\n❌ FAILURE: {result.get('error')}")

    # Test 2: Edit Image (if first succeeded)
    if result.get("success"):
        # We need to make sure the reference image is where edit_image expects it or provide path
        # edit_image expects reference_image to be relative to workspace or in gondola images
        
        # Copy the generated image to where edit_image might find it easily for testing
        ref_name = "ref_for_edit.png"
        ref_path = os.path.join(test_dir, ref_name)
        import shutil
        shutil.copy2(result["path"], ref_path)
        
        edit_prompt = "Make the apple green."
        print(f"\nCalling edit_image with prompt: '{edit_prompt}' using reference: {ref_name}")
        
        edit_result = tools.edit_image(prompt=edit_prompt, reference_image=ref_name)
        
        print("\nEdit Result:")
        # Don't print huge base64
        if "image_base64" in edit_result:
            b64 = edit_result.pop("image_base64")
            print(json.dumps(edit_result, indent=2))
            edit_result["image_base64"] = b64
        else:
            print(json.dumps(edit_result, indent=2))
            
        if edit_result.get("success"):
            print(f"\n✅ SUCCESS: Image edited and saved to {edit_result.get('path')}")
        else:
            print(f"\n❌ FAILURE: {edit_result.get('error')}")

if __name__ == "__main__":
    live_test()
