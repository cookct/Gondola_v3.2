# Avatar Expression System Implementation Plan

## Overview
Dynamic avatar system that changes expressions based on tool usage in the Venice web UI.

## File Structure
```
/images/avatar/
├── initial/          # Default/resting avatar (idle state)
├── read_file/        # Reading expressions
├── search_file_content/  # Searching/magnifying glass expressions
├── edit_file/        # Concentrating/editing expressions
├── write_file/       # Writing/creating expressions
├── run_command/      # Command execution expressions
├── done/            # Task completion expressions
└── thinking/        # Processing/planning expressions
```

## Avatar Tab Layout (Right Sidebar)
- **Main Display**: 190px wide avatar image (preserves aspect ratio)
- **Status Bar**: Small text showing current tool/action

## Behavior States

### 1. Idle State
- Shows random image from `initial/` folder
- Triggered when no tools are active
- Default state when UI loads

### 2. Active Tool States
- **read_file**: Switch to `read_file/` folder, cycle through images
- **search_file_content**: Switch to `search_file_content/` folder, cycle through images
- **edit_file**: Switch to `edit_file/` folder, cycle through images
- **write_file**: Switch to `write_file/` folder, cycle through images
- **run_command**: Switch to `run_command/` folder, cycle through images
- **done**: Switch to `done/` folder (brief pause before returning to idle)

### Image Cycling Behavior
- **Short operations (< 10 seconds)**: Single image, no cycling
- **Long operations (≥ 10 seconds)**: Cycle through all images in tool folder
- **Cycle timing**: Random intervals between 1-3 seconds (2s, 1s, 3s, etc.)
- **Never exceed 3 seconds** between image changes
- **Cycle continues** until tool completes or 10-second threshold passed

### 3. Thinking State
- Shows `thinking/` images during planning phase
- Triggered before tool execution begins

## Technical Implementation

### Frontend Components
1. **Avatar Tab HTML**: Add to right sidebar in `index.html`
2. **CSS Styling**: Avatar container, transitions, status text
3. **JavaScript Logic**: Tool detection, image switching, state management

### Image Management
- Preload images for smooth transitions
- Random selection from appropriate folder
- **Dynamic cycling**: Load all images from tool folder when cycling enabled
- **Random interval generator**: 1-3 second intervals, never exceeding 3s
- **Timer management**: Start/stop cycling based on 10-second threshold
- Fallback to initial state if folder empty
- CSS fade transitions between image changes

### Tool Detection
- Monitor tool execution via WebSocket/API
- Map tool names to image folders
- Update status text with current action
- Track tool start time for duration-based cycling
- Implement timer for 10-second threshold detection

### Fallback Strategy
1. If tool folder empty → use generic "working" expression
2. If generic not available → use initial avatar
3. If all else fails → no avatar change (graceful degradation)

## Implementation Steps
1. Create avatar tab HTML structure
2. Add CSS styling for avatar display
3. Implement JavaScript tool detection
4. Add image switching logic
5. Test with common tools
6. Add smooth transitions

## Notes
- Images must be 190px wide, aspect ratio preserved
- No gallery or grid view needed
- Keep interface simple and focused
- Ensure smooth performance during tool switching