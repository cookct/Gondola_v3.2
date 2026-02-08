#!/usr/bin/env python3
"""
Fixed Game Launcher with keyboard test
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
    print("     Arrow keys to move")
    print()
    print("  2. 🏓 PONG")
    print("     UP/DOWN arrows")
    print()
    print("  3. ⌨️  TEST KEYS")
    print("     Verify keyboard works")
    print()
    print("  4. 🚪 QUIT")
    print()
    print("=" * 50)
    print("  TIP: Make terminal LARGE first!")
    print("=" * 50)

def main():
    """Main menu loop"""
    while True:
        show_menu()
        choice = input("\n  Enter choice (1-4): ").strip()
        
        if choice == '1':
            print("\n  Starting Snake...")
            print("  Arrows: move | q: quit | p: pause")
            input("  Press Enter to start...")
            os.system(f"python3 {os.path.dirname(__file__)}/snake_fixed.py")
            input("\n  Press Enter to return to menu...")
        
        elif choice == '2':
            print("\n  Starting Pong...")
            print("  UP/DOWN: move paddle | q: quit")
            input("  Press Enter to start...")
            os.system(f"python3 {os.path.dirname(__file__)}/pong_fixed.py")
            input("\n  Press Enter to return to menu...")
        
        elif choice == '3':
            print("\n  Testing keyboard...")
            print("  Try arrow keys, then press 'q'")
            input("  Press Enter to start test...")
            os.system(f"python3 {os.path.dirname(__file__)}/test_keys.py")
            input("\n  Press Enter to return to menu...")
        
        elif choice == '4':
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
