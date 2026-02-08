#!/usr/bin/env python3
"""
Simple Game Launcher - No curses required!
"""

import os
import sys

def show_menu():
    """Display game menu"""
    print("\n" + "=" * 50)
    print("  🎮  WELCOME TO THE ARCADE  🎮")
    print("=" * 50)
    print()
    print("  1. 🐍 SNAKE (Simple version)")
    print("     Classic snake game")
    print("     Controls: Arrow keys")
    print()
    print("  2. 🏓 PONG (Simple version)")
    print("     Beat the computer!")
    print("     Controls: UP/DOWN arrows")
    print()
    print("  3. 🚪 QUIT")
    print()
    print("=" * 50)
    print("  NOTE: Make terminal window LARGE (80x24 minimum)")
    print("=" * 50)

def main():
    """Main menu loop"""
    while True:
        show_menu()
        choice = input("\n  Enter your choice (1-3): ").strip()
        
        if choice == '1':
            print("\n  Starting Snake... 🐍")
            print("  Use arrow keys to move, 'q' to quit\n")
            input("  Press Enter when ready...")
            os.system(f"python3 {os.path.dirname(__file__)}/snake_simple.py")
            input("\n  Press Enter to return to menu...")
        elif choice == '2':
            print("\n  Starting Pong... 🏓")
            print("  Use UP/DOWN arrows to move, 'q' to quit\n")
            input("  Press Enter when ready...")
            os.system(f"python3 {os.path.dirname(__file__)}/pong_simple.py")
            input("\n  Press Enter to return to menu...")
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
