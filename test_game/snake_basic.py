#!/usr/bin/env python3
"""
SNAKE - Basic version using simple input
Works in any terminal!
"""

import os
import sys
import random
import time

# Clear screen function
def clear():
    os.system('clear' if os.name != 'nt' else 'cls')

def draw_game(snake, food, width, height, score):
    """Draw the game board"""
    clear()
    print("=" * (width + 2))
    
    for y in range(1, height + 1):
        row = "|"
        for x in range(1, width + 1):
            if (x, y) == food:
                row += "*"
            elif (x, y) in snake:
                if (x, y) == snake[0]:
                    row += "@"  # Head
                else:
                    row += "o"  # Body
            else:
                row += " "
        row += "|"
        print(row)
    
    print("=" * (width + 2))
    print(f"Score: {score}  |  Controls: W/A/S/D or Q=quit")

def get_input():
    """Get single character input"""
    try:
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        try:
            ch = sys.stdin.read(1)
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except:
        # Fallback to regular input
        return input("Move (w/a/s/d/q): ").lower()[:1] if input else 'q'

def game():
    """Main game"""
    # Game settings
    width = 30
    height = 15
    
    # Snake starts in middle
    snake = [(width//2, height//2), 
             (width//2 - 1, height//2), 
             (width//2 - 2, height//2)]
    
    # Direction: (dx, dy)
    direction = (1, 0)
    
    # Place food
    def place_food():
        while True:
            f = (random.randint(1, width), random.randint(1, height))
            if f not in snake:
                return f
    
    food = place_food()
    score = 0
    game_over = False
    
    print("\n=== SNAKE ===")
    print("Use W/A/S/D to move")
    print("W=up, S=down, A=left, D=right")
    print("Q=quit, P=pause")
    print()
    input("Press Enter to start...")
    
    last_move = time.time()
    
    while not game_over:
        # Draw current state
        draw_game(snake, food, width, height, score)
        
        # Get input with timeout
        import select
        
        # Check for input (non-blocking)
        ready, _, _ = select.select([sys.stdin], [], [], 0.1)
        
        if ready:
            try:
                # Read character
                import termios, tty
                fd = sys.stdin.fileno()
                old = termios.tcgetattr(fd)
                tty.setcbreak(fd)
                char = sys.stdin.read(1)
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
                
                # Process input
                if char.lower() == 'q':
                    break
                elif char.lower() == 'p':
                    input("\nPAUSED - Press Enter to continue...")
                elif char.lower() == 'w' and direction != (0, 1):
                    direction = (0, -1)
                elif char.lower() == 's' and direction != (0, -1):
                    direction = (0, 1)
                elif char.lower() == 'a' and direction != (1, 0):
                    direction = (-1, 0)
                elif char.lower() == 'd' and direction != (-1, 0):
                    direction = (1, 0)
            except:
                pass
        
        # Move snake based on timing
        current = time.time()
        if current - last_move >= 0.15:
            last_move = current
            
            # Calculate new head
            head = snake[0]
            new_head = (head[0] + direction[0], head[1] + direction[1])
            
            # Check collision
            if (new_head[0] < 1 or new_head[0] > width or
                new_head[1] < 1 or new_head[1] > height or
                new_head in snake):
                game_over = True
                break
            
            # Move
            snake.insert(0, new_head)
            
            # Check food
            if new_head == food:
                score += 10
                food = place_food()
            else:
                snake.pop()
    
    # Game over
    draw_game(snake, food, width, height, score)
    print(f"\nGAME OVER! Final score: {score}")
    
    try:
        again = input("\nPlay again? (y/n): ").lower()
        if again == 'y':
            game()
    except:
        pass

if __name__ == "__main__":
    try:
        game()
    except KeyboardInterrupt:
        print("\n\nThanks for playing!")
    except Exception as e:
        print(f"\nError: {e}")
