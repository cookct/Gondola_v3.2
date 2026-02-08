#!/usr/bin/env python3
"""
Game Launcher - Choose your game!
"""

import os
import sys

def show_menu():
    """Display game menu"""
    print("\n" + "=" * 50)
    print("  🎮  WELCOME TO THE ARCADE  🎮")
    print("=" * 50)
    print()
    print("  1. 🐍 SNAKE")
    print("     Classic snake game - eat food, grow longer,")
    print("     don't hit walls or yourself!")
    print("     Controls: Arrow keys to move")
    print()
    print("  2. 🏓 PONG")
    print("     Classic paddle game - beat the computer!")
    print("     Controls: UP/DOWN arrows to move paddle")
    print()
    print("  3. 🚪 QUIT")
    print()
    print("=" * 50)

def main():
    """Main menu loop"""
    while True:
        show_menu()
        choice = input("  Enter your choice (1-3): ").strip()
        
        if choice == '1':
            print("\n  Starting Snake... 🐍")
            print("  (Make sure your terminal window is large!)\n")
            os.system(f"python3 {os.path.dirname(__file__)}/snake.py")
        elif choice == '2':
            print("\n  Starting Pong... 🏓")
            print("  (Make sure your terminal window is large!)\n")
            os.system(f"python3 {os.path.dirname(__file__)}/pong.py")
        elif choice == '3':
            print("\n  Thanks for playing! 👋\n")
            break
        else:
            print("\n  Invalid choice! Please enter 1, 2, or 3.\n")
            input("  Press Enter to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Goodbye! 👋\n")
        sys.exit(0)
