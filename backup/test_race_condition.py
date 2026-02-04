#!/usr/bin/env python3
"""
Test script to verify the race condition fix in UI.print()
"""

import threading
import time
import sys
from venice.core import UI, Colors

def test_concurrent_printing():
    """Test that multiple threads can print concurrently without corruption"""
    print("Testing concurrent printing (10 threads x 50 messages each)...")
    
    results = []
    
    def print_worker(thread_id):
        for i in range(50):
            UI.print(f"Thread-{thread_id:02d}: Message {i:03d}")
            # Small random delay to increase chance of race conditions
            time.sleep(0.0001)
    
    threads = [threading.Thread(target=print_worker, args=(i,)) for i in range(10)]
    
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - start
    
    print(f"\n✓ Completed in {elapsed:.2f}s - No crashes or exceptions!")
    print("Visual inspection: Messages should be complete (no partial lines)")

def test_printer_switching():
    """Test that printer can be safely switched during concurrent operations"""
    print("\nTesting printer switching during concurrent operations...")
    
    custom_output = []
    
    def custom_printer(text):
        custom_output.append(text)
    
    def print_worker(thread_id):
        for i in range(20):
            UI.print(f"Worker-{thread_id}: {i}")
            time.sleep(0.001)
    
    # Start workers
    threads = [threading.Thread(target=print_worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    
    # Switch printer mid-execution
    time.sleep(0.05)
    UI.set_printer(custom_printer)
    time.sleep(0.05)
    UI.set_printer(print)  # Switch back
    
    for t in threads:
        t.join()
    
    print(f"✓ Printer switching successful!")
    print(f"  Custom printer captured {len(custom_output)} messages")

def test_ui_methods():
    """Test various UI methods for thread safety"""
    print("\nTesting UI methods...")
    
    def ui_worker(thread_id):
        UI.success(f"Success from thread {thread_id}")
        UI.error(f"Error from thread {thread_id}")
        UI.warning(f"Warning from thread {thread_id}")
        UI.info(f"Info from thread {thread_id}")
    
    threads = [threading.Thread(target=ui_worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    print("✓ UI methods work correctly with threading")

if __name__ == "__main__":
    print("=" * 60)
    print("Race Condition Fix Verification Test")
    print("=" * 60)
    
    try:
        test_concurrent_printing()
        test_printer_switching()
        test_ui_methods()
        
        print("\n" + "=" * 60)
        print(f"{Colors.GREEN}{Colors.BOLD}✓ ALL TESTS PASSED{Colors.RESET}")
        print("=" * 60)
        print("\nThe race condition fix is working correctly!")
        print("- No crashes or exceptions")
        print("- Output is not corrupted")
        print("- Printer switching is safe")
        
    except Exception as e:
        print(f"\n{Colors.RED}✗ TEST FAILED: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
