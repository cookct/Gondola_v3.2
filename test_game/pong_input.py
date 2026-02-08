#!/usr/bin/env python3
"""
PONG - Works with simple input()
Most compatible version
"""

import os
import random

def clear():
    os.system('clear' if os.name != 'nt' else 'cls')

def game():
    """Main game"""
    width = 40
    height = 12
    
    # Paddles
    paddle_height = 3
    player_y = height // 2
    computer_y = height // 2
    player_x = 2
    computer_x = width - 1
    
    # Ball
    ball_x = width // 2
    ball_y = height // 2
    ball_dx = random.choice([-1, 1])
    ball_dy = random.choice([-1, 1])
    
    # Scores
    player_score = 0
    computer_score = 0
    
    print("\n=== PONG ===")
    print("Controls:")
    print("  8 = UP (move paddle up)")
    print("  2 = DOWN (move paddle down)")
    print("  0 = QUIT")
    print()
    print("You are the left paddle [#]")
    print("Computer is the right paddle")
    print("First to 5 wins!")
    print()
    input("Press Enter to start...")
    
    while player_score < 5 and computer_score < 5:
        clear()
        
        # Draw top border with scores
        print(f"YOU: {player_score}  |  CPU: {computer_score}")
        print("+" + "-" * width + "+")
        
        # Draw game
        for y in range(1, height + 1):
            row = "|"
            for x in range(1, width + 1):
                # Ball
                if x == ball_x and y == ball_y:
                    row += "O"
                # Player paddle
                elif x == player_x and player_y <= y < player_y + paddle_height:
                    row += "#"
                # Computer paddle
                elif x == computer_x and computer_y <= y < computer_y + paddle_height:
                    row += "#"
                else:
                    row += " "
            row += "|"
            print(row)
        
        print("+" + "-" * width + "+")
        print()
        
        # Get input
        move = input("Move (8=up, 2=down, 0=quit): ").strip()
        
        if move == '0':
            break
        elif move == '8' and player_y > 1:
            player_y -= 1
        elif move == '2' and player_y < height - paddle_height + 1:
            player_y += 1
        
        # Computer AI
        if ball_dx > 0:  # Ball coming to computer
            if ball_y < computer_y + 1 and computer_y > 1:
                computer_y -= 1
            elif ball_y > computer_y + 1 and computer_y < height - paddle_height + 1:
                computer_y += 1
        
        # Move ball
        ball_x += ball_dx
        ball_y += ball_dy
        
        # Bounce off top/bottom
        if ball_y <= 1 or ball_y >= height:
            ball_dy = -ball_dy
        
        # Paddle collisions
        if (ball_x == player_x + 1 and 
            player_y <= ball_y < player_y + paddle_height):
            ball_dx = -ball_dx
        
        if (ball_x == computer_x - 1 and 
            computer_y <= ball_y < computer_y + paddle_height):
            ball_dx = -ball_dx
        
        # Scoring
        if ball_x <= 1:
            computer_score += 1
            ball_x = width // 2
            ball_y = height // 2
            ball_dx = random.choice([-1, 1])
        
        if ball_x >= width:
            player_score += 1
            ball_x = width // 2
            ball_y = height // 2
            ball_dx = random.choice([-1, 1])
    
    # Game over
    clear()
    winner = "YOU" if player_score >= 5 else "COMPUTER"
    print(f"\n=== {winner} WINS! ===")
    print(f"Final Score - You: {player_score}  Computer: {computer_score}")
    
    again = input("\nPlay again? (y/n): ").lower()
    if again == 'y':
        game()

if __name__ == "__main__":
    game()
