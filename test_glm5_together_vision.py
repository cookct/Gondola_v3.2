#!/usr/bin/env python3
"""
Standalone test: Does GLM-5 support vision on Together AI?
"""
import os
import base64
import json
import httpx

# Together AI API key - read from app_config.json (same as Venice app)
API_KEY = None
try:
    with open('app_config.json', 'r') as f:
        config = json.load(f)
        API_KEY = config.get('together_api_key')
except:
    pass

# Fallback to environment
if not API_KEY:
    API_KEY = os.environ.get('TOGETHER_API_KEY')

if not API_KEY:
    print("❌ No Together API key found! Add to app_config.json or set TOGETHER_API_KEY env var")
    exit(1)

# Model to test on Together
MODEL_ID = "zai-org/GLM-5"

# Image to test
IMAGE_PATH = "images/avatars/initial/halt/1.png"

def test_vision():
    # Load image
    if not os.path.exists(IMAGE_PATH):
        print(f"❌ Image not found: {IMAGE_PATH}")
        return False
    
    with open(IMAGE_PATH, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    
    print(f"📸 Image loaded: {len(image_data)} chars base64")
    print(f"🤖 Model: {MODEL_ID}")
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
                    "text": "Describe this image briefly."
                }
            ]
        }
    ]
    
    payload = {
        "model": MODEL_ID,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.3
    }
    
    print(f"\n📤 Sending {len(json.dumps(payload))} bytes to Together AI...")
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            print(f"\n📥 Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                print(f"\n✅ SUCCESS! GLM-5 IS vision-capable on Together!")
                print(f"\n📝 Response:\n{'='*50}")
                print(content)
                print(f"{'='*50}")
                return True
            else:
                print(f"\n❌ FAILED: {response.status_code}")
                try:
                    error = response.json()
                    print(f"Error: {json.dumps(error, indent=2)}")
                except:
                    print(f"Response: {response.text[:500]}")
                return False
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("GLM-5 VISION TEST - TOGETHER AI")
    print("="*60)
    
    success = test_vision()
    
    print("\n" + "="*60)
    if success:
        print("✅ GLM-5 supports vision on Together AI")
    else:
        print("❌ GLM-5 does NOT support vision on Together AI")
    print("="*60)
