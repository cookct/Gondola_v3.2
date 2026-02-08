#!/usr/bin/env python3
"""
SNAKE - Works with simple input()
Most compatible version
"""

import os
import random
import time

def clear():
    os.system('clear' if os.name != 'nt' else 'cls')

def game():
    """Main game"""
    width = 20
    height = 10
    
    # Snake
    snake = [(10, 5), (9, 5), (8, 5)]
    direction = (1, 0)
    
    # Food
    def place_food():
        while True:
            f = (random.randint(1, width), random.randint(1, height))
            if f not in snake:
                return f
    
    food = place_food()
    score = 0
    game_over = False
    
    print("\n=== SNAKE ===")
    print("Controls:")
    print("  8 = UP")
    print("  2 = DOWN") 
    print("  4 = LEFT")
    print("  6 = RIGHT")
    print("  0 = QUIT")
    print()
    input("Press Enter to start...")
    
    while not game_over:
        clear()
        
        # Draw border
        print("+" + "-" * width + "+")
        
        # Draw game area
        for y in range(1, height + 1):
            row = "|"
            for x in range(1, width + 1):
                if (x, y) == food:
                    row += "*"
                elif (x, y) in snake:
                    row += "@" if (x, y) == snake[0] else "o"
                else:
                    row += " "
            row += "|"
            print(row)
        
        print("+" + "-" * width + "+")
        print(f"Score: {score}")
        print()
        
        # Get input
        move = input("Move (8/2/4/6/0): ").strip()
        
        if move == '0':
            break
        elif move == '8' and direction != (0, 1):
            direction = (0, -1)
        elif move == '2' and direction != (0, -1):
            direction = (0, 1)
        elif move == '4' and direction != (1, 0):
            direction = (-1, 0)
        elif move == '6' and direction != (-1, 0):
            direction = (1, 0)
        
        # Move snake
        head = snake[0]
        new_head = (head[0] + direction[0], head[1] + direction[1])
        
        # Check collision
        if (new_head[0] < 1 or new_head[0] > width or
            new_head[1] < 1 or new_head[1] > height or
            new_head in snake):
            game_over = True
            break
        
        snake.insert(0, new_head)
        
        if new_head == food:
            score += 10
            food = place_food()
        else:
            snake.pop()
    
    clear()
    print(f"\nGAME OVER!")
    print(f"Final Score: {score}")
    
    again = input("\nPlay again? (y/n): ").lower()
    if again == 'y':
        game()

if __name__ == "__main__":
    game()
