#!/usr/bin/env python3
"""
PONG - Simple version using ANSI escape codes
No curses required!
"""

import sys
import os
import random
import time
import select
import tty
import termios

# ANSI escape codes
CLEAR = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

def get_terminal_size():
    """Get terminal dimensions"""
    import shutil
    return shutil.get_terminal_size()

def getch_nonblocking():
    """Get a single character without blocking"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def getch():
    """Get a single character (blocking)"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def clear_screen():
    """Clear the terminal"""
    print(CLEAR, end="")
    sys.stdout.flush()

def draw_at(x, y, char):
    """Draw a character at position"""
    print(f"\033[{y};{x}H{char}", end="")

def draw_box(width, height):
    """Draw game border"""
    # Top and bottom
    draw_at(1, 1, "+" + "-" * (width - 2) + "+")
    draw_at(1, height, "+" + "-" * (width - 2) + "+")
    # Sides
    for y in range(2, height):
        draw_at(1, y, "|")
        draw_at(width, y, "|")
    # Center line
    for y in range(2, height):
        if y % 2 == 0:
            draw_at(width // 2, y, "|")

def draw_paddle(x, y, height):
    """Draw a paddle"""
    for i in range(height):
        draw_at(x, y + i, "#")

def draw_ball(x, y):
    """Draw the ball"""
    draw_at(x, y, "O")

def draw_scores(p_score, c_score, width):
    """Draw scores"""
    p_text = f"YOU: {p_score}"
    c_text = f"CPU: {c_score}"
    draw_at(3, 1, p_text)
    draw_at(width - len(c_text) - 2, 1, c_text)

def show_game_over(width, height, winner):
    """Show game over"""
    msg = f" {winner} WINS! "
    y = height // 2
    x = (width - len(msg)) // 2
    draw_at(x, y, msg)
    draw_at(x, y + 2, "Press 'r' to restart")
    draw_at(x, y + 3, "Press 'q' to quit")

def show_start_screen(width, height):
    """Show start screen"""
    clear_screen()
    
    title = " PONG "
    y = height // 2 - 3
    x = (width - len(title)) // 2
    
    draw_at(x, y, title)
    draw_at(x - 8, y + 2, "Use UP/DOWN to move paddle")
    draw_at(x - 6, y + 3, "First to 5 points wins!")
    draw_at(x - 6, y + 5, "Press any key to start...")
    
    sys.stdout.flush()
    getch()

def game():
    """Main game loop"""
    # Get terminal size
    size = get_terminal_size()
    width = min(70, size.columns)
    height = min(20, size.lines)
    
    if width < 30 or height < 10:
        print("Terminal too small! Please resize.")
        return
    
    # Game settings
    paddle_height = 3
    paddle_x_offset = 3
    
    # Player paddle (left)
    player_y = height // 2 - paddle_height // 2
    player_x = paddle_x_offset
    
    # Computer paddle (right)
    computer_y = height // 2 - paddle_height // 2
    computer_x = width - paddle_x_offset
    
    # Ball
    ball_x = width // 2
    ball_y = height // 2
    ball_dx = random.choice([-1, 1])
    ball_dy = random.choice([-1, 1])
    
    # Scores
    player_score = 0
    computer_score = 0
    
    game_over = False
    winner = None
    
    print(HIDE_CURSOR, end="")
    
    try:
        show_start_screen(width, height)
        
        last_move = time.time()
        move_delay = 0.08
        
        while True:
            char = getch_nonblocking()
            
            if char:
                if char == 'q':
                    break
                
                # Arrow keys
                if char == '\x1b':
                    next1 = getch_nonblocking()
                    if next1 == '[':
                        next2 = getch_nonblocking()
                        if next2 == 'A':  # Up
                            if player_y > 2:
                                player_y -= 1
                        elif next2 == 'B':  # Down
                            if player_y < height - paddle_height - 1:
                                player_y += 1
                
                if game_over:
                    if char == 'r':
                        # Reset
                        player_score = 0
                        computer_score = 0
                        player_y = height // 2 - paddle_height // 2
                        computer_y = height // 2 - paddle_height // 2
                        ball_x = width // 2
                        ball_y = height // 2
                        game_over = False
                        winner = None
                    elif char == 'q':
                        break
            
            if game_over:
                continue
            
            current_time = time.time()
            if current_time - last_move >= move_delay:
                last_move = current_time
                
                # Computer AI
                if ball_dx > 0:  # Ball coming to computer
                    if ball_y < computer_y + paddle_height // 2 and computer_y > 2:
                        computer_y -= 1
                    elif ball_y > computer_y + paddle_height // 2 and computer_y < height - paddle_height - 1:
                        computer_y += 1
                else:  # Ball going away - center paddle
                    center = height // 2 - paddle_height // 2
                    if computer_y < center - 1:
                        computer_y += 1
                    elif computer_y > center + 1:
                        computer_y -= 1
                
                # Move ball
                ball_x += ball_dx
                ball_y += ball_dy
                
                # Bounce off top/bottom
                if ball_y <= 2 or ball_y >= height - 1:
                    ball_dy = -ball_dy
                
                # Check paddle collisions
                # Player paddle
                if (ball_x == player_x + 1 and 
                    player_y <= ball_y < player_y + paddle_height):
                    ball_dx = -ball_dx
                
                # Computer paddle
                if (ball_x == computer_x - 1 and 
                    computer_y <= ball_y < computer_y + paddle_height):
                    ball_dx = -ball_dx
                
                # Scoring
                if ball_x <= 1:
                    computer_score += 1
                    if computer_score >= 5:
                        game_over = True
                        winner = "COMPUTER"
                    else:
                        ball_x = width // 2
                        ball_y = height // 2
                        ball_dx = random.choice([-1, 1])
                        time.sleep(0.3)
                
                if ball_x >= width:
                    player_score += 1
                    if player_score >= 5:
                        game_over = True
                        winner = "YOU"
                    else:
                        ball_x = width // 2
                        ball_y = height // 2
                        ball_dx = random.choice([-1, 1])
                        time.sleep(0.3)
            
            # Draw
            clear_screen()
            draw_box(width, height)
            draw_paddle(player_x, player_y, paddle_height)
            draw_paddle(computer_x, computer_y, paddle_height)
            draw_ball(ball_x, ball_y)
            draw_scores(player_score, computer_score, width)
            
            if game_over:
                show_game_over(width, height, winner)
            
            sys.stdout.flush()
            time.sleep(0.01)
    
    finally:
        print(SHOW_CURSOR, end="")
        clear_screen()
        print(f"Final Score - You: {player_score}  Computer: {computer_score}")

if __name__ == "__main__":
    try:
        game()
    except KeyboardInterrupt:
        print(SHOW_CURSOR, end="")
        print("\nThanks for playing Pong!")
    except Exception as e:
        print(SHOW_CURSOR, end="")
        print(f"\nError: {e}")
