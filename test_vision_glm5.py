#!/usr/bin/env python3
"""
Test script to verify if GLM-5 supports vision via Together AI API
"""
import os
import base64
import json
import httpx
from pathlib import Path

# Load API key
from venice.api import get_together_api_key

API_KEY = get_together_api_key()
if not API_KEY:
    print("❌ No Together API key found!")
    exit(1)

# Model to test - Together uses slashes
MODEL_ID = "zai-org/GLM-5"

# Image to test
IMAGE_PATH = "images/avatars/initial/halt/1.png"

def test_vision_capability():
    """Test if GLM-5 can process images via Venice API"""
    
    # Load and encode image
    if not os.path.exists(IMAGE_PATH):
        print(f"❌ Image not found: {IMAGE_PATH}")
        return False
    
    with open(IMAGE_PATH, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    
    print(f"📸 Loaded image: {IMAGE_PATH} ({len(image_data)} chars base64)")
    print(f"🤖 Testing model: {MODEL_ID}")
    print(f"🔗 Endpoint: https://api.together.xyz/v1/chat/completions")
    
    # Build multimodal message
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_data}"
                    }
                },
                {
                    "type": "text",
                    "text": "Describe this image briefly. What do you see?"
                }
            ]
        }
    ]
    
    # Build request
    payload = {
        "model": MODEL_ID,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.3,
        "venice_parameters": {
            "include_venice_prompt": True  # Include Venice system prompt
        }
    }
    
    print(f"\n📤 Sending request...")
    print(f"Payload size: {len(json.dumps(payload))} bytes")
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                "https://api.venice.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            print(f"\n📥 Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                print(f"\n✅ SUCCESS! GLM-5 IS vision-capable!")
                print(f"\n📝 Response:\n{'='*50}")
                print(content)
                print(f"{'='*50}")
                return True
            else:
                print(f"\n❌ FAILED! Status: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Error: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"Raw response: {response.text[:500]}")
                return False
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("="*60)
    print("GLM-5 VISION CAPABILITY TEST")
    print("="*60)
    
    success = test_vision_capability()
    
    print("\n" + "="*60)
    if success:
        print("RESULT: ✅ GLM-5 supports vision via Venice API")
    else:
        print("RESULT: ❌ GLM-5 does NOT support vision via Venice API")
        print("\nThe API error confirms the model cannot process images.")
        print("Vision fallback to Kimi K2.5 would be needed.")
    print("="*60)
