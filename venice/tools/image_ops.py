"""
Image Operations Mixin for Venice CLI
Provides AI image generation and editing tools using Venice qwen-image/qwen-edit models.
"""

import os
import base64
import httpx
from datetime import datetime
from typing import Dict, Optional

from venice.core import UI


class ImageOpsMixin:
    """Mixin providing image generation and editing operations."""

    def generate_image(self, prompt: str, filename: str = None, width: int = 1024, height: int = 1024) -> Dict:
        """
        Generate an image using Venice qwen-image model.

        Args:
            prompt: Text description of the image to generate
            filename: Optional output filename (auto-generated if not provided)
            width: Image width in pixels (default 1024)
            height: Image height in pixels (default 1024)

        Returns:
            Dict with success status, filename, and path
        """
        self.next_step(f"Generating image: {prompt[:50]}...")

        # Import here to avoid circular import
        from venice.api import get_api_key
        api_key = get_api_key()
        if not api_key:
            return {"success": False, "error": "Venice API key not configured"}

        # Ensure images directory exists in workspace
        images_dir = os.path.join(self.workspace.root_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Sanitize prompt for filename
            safe_prompt = "".join(c if c.isalnum() or c in " -_" else "" for c in prompt[:30]).strip()
            safe_prompt = safe_prompt.replace(" ", "_")
            filename = f"generated_{safe_prompt}_{timestamp}.png"

        # Ensure .png extension
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            filename += '.png'

        output_path = os.path.join(images_dir, filename)

        try:
            payload = {
                "model": "qwen-image",
                "prompt": prompt,
                "width": width,
                "height": height,
                "hide_watermark": True,
                "safe_mode": False
            }

            UI.step_detail(f"Calling Venice API (qwen-image)...")

            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    "https://api.venice.ai/api/v1/image/generate",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )

                if response.status_code != 200:
                    error_text = response.text[:500]
                    return {"success": False, "error": f"API error {response.status_code}: {error_text}"}

                result = response.json()

                # Venice returns images as base64 in "images" array
                if "images" in result and len(result["images"]) > 0:
                    image_b64 = result["images"][0]
                    image_bytes = base64.b64decode(image_b64)

                    with open(output_path, 'wb') as f:
                        f.write(image_bytes)

                    UI.step_done(f"Saved: {filename} ({len(image_bytes):,} bytes)")

                    return {
                        "success": True,
                        "filename": filename,
                        "path": output_path,
                        "url": f"/workspace-images/{filename}",
                        "size": len(image_bytes),
                        "prompt": prompt,
                        "dimensions": f"{width}x{height}"
                    }
                else:
                    return {"success": False, "error": "No image returned from API"}

        except httpx.TimeoutException:
            return {"success": False, "error": "Image generation timed out (120s)"}
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": f"Image generation failed: {str(e)}"}

    def edit_image(self, reference_image: str, prompt: str, filename: str = None) -> Dict:
        """
        Edit/transform an image using Venice qwen-edit model with a reference image.

        Args:
            reference_image: Path to the reference image file
            prompt: Text description of the desired transformation
            filename: Optional output filename (auto-generated if not provided)

        Returns:
            Dict with success status, filename, and path
        """
        self.next_step(f"Editing image with prompt: {prompt[:50]}...")

        # Import here to avoid circular import
        from venice.api import get_api_key
        api_key = get_api_key()
        if not api_key:
            return {"success": False, "error": "Venice API key not configured"}

        # Resolve reference image path
        ref_path = self.workspace._resolve(reference_image)
        if not os.path.exists(ref_path):
            # Try in images directory
            ref_path = os.path.join(self.workspace.root_dir, "images", reference_image)
            if not os.path.exists(ref_path):
                return {"success": False, "error": f"Reference image not found: {reference_image}"}

        # Read and encode reference image
        try:
            with open(ref_path, 'rb') as f:
                image_bytes = f.read()
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        except Exception as e:
            return {"success": False, "error": f"Failed to read reference image: {str(e)}"}

        # Ensure images directory exists
        images_dir = os.path.join(self.workspace.root_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = os.path.splitext(os.path.basename(reference_image))[0]
            filename = f"edited_{base_name}_{timestamp}.png"

        # Ensure .png extension
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            filename += '.png'

        output_path = os.path.join(images_dir, filename)

        try:
            payload = {
                "prompt": prompt,
                "image": image_b64,
                "modelId": "qwen-edit"
            }

            UI.step_detail(f"Calling Venice API (qwen-edit)...")

            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    "https://api.venice.ai/api/v1/image/edit",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )

                if response.status_code != 200:
                    error_text = response.text[:500]
                    return {"success": False, "error": f"API error {response.status_code}: {error_text}"}

                result = response.json()

                # Venice edit returns images in "images" array
                if "images" in result and len(result["images"]) > 0:
                    edited_b64 = result["images"][0]
                    edited_bytes = base64.b64decode(edited_b64)

                    with open(output_path, 'wb') as f:
                        f.write(edited_bytes)

                    UI.step_done(f"Saved: {filename} ({len(edited_bytes):,} bytes)")

                    return {
                        "success": True,
                        "filename": filename,
                        "path": output_path,
                        "url": f"/workspace-images/{filename}",
                        "size": len(edited_bytes),
                        "prompt": prompt,
                        "reference_image": reference_image
                    }
                else:
                    return {"success": False, "error": "No image returned from API"}

        except httpx.TimeoutException:
            return {"success": False, "error": "Image editing timed out (120s)"}
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": f"Image editing failed: {str(e)}"}
