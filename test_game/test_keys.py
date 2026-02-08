#!/usr/bin/env python3
"""
Test keyboard input - run this first to verify keys work!
"""

import sys
import tty
import termios
import select
import time

def test_keys():
    """Test keyboard input"""
    print("=== KEYBOARD TEST ===")
    print()
    print("Press keys to test (q to quit):")
    print("Try: arrow keys, letters, etc.")
    print()
    
    # Save terminal settings
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    
    try:
        # Set raw mode
        tty.setraw(fd)
        
        while True:
            # Check if key pressed
            if select.select([sys.stdin], [], [], 0)[0]:
                char = sys.stdin.read(1)
                
                # Show what was received
                if char == '\x1b':
                    # Escape sequence - check for more
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        next_char = sys.stdin.read(1)
                        if next_char == '[':
                            if select.select([sys.stdin], [], [], 0.1)[0]:
                                arrow = sys.stdin.read(1)
                                if arrow == 'A':
                                    print("UP ARROW")
                                elif arrow == 'B':
                                    print("DOWN ARROW")
                                elif arrow == 'C':
                                    print("RIGHT ARROW")
                                elif arrow == 'D':
                                    print("LEFT ARROW")
                                else:
                                    print(f"ESC sequence: [ {arrow}")
                        else:
                            print(f"ESC + {repr(next_char)}")
                    else:
                        print("ESCAPE key")
                elif char == '\x03':  # Ctrl+C
                    print("Ctrl+C")
                    break
                elif char == 'q':
                    print("q - quitting")
                    break
                elif char == '\r':
                    print("ENTER")
                elif char == ' ':
                    print("SPACE")
                else:
                    # Regular character
                    if char.isprintable():
                        print(f"Key: '{char}' (code: {ord(char)})")
                    else:
                        print(f"Control key: code {ord(char)}")
            
            time.sleep(0.01)
    
    finally:
        # Restore terminal
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    print()
    print("=== TEST COMPLETE ===")

if __name__ == "__main__":
    try:
        test_keys()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
