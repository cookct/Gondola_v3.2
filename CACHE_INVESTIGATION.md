# Prompt Caching Investigation

## Current Situation

User reported session stats after 11 turns:
- ⏱️ Time: 02:34
- 🔄 Turn: 11 / 40
- 📥 In: **155,498 tokens**
- 📤 Out: 1,197 tokens
- 💰 Cost: **$0.6056**

## Expected vs Actual

### Expected with Caching (per PROMPT_CACHING_OPTIMIZATION.md)
- Turn 1: ~50,000 tokens (cache write)
- Turns 2-11: ~4,000 tokens each × 10 = 40,000 tokens
- **Total expected: ~90,000 tokens**
- **Expected cost: ~$0.35**

### Actual
- **Total: 155,498 tokens**
- **Average per turn: 14,136 tokens**
- **Actual cost: $0.6056**

### Analysis
- **73% more tokens than expected** (155k vs 90k)
- **73% higher cost than expected** ($0.60 vs $0.35)
- Average 14k/turn is between no-cache (50k) and full-cache (4k)
- Suggests **partial caching** or **cache misses**

## Implementation Review

### ✅ Code is Correct

**Static/Dynamic Split** (`venice/prompts/system.py`):
```python
def build_static_system_prompt(model_id, project_context, planning_mode, memory_context):
    """Build STATIC portion (cacheable) - NEVER changes during conversation"""
    parts = [BASE_SYSTEM_PROMPT]
    if planning_mode: parts.append(PLANNING_MODE_PROMPT)
    if memory_context: parts.append(f"\n## MEMORY:\n\n{memory_context}")
    parts.append(STOPPING_CRITERIA)
    if model_id in MODEL_SPECIFIC_GUIDANCE: parts.append(MODEL_SPECIFIC_GUIDANCE[model_id])
    if project_context: parts.append(f"\n## PROJECT OVERVIEW:\n\n{project_context}")
    return '\n'.join(parts)

def build_dynamic_context(turn_count, max_turns, files_already_read, resurrection_context):
    """Build DYNAMIC portion - prepended to user message"""
    parts = []
    if resurrection_context: parts.append(f"## RESURRECTION POINT:\n\n{resurrection_context}")
    if turn_count > 0:
        remaining = max_turns - turn_count
        if remaining <= 5: parts.append(f"## TURN LIMIT WARNING:\n\nYou have {remaining} turns remaining.")
        elif remaining <= 10: parts.append(f"(Turn {turn_count}/{max_turns})")
    if files_already_read: parts.append(f"## FILES ALREADY READ:\n\n{', '.join(files_already_read[:10])}")
    return '\n'.join(parts)
```

**Server Implementation** (`venice-web-ui/server.py` lines 1218-1250):
```python
# Build static system prompt (only on first turn or if not set)
if agent_turns == 0 or not messages or messages[0].get('role') != 'system':
    include_full_context = (agent_turns < 3)
    project_context = context_manager.project_context if (context_manager and include_full_context) else None
    
    static_prompt = build_static_system_prompt(
        model_id=model_id,
        project_context=project_context,
        planning_mode=planning_mode,
        memory_context=memory_context
    )
    
    messages.insert(0, {"role": "system", "content": static_prompt})
    logger.info(f"[{request_id}] Static system prompt set ({len(static_prompt)} chars) - CACHEABLE")

# Build dynamic context and prepend to the LAST user message
dynamic_context = build_dynamic_context(
    turn_count=agent_turns,
    max_turns=MAX_AGENT_TURNS,
    files_already_read=files_read
)

if dynamic_context:
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get('role') == 'user':
            messages[i]['content'] = dynamic_context + "\n" + original_content
            break
```

### 🔍 Potential Issues

#### 1. **Project Context Changes After Turn 3**
```python
include_full_context = (agent_turns < 3)
project_context = context_manager.project_context if (context_manager and include_full_context) else None
```

- Turns 0-2: System prompt includes project context (~10-30k tokens)
- Turn 3+: System prompt **REBUILT WITHOUT** project context
- **This invalidates the cache on turn 3!**

#### 2. **Memory Context May Change**
```python
memory_context = memory.get_context() if memory else None
```

If memory context changes between turns, system prompt is rebuilt with different content.

