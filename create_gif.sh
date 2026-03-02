#!/bin/bash

# Video to transparent GIF with green screen removal
# Plays forward then backward

INPUT="images/avatars/initial/animated/three/VeniceAI_C24P91t.mp4"
OUTPUT="images/avatars/initial/animated/three/output.gif"
TEMP_DIR="images/avatars/initial/animated/three/temp"

echo "🎬 Processing video: $INPUT"
echo "🎨 Green screen removal with high tolerance"
echo "🔄 Forward then backward playback"
echo ""

# Create temp directory
mkdir -p "$TEMP_DIR"

# Step 1: Extract frames as PNG with green screen removal
echo "📸 Step 1: Extracting frames with chroma key..."
ffmpeg -i "$INPUT" -vf "chromakey=green:0.3:0.2" -vsync 0 "$TEMP_DIR/frame_%04d.png" -y 2>&1 | grep -E "(Duration|Stream|frame=)"

# Step 2: Get frame count
FRAME_COUNT=$(ls -1 "$TEMP_DIR"/frame_*.png | wc -l)
echo "✅ Extracted $FRAME_COUNT frames"

# Step 3: Create forward sequence
echo "📋 Step 2: Creating forward sequence..."
for i in $(seq -f "%04g" 1 $FRAME_COUNT); do
    cp "$TEMP_DIR/frame_$i.png" "$TEMP_DIR/forward_$i.png"
done

# Step 4: Create backward sequence
echo "📋 Step 3: Creating backward sequence..."
for i in $(seq -f "%04g" 1 $FRAME_COUNT); do
    j=$((FRAME_COUNT - i + 1))
    cp "$TEMP_DIR/frame_$j.png" "$TEMP_DIR/backward_$i.png"
done

# Step 5: Combine forward and backward frames
echo "📋 Step 4: Combining forward + backward..."
for i in $(seq -f "%04g" 1 $FRAME_COUNT); do
    cp "$TEMP_DIR/forward_$i.png" "$TEMP_DIR/combined_$(printf "%04d" $i).png"
done

BACKWARD_START=$((FRAME_COUNT + 1))
for i in $(seq -f "%04g" 1 $FRAME_COUNT); do
    cp "$TEMP_DIR/backward_$i.png" "$TEMP_DIR/combined_$(printf "%04d" $((BACKWARD_START + i - 1))).png"
done

TOTAL_FRAMES=$((FRAME_COUNT * 2))
echo "✅ Total frames: $TOTAL_FRAMES (forward + backward)"

# Step 6: Create GIF with transparency
echo "🎨 Step 5: Creating animated GIF with transparency..."
ffmpeg -framerate 30 -i "$TEMP_DIR/combined_%04d.png" -vf "scale=512:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" -loop 0 "$OUTPUT" -y

# Step 7: Optimize GIF (reduce file size)
echo "⚡ Step 6: Optimizing GIF..."
gifsicle -O3 --lossy=30 --colors 256 "$OUTPUT" -o "$OUTPUT"

# Cleanup
echo "🧹 Cleaning up..."
rm -rf "$TEMP_DIR"

echo ""
echo "✨ DONE! Output saved to: $OUTPUT"
echo "📊 Total frames: $TOTAL_FRAMES"
echo "🎬 Playback: Forward → Backward (looping)"