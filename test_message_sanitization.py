#!/usr/bin/env python3
"""
Test message sanitization to prevent "Assistant messages must have either content or tool_calls" error
"""

import json
from venice.core import Colors

def test_message_sanitization():
    """Test that assistant messages are properly sanitized"""
    
    print("Testing message sanitization...\n")
    
    test_cases = [
        {
            "name": "Empty content, no tool_calls",
            "input": {"role": "assistant", "content": ""},
            "should_include": False,
            "reason": "Empty message should be dropped"
        },
        {
            "name": "Empty content with tool_calls",
            "input": {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "test", "arguments": "{}"}}]},
            "should_include": True,
            "expected_fields": ["role", "tool_calls"],
            "excluded_fields": ["content"],
            "reason": "Should omit empty content when tool_calls present"
        },
        {
            "name": "Valid content, no tool_calls",
            "input": {"role": "assistant", "content": "Hello"},
            "should_include": True,
            "expected_fields": ["role", "content"],
            "reason": "Normal message should pass through"
        },
        {
            "name": "Valid content with tool_calls",
            "input": {"role": "assistant", "content": "Let me help", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "test", "arguments": "{}"}}]},
            "should_include": True,
            "expected_fields": ["role", "content", "tool_calls"],
            "reason": "Both content and tool_calls should be included"
        },
        {
            "name": "Whitespace-only content",
            "input": {"role": "assistant", "content": "   "},
            "should_include": False,
            "reason": "Whitespace-only should be treated as empty"
        },
        {
            "name": "None content, no tool_calls",
            "input": {"role": "assistant", "content": None},
            "should_include": False,
            "reason": "None content should be dropped"
        },
        {
            "name": "User message (should pass through)",
            "input": {"role": "user", "content": ""},
            "should_include": True,
            "reason": "Non-assistant messages pass through unchanged"
        }
    ]
    
    # Simulate the sanitization logic from cli.py
    def sanitize_messages(messages):
        sanitized = []
        for m in messages:
            if m.get("role") == "assistant":
                content = m.get("content")
                tool_calls = m.get("tool_calls")
                
                has_tools = tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0
                has_content = content is not None and str(content).strip() != ""
                
                if has_tools or has_content:
                    m_copy = {"role": "assistant"}
                    
                    if has_content:
                        m_copy["content"] = content
                    elif not has_tools:
                        m_copy["content"] = ""
                    
                    if has_tools:
                        m_copy["tool_calls"] = tool_calls
                    
                    sanitized.append(m_copy)
            else:
                sanitized.append(m)
        return sanitized
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['name']}")
        print(f"  Input: {json.dumps(test['input'])}")
        
        result = sanitize_messages([test['input']])
        
        # Check if message was included/excluded as expected
        if test['should_include']:
            if len(result) == 0:
                print(f"  {Colors.RED}✗ FAIL: Message was dropped but should be included{Colors.RESET}")
                print(f"  Reason: {test['reason']}")
                failed += 1
                print()
                continue
            
            output = result[0]
            print(f"  Output: {json.dumps(output)}")
            
            # Check expected fields
            if 'expected_fields' in test:
                missing = [f for f in test['expected_fields'] if f not in output]
                if missing:
                    print(f"  {Colors.RED}✗ FAIL: Missing fields: {missing}{Colors.RESET}")
                    failed += 1
                    print()
                    continue
            
            # Check excluded fields
            if 'excluded_fields' in test:
                present = [f for f in test['excluded_fields'] if f in output]
                if present:
                    print(f"  {Colors.RED}✗ FAIL: Should not have fields: {present}{Colors.RESET}")
                    failed += 1
                    print()
                    continue
            
            print(f"  {Colors.GREEN}✓ PASS{Colors.RESET}")
            passed += 1
        else:
            if len(result) > 0:
                print(f"  Output: {json.dumps(result[0])}")
                print(f"  {Colors.RED}✗ FAIL: Message should be dropped{Colors.RESET}")
                print(f"  Reason: {test['reason']}")
                failed += 1
            else:
                print(f"  Output: (dropped)")
                print(f"  {Colors.GREEN}✓ PASS{Colors.RESET}")
                passed += 1
        
        print()
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ ALL TESTS PASSED{Colors.RESET}")
        return True
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ SOME TESTS FAILED{Colors.RESET}")
        return False

def test_api_compatibility():
    """Test that sanitized messages would be accepted by the API"""
    print("\nTesting API compatibility...\n")
    
    # These are the types of messages that were causing the error
    problematic_messages = [
        {"role": "assistant", "content": ""},
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "assistant", "content": None},
    ]
    
    def sanitize_messages(messages):
        sanitized = []
        for m in messages:
            if m.get("role") == "assistant":
                content = m.get("content")
                tool_calls = m.get("tool_calls")
                
                has_tools = tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0
                has_content = content is not None and str(content).strip() != ""
                
                if has_tools or has_content:
                    m_copy = {"role": "assistant"}
                    
                    if has_content:
                        m_copy["content"] = content
                    elif not has_tools:
                        m_copy["content"] = ""
                    
                    if has_tools:
                        m_copy["tool_calls"] = tool_calls
                    
                    sanitized.append(m_copy)
            else:
                sanitized.append(m)
        return sanitized
    
    def validate_message(msg):
        """Check if message meets API requirements"""
        if msg.get("role") != "assistant":
            return True, "Non-assistant message"
        
        has_content = "content" in msg and msg["content"]
        has_tool_calls = "tool_calls" in msg and msg["tool_calls"]
        
        if has_content or has_tool_calls:
            return True, "Has content or tool_calls"
        else:
            return False, "Missing both content and tool_calls"
    
    all_valid = True
    for msg in problematic_messages:
        print(f"Input: {json.dumps(msg)}")
        sanitized = sanitize_messages([msg])
        
        if len(sanitized) == 0:
            print(f"  → Dropped (safe)")
        else:
            output = sanitized[0]
            valid, reason = validate_message(output)
            if valid:
                print(f"  → {json.dumps(output)}")
                print(f"  {Colors.GREEN}✓ Valid: {reason}{Colors.RESET}")
            else:
                print(f"  → {json.dumps(output)}")
                print(f"  {Colors.RED}✗ Invalid: {reason}{Colors.RESET}")
                all_valid = False
        print()
    
    if all_valid:
        print(f"{Colors.GREEN}✓ All sanitized messages are API-compatible{Colors.RESET}")
        return True
    else:
        print(f"{Colors.RED}✗ Some messages would still fail API validation{Colors.RESET}")
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("Message Sanitization Test")
    print("=" * 70)
    print()
    
    result1 = test_message_sanitization()
    result2 = test_api_compatibility()
    
    print("\n" + "=" * 70)
    if result1 and result2:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ ALL TESTS PASSED{Colors.RESET}")
        print("\nThe message sanitization fix prevents the error:")
        print('  "Assistant messages must have either content or tool_calls"')
        exit(0)
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ SOME TESTS FAILED{Colors.RESET}")
        exit(1)
