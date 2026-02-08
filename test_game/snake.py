#!/usr/bin/env python3
"""
SNAKE - A classic terminal game
Use arrow keys to move, eat food, don't hit walls or yourself!
Press 'q' to quit, 'p' to pause
"""

import curses
import random
import time
from collections import deque


def main(stdscr):
    # Setup
    curses.curs_set(0)  # Hide cursor
    stdscr.nodelay(1)   # Non-blocking input
    stdscr.timeout(100) # Refresh rate (ms)
    
    # Get screen dimensions
    height, width = stdscr.getmaxyx()
    
    # Game area (leave room for border)
    game_height = height - 2
    game_width = width - 2
    
    # Initialize snake in the middle
    snake = deque([
        (game_height // 2, game_width // 2),
        (game_height // 2, game_width // 2 - 1),
        (game_height // 2, game_width // 2 - 2)
    ])
    
    # Initial direction (right)
    direction = (0, 1)
    
    # Place first food
    def place_food():
        while True:
            food = (random.randint(1, game_height - 2), 
                   random.randint(1, game_width - 2))
            if food not in snake:
                return food
    
    food = place_food()
    
    score = 0
    high_score = 0
    paused = False
    game_over = False
    
    # Colors
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Snake
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)     # Food
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Border
    curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Score
    
    def draw_border():
        """Draw game border"""
        for x in range(game_width + 1):
            stdscr.addch(0, x, '═', curses.color_pair(3))
            stdscr.addch(game_height, x, '═', curses.color_pair(3))
        for y in range(game_height + 1):
            stdscr.addch(y, 0, '║', curses.color_pair(3))
            stdscr.addch(y, game_width, '║', curses.color_pair(3))
        # Corners
        stdscr.addch(0, 0, '╔', curses.color_pair(3))
        stdscr.addch(0, game_width, '╗', curses.color_pair(3))
        stdscr.addch(game_height, 0, '╚', curses.color_pair(3))
        stdscr.addch(game_height, game_width, '╝', curses.color_pair(3))
    
    def draw_snake():
        """Draw the snake"""
        for i, (y, x) in enumerate(snake):
            if i == 0:
                # Head
                char = '●' if direction == (0, 1) or direction == (0, -1) else '●'
                stdscr.addch(y, x, char, curses.color_pair(1) | curses.A_BOLD)
            else:
                # Body
                stdscr.addch(y, x, '○', curses.color_pair(1))
    
    def draw_food():
        """Draw the food"""
        y, x = food
        stdscr.addch(y, x, '★', curses.color_pair(2) | curses.A_BOLD)
    
    def show_score():
        """Display score"""
        score_text = f" Score: {score} | High: {high_score} | Press 'p' to pause, 'q' to quit "
        stdscr.addstr(game_height + 1, 2, score_text, curses.color_pair(4))
    
    def show_game_over():
        """Show game over screen"""
        msg = " GAME OVER! Press 'r' to restart or 'q' to quit "
        y = game_height // 2
        x = (game_width - len(msg)) // 2
        stdscr.addstr(y, x, msg, curses.color_pair(2) | curses.A_BOLD | curses.A_REVERSE)
    
    def show_pause():
        """Show pause screen"""
        msg = " PAUSED - Press 'p' to continue "
        y = game_height // 2
        x = (game_width - len(msg)) // 2
        stdscr.addstr(y, x, msg, curses.color_pair(4) | curses.A_BOLD | curses.A_REVERSE)
    
    def show_start_screen():
        """Show start screen"""
        stdscr.clear()
        title = "🐍 SNAKE 🐍"
        instructions = [
            "",
            "Use arrow keys to move",
            "Eat ★ to grow and score points",
            "Don't hit walls or yourself!",
            "",
            "Controls:",
            "  ↑ ↓ ← →  Move",
            "  p          Pause",
            "  q          Quit",
            "",
            "Press any key to start..."
        ]
        
        y = game_height // 2 - len(instructions) // 2
        x = (game_width - len(title)) // 2
        stdscr.addstr(y, x, title, curses.color_pair(1) | curses.A_BOLD)
        
        for i, line in enumerate(instructions):
            x = (game_width - len(line)) // 2
            stdscr.addstr(y + i + 1, x, line, curses.color_pair(4))
        
        stdscr.refresh()
        stdscr.nodelay(0)
        stdscr.getch()
        stdscr.nodelay(1)
    
    # Show start screen
    show_start_screen()
    
    # Main game loop
    while True:
        stdscr.clear()
        
        # Handle input
        key = stdscr.getch()
        
        if key == ord('q'):
            break
        
        if key == ord('p'):
            paused = not paused
            if paused:
                show_pause()
                stdscr.refresh()
                while True:
                    key = stdscr.getch()
                    if key == ord('p'):
                        paused = False
                        break
                    elif key == ord('q'):
                        return
                continue
        
        if game_over:
            if key == ord('r'):
                # Reset game
                snake = deque([
                    (game_height // 2, game_width // 2),
                    (game_height // 2, game_width // 2 - 1),
                    (game_height // 2, game_width // 2 - 2)
                ])
                direction = (0, 1)
                food = place_food()
                score = 0
                game_over = False
            elif key == ord('q'):
                break
            else:
                draw_border()
                show_score()
                show_game_over()
                stdscr.refresh()
                continue
        
        # Change direction based on arrow keys
        if key == curses.KEY_UP and direction != (1, 0):
            direction = (-1, 0)
        elif key == curses.KEY_DOWN and direction != (-1, 0):
            direction = (1, 0)
        elif key == curses.KEY_LEFT and direction != (0, 1):
            direction = (0, -1)
        elif key == curses.KEY_RIGHT and direction != (0, -1):
            direction = (0, 1)
        
        # Calculate new head position
        head_y, head_x = snake[0]
        new_head = (head_y + direction[0], head_x + direction[1])
        
        # Check for collisions
        if (new_head[0] <= 0 or new_head[0] >= game_height or
            new_head[1] <= 0 or new_head[1] >= game_width or
            new_head in snake):
            game_over = True
            if score > high_score:
                high_score = score
            continue
        
        # Move snake
        snake.appendleft(new_head)
        
        # Check if food eaten
        if new_head == food:
            score += 10
            food = place_food()
            # Speed up slightly
            if score % 50 == 0:
                current_timeout = stdscr.timeout()
                if current_timeout > 50:
                    stdscr.timeout(current_timeout - 10)
        else:
            snake.pop()
        
        # Draw everything
        draw_border()
        draw_snake()
        draw_food()
        show_score()
        
        stdscr.refresh()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\nThanks for playing Snake! 🐍")
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure your terminal window is large enough!")
