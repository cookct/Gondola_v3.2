"""
Image Operations Mixin for Venice AI
Provides AI image generation and editing tools using Venice seedream-v4/seedream-v4-edit models.
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
        Generate an image using Venice seedream-v4 model.

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
            # Get style preset from config
            from venice.prompts.system import get_edit_model
            config = get_edit_model()
            style_preset = config.get("style_preset", "Pixel Art")
            
            # If style_preset is empty string, don't include it in payload
            if not style_preset:
                style_preset = None

            payload = {
                "model": "seedream-v4",
                "prompt": prompt,
                "width": width,
                "height": height,
                "hide_watermark": True,
                "safe_mode": False
            }
            
            if style_preset:
                payload["style_preset"] = style_preset

            UI.step_detail(f"Calling Venice API (seedream-v4)...")

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
                        "dimensions": f"{width}x{height}",
                        "image_base64": image_b64
                    }
                else:
                    return {"success": False, "error": "No image returned from API"}

        except httpx.TimeoutException:
            return {"success": False, "error": "Image generation timed out (120s)"}
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": f"Image generation failed: {str(e)}"}

    def edit_image(self, prompt: str, reference_image: str = "avatar.png", filename: str = None) -> Dict:
        """
        Edit/transform an image using Venice image edit model. Defaults to avatar.png.

        Args:
            prompt: Text description of the desired expression/transformation
            reference_image: Reference image file (defaults to avatar.png)
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

        # Resolve reference image path - ALWAYS use absolute path to gondola images
        # Get gondola root directory (where venice package lives)
        gondola_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        gondola_images = os.path.join(gondola_root, "images", reference_image)

        # DEBUG: Log exact path being used
        import sys
        print(f"[edit_image DEBUG] __file__: {__file__}", file=sys.stderr)
        print(f"[edit_image DEBUG] gondola_root: {gondola_root}", file=sys.stderr)
        print(f"[edit_image DEBUG] Looking for avatar at: {gondola_images}", file=sys.stderr)
        print(f"[edit_image DEBUG] File exists: {os.path.exists(gondola_images)}", file=sys.stderr)
        if os.path.exists(gondola_images):
            stat = os.stat(gondola_images)
            print(f"[edit_image DEBUG] File size: {stat.st_size}, mtime: {stat.st_mtime}", file=sys.stderr)

        ref_path = None
        if os.path.exists(gondola_images):
            # Found in gondola's images directory
            ref_path = gondola_images
        else:
            # Try workspace resolution
            ref_path = self.workspace._resolve(reference_image)
            if not os.path.exists(ref_path):
                # Try in workspace images directory
                ref_path = os.path.join(self.workspace.root_dir, "images", reference_image)
                if not os.path.exists(ref_path):
                    return {"success": False, "error": f"Reference image not found: {reference_image}. Checked: {gondola_images}, workspace"}

        # Read and encode reference image
        try:
            # DEBUG: Log exact file being read
            print(f"[edit_image DEBUG] Reading reference image from: {ref_path}", file=sys.stderr)
            stat_before = os.stat(ref_path)
            print(f"[edit_image DEBUG] File size: {stat_before.st_size}, mtime: {stat_before.st_mtime}", file=sys.stderr)

            with open(ref_path, 'rb') as f:
                image_bytes = f.read()
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            print(f"[edit_image DEBUG] Read {len(image_bytes)} bytes, base64 len: {len(image_b64)}", file=sys.stderr)
        except Exception as e:
            return {"success": False, "error": f"Failed to read reference image: {str(e)}"}

        # Expressions go in gondola root, not workspace
        gondola_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        expressions_dir = os.path.join(gondola_root, "expressions")
        os.makedirs(expressions_dir, exist_ok=True)

        # Generate filename if not provided - include expression description for easy browsing
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Sanitize prompt for filename
            safe_prompt = "".join(c if c.isalnum() or c in " -_" else "" for c in prompt[:30]).strip()
            safe_prompt = safe_prompt.replace(" ", "_")
            filename = f"expr_{safe_prompt}_{timestamp}.png"
        else:
            # Strip any directory path from filename
            filename = os.path.basename(filename)

        # Ensure .png extension
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            filename += '.png'

        output_path = os.path.join(expressions_dir, filename)

        try:
            # Force expression-only prompt - don't let agent describe a new character
            expression_prompt = f"Change the facial expression to: {prompt}. Keep the same person, same style, same character."

            # Get configured edit model
            from venice.prompts.system import get_edit_model
            config = get_edit_model()
            edit_model = config.get("model", "seedream-v4-edit")

            payload = {
                "prompt": expression_prompt,
                "image": image_b64,  # Raw base64, no data URI prefix
                "modelId": edit_model
            }

            UI.step_detail(f"Calling Venice API ({edit_model})...")

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
                    try:
                        error_text = response.text[:500]
                    except:
                        error_text = f"Status {response.status_code}"
                    return {"success": False, "error": f"API error {response.status_code}: {error_text}"}

                # Handle response - Venice returns binary (image/*) or JSON
                content_type = response.headers.get("Content-Type", "")

                if "image" in content_type:
                    # Binary image response
                    edited_bytes = response.content
                else:
                    # JSON response with base64 images
                    result = response.json()
                    if "images" in result and len(result["images"]) > 0:
                        edited_bytes = base64.b64decode(result["images"][0])
                    else:
                        return {"success": False, "error": "No image returned from API"}

                with open(output_path, 'wb') as f:
                    f.write(edited_bytes)

                UI.step_done(f"Saved: {filename} ({len(edited_bytes):,} bytes)")

                # Include base64 so agent can see the result
                image_b64_result = base64.b64encode(edited_bytes).decode('utf-8')

                return {
                    "success": True,
                    "filename": filename,
                    "path": output_path,
                    "url": f"/workspace-expressions/{filename}",
                    "size": len(edited_bytes),
                    "prompt": prompt,
                    "reference_image": reference_image,
                    "image_base64": image_b64_result
                }

        except httpx.TimeoutException:
            return {"success": False, "error": "Image editing timed out (120s)"}
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": f"Image editing failed: {str(e)}"}
