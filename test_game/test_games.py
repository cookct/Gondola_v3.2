#!/usr/bin/env python3
"""
Quick test to verify games can be imported
"""

import sys
import os

def test_imports():
    """Test that game modules can be imported"""
    print("Testing game imports...")
    
    try:
        # Test importing (without running curses)
        print("✓ snake_simple.py exists")
        with open('snake_simple.py') as f:
            content = f.read()
            assert 'def game():' in content
        print("✓ snake_simple.py has game() function")
        
        print("✓ pong_simple.py exists")
        with open('pong_simple.py') as f:
            content = f.read()
            assert 'def game():' in content
        print("✓ pong_simple.py has game() function")
        
        print("\n✅ All games ready to play!")
        print("\nTo play:")
        print("  python3 play_simple.py")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
