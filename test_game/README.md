# 🎮 Test Games - Arcade

Simple terminal games that work in any environment!

## 🐍 SNAKE

**File:** `snake_input.py`

**Controls:**
- `8` = Move UP
- `2` = Move DOWN
- `4` = Move LEFT
- `6` = Move RIGHT
- `0` = Quit

**How to play:**
- Eat `*` (food) to grow and score points
- Don't hit walls or yourself!
- Snake head is `@`, body is `o`

## 🏓 PONG

**File:** `pong_input.py`

**Controls:**
- `8` = Move paddle UP
- `2` = Move paddle DOWN
- `0` = Quit

**How to play:**
- You control the left paddle `[#]`
- Computer controls right paddle
- Ball is `O`
- First to 5 points wins!

## 🚀 Quick Start

```bash
cd test_game

# Use the menu
python3 play_input.py

# Or play directly
python3 snake_input.py
python3 pong_input.py
```

## 📁 Files

| File | Description |
|------|-------------|
| `snake_input.py` | Snake game (numpad controls) |
| `pong_input.py` | Pong game (numpad controls) |
| `play_input.py` | Game menu launcher |
| `snake_fixed.py` | Snake with arrow keys (if terminal supports) |
| `pong_fixed.py` | Pong with arrow keys (if terminal supports) |
| `test_keys.py` | Keyboard test utility |

## ⚠️ Notes

- Games use **numpad-style controls** (8/2/4/6) for maximum compatibility
- Arrow key versions may not work in all terminals
- Make terminal window reasonably large for best experience
- Press Enter after each move in the numpad versions

## 🎯 Tips

- In Snake: Plan your path - you grow longer!
- In Pong: The computer is beatable but tricky
- Both games ask if you want to play again

Have fun! 🎉
