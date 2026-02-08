#!/usr/bin/env python3
"""
Simple Game Launcher - Works with basic input()
"""

import os
import sys

def show_menu():
    """Display game menu"""
    print("\n" + "=" * 50)
    print("  🎮  ARCADE  🎮")
    print("=" * 50)
    print()
    print("  1. 🐍 SNAKE")
    print("     Use: 8=UP, 2=DOWN, 4=LEFT, 6=RIGHT")
    print()
    print("  2. 🏓 PONG")
    print("     Use: 8=UP, 2=DOWN to move paddle")
    print()
    print("  3. 🚪 QUIT")
    print()
    print("=" * 50)

def main():
    """Main menu loop"""
    while True:
        show_menu()
        choice = input("\n  Enter choice (1-3): ").strip()
        
        if choice == '1':
            print("\n  Starting Snake...")
            os.system(f"python3 {os.path.dirname(__file__)}/snake_input.py")
        
        elif choice == '2':
            print("\n  Starting Pong...")
            os.system(f"python3 {os.path.dirname(__file__)}/pong_input.py")
        
        elif choice == '3':
            print("\n  Goodbye! 👋\n")
            break
        
        else:
            print("\n  Invalid choice!\n")
            input("  Press Enter...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Goodbye!\n")
        sys.exit(0)