#### 3. **System Prompt Rebuilt on Every Turn?**
```python
if agent_turns == 0 or not messages or messages[0].get('role') != 'system':
```

This condition checks if system message exists, but the logic might be rebuilding it unnecessarily.

#### 4. **Message History Management**
The server maintains conversation history. If the system message is in the history and gets modified, it could cause issues.

## Test Script Created

Created `test_prompt_caching.py` to:
1. Test Venice AI and Together AI with identical system prompts
2. Send 5 turns with the SAME static system prompt
3. Capture actual token usage from API responses
4. Look for `cache_read_input_tokens` and `cache_creation_input_tokens` fields
5. Calculate cache efficiency and cost savings
6. Compare expected vs actual behavior

### Usage
```bash
# Test both providers
python test_prompt_caching.py --provider both --turns 5

# Test Venice only
python test_prompt_caching.py --provider venice --turns 5

# Test Together only
python test_prompt_caching.py --provider together --turns 5
```

### What to Look For

**Good (caching working):**
```
Turn 1: 50,000 prompt tokens (cache write)
Turn 2: 4,000 prompt tokens (cache hit - 90% reduction)
Turn 3: 4,000 prompt tokens (cache hit)
...
```

**Bad (caching not working):**
```
Turn 1: 50,000 prompt tokens
Turn 2: 50,000 prompt tokens (no reduction)
Turn 3: 50,000 prompt tokens (no reduction)
...
```

**Partial (cache invalidated mid-session):**
```
Turn 1: 50,000 tokens
Turn 2: 4,000 tokens (cache hit)
Turn 3: 50,000 tokens (cache miss - system prompt changed!)
Turn 4: 4,000 tokens (cache hit again)
...
```

## Hypothesis

Based on the 14k average per turn, I suspect:

1. **Turns 0-2**: Full system prompt with project context (~50k tokens)
2. **Turn 3**: System prompt rebuilt WITHOUT project context → **CACHE MISS** → new cache write (~40k tokens)
3. **Turns 4-11**: Cache hits on the new prompt (~4k tokens each)

This would give:
- Turns 0-2: 50k × 3 = 150k
- Turn 3: 40k (cache miss, new baseline)
- Turns 4-11: 4k × 8 = 32k
- **Total: ~222k tokens** (still higher than observed)

Alternative: Cache is working but the static prompt is larger than expected, or the API isn't reporting cache hits correctly.

## Next Steps

1. **Run the test script** to verify cache behavior in isolation
2. **Check server logs** for "CACHEABLE" messages and system prompt sizes
3. **Add cache hit logging** to server.py to track `cache_read_input_tokens`
4. **Consider fixing the project context issue** - either:
   - Include it in ALL turns (defeats purpose of optimization)
   - Never include it (lose context)
   - Include it in dynamic context instead (but it's large)
   - Use a separate "context" message that's also cacheable

## Recommended Fix

**Option A: Keep Project Context Static**
```python
# Always include project context in static prompt (don't change it mid-session)
project_context = context_manager.project_context if context_manager else None

static_prompt = build_static_system_prompt(
    model_id=model_id,
    project_context=project_context,  # Always include
    planning_mode=planning_mode,
    memory_context=memory_context
)
```

**Option B: Never Include Project Context in System Prompt**
```python
# Move project context to a separate user message or omit entirely
project_context = None  # Don't include in system prompt
```

**Option C: Add Cache Hit Tracking**
```python
# In server.py, after capturing usage:
if 'usage' in data_obj:
    usage = data_obj['usage']
    turn_tokens_in = usage.get('prompt_tokens', 0)
    turn_tokens_out = usage.get('completion_tokens', 0)
    cache_read = usage.get('cache_read_input_tokens', 0)
    cache_write = usage.get('cache_creation_input_tokens', 0)
    
    if cache_read > 0:
        logger.info(f"[{request_id}] 🟢 CACHE HIT: {cache_read:,} tokens read from cache")
    if cache_write > 0:
        logger.info(f"[{request_id}] 🔵 CACHE WRITE: {cache_write:,} tokens written to cache")
```

## Conclusion

The implementation is architecturally correct, but there's likely a **cache invalidation issue** caused by:
1. Project context being removed after turn 3
2. Possible memory context changes
3. System prompt being rebuilt unnecessarily

The test script will help isolate whether the issue is in our code or the API provider's caching implementation.
