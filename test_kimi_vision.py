#!/usr/bin/env python3
"""
Test script to send images/72256.png to Kimi K2.5 via Together AI.
Uses base64-encoded image in the image_url format.
"""

import os
import sys
import base64
from pathlib import Path

# Try to import together client
try:
    from together import Together
except ImportError:
    print("Error: 'together' package not installed.")
    print("Install with: pip install together")
    sys.exit(1)

# Configuration
IMAGE_PATH = "images/72256.png"
MODEL = "moonshotai/Kimi-K2.5"

def get_together_api_key():
    """Get Together API key from environment or config."""
    # Try environment variable first
    api_key = os.environ.get("TOGETHER_API_KEY")
    if api_key:
        return api_key
    
    # Try config file
    config_paths = [
        "app_config.json",
        os.path.expanduser("~/.venice_config.json"),
    ]
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                import json
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    key = config.get("together_api_key")
                    if key and key != "YOUR_TOGETHER_API_KEY_HERE":
                        return key
            except Exception:
                pass
    
    return None

def encode_image_to_base64(image_path):
    """Encode image file to base64 string."""
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode('utf-8')
    return encoded

def test_kimi_vision():
    """Send image to Kimi K2.5 via Together AI."""
    
    # Check image exists
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: Image not found at {IMAGE_PATH}")
        sys.exit(1)
    
    print(f"📷 Loading image: {IMAGE_PATH}")
    print(f"   Size: {os.path.getsize(IMAGE_PATH) / 1024 / 1024:.2f} MB")
    
    # Get API key
    api_key = get_together_api_key()
    if not api_key:
        print("\n❌ Error: Together API key not found!")
        print("Set TOGETHER_API_KEY environment variable or add to app_config.json")
        sys.exit(1)
    
    print("🔑 API key found")
    
    # Encode image
    print("🔌 Encoding image to base64...")
    base64_image = encode_image_to_base64(IMAGE_PATH)
    print(f"   Encoded size: {len(base64_image) / 1024:.1f} KB")
    
    # Create data URL
    # Detect mime type from extension
    ext = Path(IMAGE_PATH).suffix.lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
    }
    mime_type = mime_types.get(ext, 'image/png')
    data_url = f"data:{mime_type};base64,{base64_image}"
    
    # Initialize Together client
    print(f"🚀 Initializing Together client...")
    client = Together(api_key=api_key)
    
    # Prepare messages
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image? Describe it in detail."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
    }]
    
    print(f"🤖 Sending to model: {MODEL}")
    print("   (This may take a moment...)\n")
    
    try:
        # Make API call
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        
        # Extract and print response
        content = response.choices[0].message.content
        
        print("=" * 60)
        print("✅ SUCCESS! Kimi K2.5 Response:")
        print("=" * 60)
        print(content)
        print("=" * 60)
        
        # Print usage info
        if hasattr(response, 'usage') and response.usage:
            print(f"\n📊 Usage:")
            print(f"   Prompt tokens: {response.usage.prompt_tokens}")
            print(f"   Completion tokens: {response.usage.completion_tokens}")
            print(f"   Total tokens: {response.usage.total_tokens}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Together AI Vision Test - Kimi K2.5")
    print("=" * 60)
    
    success = test_kimi_vision()
    sys.exit(0 if success else 1)
