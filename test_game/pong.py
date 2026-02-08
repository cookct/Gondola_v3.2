#!/usr/bin/env python3
"""
PONG - Classic arcade game
Player vs Computer
Use UP/DOWN arrows to move your paddle
First to 5 points wins!
"""

import curses
import random
import time


def main(stdscr):
    # Setup
    curses.curs_set(0)
    stdscr.nodelay(1)
    stdscr.timeout(50)  # Fast refresh for smooth ball
    
    height, width = stdscr.getmaxyx()
    
    # Game dimensions
    game_height = height - 2
    game_width = width - 2
    
    # Paddle settings
    paddle_height = 4
    paddle_width = 1
    
    # Player paddle (left)
    player_y = game_height // 2 - paddle_height // 2
    player_x = 2
    
    # Computer paddle (right)
    computer_y = game_height // 2 - paddle_height // 2
    computer_x = game_width - 2
    
    # Ball
    ball_y = game_height // 2
    ball_x = game_width // 2
    ball_dy = random.choice([-1, 1])
    ball_dx = random.choice([-1, 1])
    
    # Scores
    player_score = 0
    computer_score = 0
    
    # Game state
    paused = False
    game_over = False
    winner = None
    
    # Colors
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Player
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)     # Computer
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLACK)   # Ball
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)   # UI
    curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)    # Border
    
    def draw_border():
        """Draw game border"""
        for x in range(game_width + 1):
            stdscr.addch(0, x, '─', curses.color_pair(5))
            stdscr.addch(game_height, x, '─', curses.color_pair(5))
        for y in range(game_height + 1):
            stdscr.addch(y, 0, '│', curses.color_pair(5))
            stdscr.addch(y, game_width, '│', curses.color_pair(5))
        # Corners
        stdscr.addch(0, 0, '┌', curses.color_pair(5))
        stdscr.addch(0, game_width, '┐', curses.color_pair(5))
        stdscr.addch(game_height, 0, '└', curses.color_pair(5))
        stdscr.addch(game_height, game_width, '┘', curses.color_pair(5))
        # Center line
        for y in range(1, game_height):
            if y % 2 == 0:
                stdscr.addch(y, game_width // 2, '│', curses.color_pair(5))
    
    def draw_paddle(y, x, color):
        """Draw a paddle"""
        for i in range(paddle_height):
            if y + i < game_height:
                stdscr.addch(y + i, x, '█', curses.color_pair(color))
    
    def draw_ball():
        """Draw the ball"""
        stdscr.addch(ball_y, ball_x, '●', curses.color_pair(3) | curses.A_BOLD)
    
    def draw_scores():
        """Draw scores"""
        score_text = f"  YOU: {player_score}  │  CPU: {computer_score}  "
        x = (game_width - len(score_text)) // 2
        stdscr.addstr(0, x, score_text, curses.color_pair(4) | curses.A_BOLD)
    
    def draw_instructions():
        """Draw instructions"""
        instr = " ↑/↓: Move  │  p: Pause  │  q: Quit  │  First to 5 wins! "
        x = (game_width - len(instr)) // 2
        stdscr.addstr(game_height + 1, x, instr, curses.color_pair(4))
    
    def reset_ball(winner_side):
        """Reset ball after scoring"""
        nonlocal ball_y, ball_x, ball_dy, ball_dx
        ball_y = game_height // 2
        ball_x = game_width // 2
        # Ball goes to loser
        ball_dx = 1 if winner_side == "player" else -1
        ball_dy = random.choice([-1, 1])
        time.sleep(0.5)  # Brief pause
    
    def show_game_over():
        """Show game over screen"""
        msg = f" {winner.upper()} WINS! Press 'r' to restart or 'q' to quit "
        y = game_height // 2
        x = (game_width - len(msg)) // 2
        color = 1 if winner == "player" else 2
        stdscr.addstr(y, x, msg, curses.color_pair(color) | curses.A_BOLD | curses.A_REVERSE)
    
    def show_pause():
        """Show pause screen"""
        msg = " PAUSED - Press 'p' to continue "
        y = game_height // 2
        x = (game_width - len(msg)) // 2
        stdscr.addstr(y, x, msg, curses.color_pair(4) | curses.A_BOLD | curses.A_REVERSE)
    
    def show_start_screen():
        """Show start screen"""
        stdscr.clear()
        title = "🏓 PONG 🏓"
        subtitle = "Player vs Computer"
        instructions = [
            "",
            "Use UP and DOWN arrow keys to move your paddle",
            "Don't let the ball get past you!",
            "",
            "Controls:",
            "  ↑ / ↓     Move paddle",
            "  p         Pause",
            "  q         Quit",
            "",
            "First to 5 points wins!",
            "",
            "Press any key to start..."
        ]
        
        y = game_height // 2 - len(instructions) // 2
        
        # Title
        x = (game_width - len(title)) // 2
        stdscr.addstr(y - 2, x, title, curses.color_pair(1) | curses.A_BOLD)
        
        # Subtitle
        x = (game_width - len(subtitle)) // 2
        stdscr.addstr(y - 1, x, subtitle, curses.color_pair(4))
        
        # Instructions
        for i, line in enumerate(instructions):
            x = (game_width - len(line)) // 2
            stdscr.addstr(y + i, x, line, curses.color_pair(4))
        
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
        
        if key == ord('p') and not game_over:
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
                player_score = 0
                computer_score = 0
                player_y = game_height // 2 - paddle_height // 2
                computer_y = game_height // 2 - paddle_height // 2
                reset_ball("player")
                game_over = False
                winner = None
            elif key == ord('q'):
                break
            else:
                draw_border()
                draw_paddle(player_y, player_x, 1)
                draw_paddle(computer_y, computer_x, 2)
                draw_ball()
                draw_scores()
                show_game_over()
                stdscr.refresh()
                continue
        
        # Move player paddle
        if key == curses.KEY_UP and player_y > 1:
            player_y -= 1
        elif key == curses.KEY_DOWN and player_y < game_height - paddle_height - 1:
            player_y += 1
        
        # Simple AI for computer paddle
        # Computer follows the ball with some delay/reaction time
        if ball_dx > 0:  # Ball moving toward computer
            if ball_y < computer_y + paddle_height // 2 and computer_y > 1:
                computer_y -= 1
            elif ball_y > computer_y + paddle_height // 2 and computer_y < game_height - paddle_height - 1:
                computer_y += 1
        else:  # Ball moving away - center paddle
            center = game_height // 2 - paddle_height // 2
            if computer_y < center - 1:
                computer_y += 1
            elif computer_y > center + 1:
                computer_y -= 1
        
        # Move ball
        ball_y += ball_dy
        ball_x += ball_dx
        
        # Ball collision with top/bottom walls
        if ball_y <= 1 or ball_y >= game_height - 1:
            ball_dy = -ball_dy
        
        # Ball collision with paddles
        # Player paddle
        if (ball_x == player_x + 1 and 
            player_y <= ball_y < player_y + paddle_height):
            ball_dx = -ball_dx
            # Add some angle variation based on where it hit
            hit_pos = ball_y - player_y
            if hit_pos < paddle_height // 2:
                ball_dy = -1
            elif hit_pos > paddle_height // 2:
                ball_dy = 1
        
        # Computer paddle
        if (ball_x == computer_x - 1 and 
            computer_y <= ball_y < computer_y + paddle_height):
            ball_dx = -ball_dx
            # Add some angle variation
            hit_pos = ball_y - computer_y
            if hit_pos < paddle_height // 2:
                ball_dy = -1
            elif hit_pos > paddle_height // 2:
                ball_dy = 1
        
        # Scoring
        if ball_x <= 0:
            computer_score += 1
            if computer_score >= 5:
                game_over = True
                winner = "computer"
            else:
                reset_ball("computer")
        elif ball_x >= game_width:
            player_score += 1
            if player_score >= 5:
                game_over = True
                winner = "player"
            else:
                reset_ball("player")
        
        # Draw everything
        draw_border()
        draw_paddle(player_y, player_x, 1)
        draw_paddle(computer_y, computer_x, 2)
        draw_ball()
        draw_scores()
        draw_instructions()
        
        stdscr.refresh()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\nThanks for playing Pong! 🏓")
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure your terminal window is large enough!")
