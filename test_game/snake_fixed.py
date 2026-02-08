#!/usr/bin/env python3
"""
SNAKE - Fixed version with proper key handling
"""

import sys
import os
import random
import time
import select
import tty
import termios
import fcntl
import struct

# ANSI escape codes
CLEAR = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

def get_terminal_size():
    """Get terminal dimensions"""
    try:
        import shutil
        return shutil.get_terminal_size()
    except:
        return os.terminal_size((80, 24))

def set_terminal_raw():
    """Set terminal to raw mode"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setraw(fd)
    return old_settings

def restore_terminal(old_settings):
    """Restore terminal settings"""
    fd = sys.stdin.fileno()
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def kbhit():
    """Check if key pressed (non-blocking)"""
    fd = sys.stdin.fileno()
    return select.select([sys.stdin], [], [], 0)[0] != []

def getch():
    """Get a single character"""
    return sys.stdin.read(1)

def clear_screen():
    """Clear the terminal"""
    print(CLEAR, end="")
    sys.stdout.flush()

def draw_at(x, y, char):
    """Draw a character at position"""
    if x > 0 and y > 0:
        print(f"\033[{y};{x}H{char}", end="")

def draw_box(width, height):
    """Draw game border"""
    # Top
    draw_at(1, 1, "+" + "-" * (width - 2) + "+")
    # Bottom
    draw_at(1, height, "+" + "-" * (width - 2) + "+")
    # Sides
    for y in range(2, height):
        draw_at(1, y, "|")
        draw_at(width, y, "|")

def draw_snake(snake):
    """Draw the snake"""
    for i, (x, y) in enumerate(snake):
        char = "@" if i == 0 else "o"
        draw_at(x, y, char)

def draw_food(food):
    """Draw the food"""
    draw_at(food[0], food[1], "*")

def draw_score(score, high_score, width):
    """Draw score"""
    score_text = f" Score: {score}  High: {high_score} "
    draw_at((width - len(score_text)) // 2, 1, score_text)

def show_game_over(width, height, score):
    """Show game over"""
    msg = f" GAME OVER! Score: {score} "
    y = height // 2
    x = (width - len(msg)) // 2
    draw_at(x, y, msg)
    draw_at(x - 2, y + 2, "Press 'r' to restart, 'q' to quit ")

def show_start_screen(width, height):
    """Show start screen"""
    clear_screen()
    
    title = "=== SNAKE ==="
    y = height // 2 - 3
    x = (width - len(title)) // 2
    
    draw_at(x, y, title)
    draw_at(x - 5, y + 2, "Use arrow keys to move")
    draw_at(x - 8, y + 3, "Eat * to grow, don't hit walls!")
    draw_at(x - 6, y + 5, "Press ANY KEY to start...")
    
    sys.stdout.flush()
    
    # Wait for any key
    while not kbhit():
        time.sleep(0.01)
    getch()  # Consume the key

def game():
    """Main game loop"""
    # Get terminal size
    size = get_terminal_size()
    width = min(60, size.columns)
    height = min(20, size.lines)
    
    if width < 20 or height < 10:
        print("Terminal too small! Please resize.")
        return
    
    # Game area
    game_width = width - 2
    game_height = height - 2
    
    # Initialize snake
    start_x = width // 2
    start_y = height // 2
    snake = [(start_x, start_y), (start_x - 1, start_y), (start_x - 2, start_y)]
    
    # Direction: (x, y)
    direction = (1, 0)
    
    # Place food
    def place_food():
        while True:
            fx = random.randint(2, width - 1)
            fy = random.randint(2, height - 1)
            if (fx, fy) not in snake:
                return (fx, fy)
    
    food = place_food()
    
    score = 0
    high_score = 0
    game_over = False
    
    # Setup terminal
    old_settings = termios.tcgetattr(sys.stdin.fileno())
    
    try:
        # Set raw mode
        set_terminal_raw()
        print(HIDE_CURSOR, end="")
        
        show_start_screen(width, height)
        
        last_move = time.time()
        move_delay = 0.15
        
        while True:
            # Check for input
            if kbhit():
                char = getch()
                
                # Check for escape sequence (arrow keys)
                if char == '\x1b':  # Escape
                    if kbhit():
                        next_char = getch()
                        if next_char == '[':
                            if kbhit():
                                arrow = getch()
                                if arrow == 'A':  # Up
                                    if direction != (0, 1):
                                        direction = (0, -1)
                                elif arrow == 'B':  # Down
                                    if direction != (0, -1):
                                        direction = (0, 1)
                                elif arrow == 'C':  # Right
                                    if direction != (-1, 0):
                                        direction = (1, 0)
                                elif arrow == 'D':  # Left
                                    if direction != (1, 0):
                                        direction = (-1, 0)
                
                elif char.lower() == 'q':
                    break
                
                elif char.lower() == 'p':
                    draw_at(width // 2 - 3, height // 2, "PAUSED")
                    sys.stdout.flush()
                    while True:
                        if kbhit():
                            c = getch()
                            if c.lower() == 'p':
                                break
                            elif c.lower() == 'q':
                                return
                        time.sleep(0.01)
                
                elif game_over and char.lower() == 'r':
                    # Restart
                    snake = [(start_x, start_y), (start_x - 1, start_y), (start_x - 2, start_y)]
                    direction = (1, 0)
                    food = place_food()
                    score = 0
                    game_over = False
            
            if game_over:
                continue
            
            # Move snake based on timing
            current_time = time.time()
            if current_time - last_move >= move_delay:
                last_move = current_time
                
                # Calculate new head
                head_x, head_y = snake[0]
                new_head = (head_x + direction[0], head_y + direction[1])
                
                # Check collisions
                if (new_head[0] <= 1 or new_head[0] >= width or
                    new_head[1] <= 1 or new_head[1] >= height or
                    new_head in snake):
                    game_over = True
                    if score > high_score:
                        high_score = score
                    continue
                
                # Move snake
                snake.insert(0, new_head)
                
                # Check if food eaten
                if new_head == food:
                    score += 10
                    food = place_food()
                    if score % 50 == 0:
                        move_delay = max(0.05, move_delay - 0.01)
                else:
                    snake.pop()
            
            # Draw everything
            clear_screen()
            draw_box(width, height)
            draw_snake(snake)
            draw_food(food)
            draw_score(score, high_score, width)
            
            if game_over:
                show_game_over(width, height, score)
            
            sys.stdout.flush()
            time.sleep(0.01)
    
    finally:
        # Cleanup
        restore_terminal(old_settings)
        print(SHOW_CURSOR, end="")
        clear_screen()
        print(f"Thanks for playing! Final score: {score}")

if __name__ == "__main__":
    try:
        game()
    except KeyboardInterrupt:
        print(SHOW_CURSOR, end="")
        print("\nThanks for playing Snake!")
    except Exception as e:
        print(SHOW_CURSOR, end="")
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
