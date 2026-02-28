# View Image Tool Plan

## Purpose
Enable the agent to "see" images stored in the workspace for frontend development, UI review, and asset verification.

## Use Case
One-shot image viewing for frontend work:
1. User references a screenshot (`test_site/screenshot.png`)
2. Agent calls `view_image()`
3. Agent sees the image and describes issues
4. Agent fixes the code

No caching. No complexity. Load, view, done.

## Tool Specification

```python
def view_image(filename: str) -> dict:
    """
    Load an image from workspace and return it for display.
    
    Args:
        filename: Path to image (png, jpg, jpeg, webp, gif)
    
    Returns:
        {
            "success": bool,
            "image_data": "base64_encoded_string",
            "mime_type": "image/png"  # or image/jpeg, etc.
        }
    """
```

## Implementation

### Files to Modify
1. `venice/tools/image_ops.py` - Add the function
2. `venice/tools/schema.py` - Add to TOOL_SCHEMAS
3. `venice-web-ui/server.py` - Handle image display response

### Key Points
- No caching - one and done
- No resizing - send as-is
- Simple return: base64 + mime type
- Frontend focused: screenshots, mockups, UI assets

## Example Flow

```
User: "The navbar is broken on mobile"
Agent: view_image("test_site/mobile_nav.png")
Agent: [sees overlapping elements]
Agent: "The hamburger menu overlaps the logo. Fixing CSS..."
```

## Status
**Not implemented** - Documented for future development.
