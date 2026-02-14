# How to Run Prompt Caching Investigation

## Quick Start

### 1. Run the Test Script

```bash
# Make sure API keys are set
export VENICE_API_KEY="your_venice_key"
export TOGETHER_API_KEY="your_together_key"

# Test both providers (recommended)
python test_prompt_caching.py --provider both --turns 5

# Or test individually
python test_prompt_caching.py --provider venice --turns 5
python test_prompt_caching.py --provider together --turns 5
```

### 2. Check the Results

The script will:
- ✅ Send 5 identical requests with the SAME static system prompt
- ✅ Capture actual token usage from API responses
- ✅ Look for cache hit indicators (`cache_read_input_tokens`)
- ✅ Calculate cost savings
- ✅ Print a detailed summary

**Expected output (if caching works):**
```
Turn 1: 50,000 prompt tokens (cache write)
Turn 2: 4,000 prompt tokens (90% reduction - CACHE HIT!)
Turn 3: 4,000 prompt tokens (CACHE HIT!)
...

✅ CACHE IS WORKING!
   Cache saved 184,000 token reads
   Cache efficiency: 85.2%
   Estimated cost: $0.0234
   Expected with cache: $0.0234
```

**Bad output (if caching fails):**
```
Turn 1: 50,000 prompt tokens
Turn 2: 50,000 prompt tokens (no reduction)
Turn 3: 50,000 prompt tokens (no reduction)
...

❌ CACHE NOT DETECTED
   Possible reasons:
   1. Provider doesn't support caching for this model
   2. Cache not enabled in API
   3. System prompt changing between requests
```

### 3. Check Server Logs (Web UI)

After the fix, the web UI server will now log cache hits:

```bash
# Start the web UI
python venice-web-ui/server.py

# Watch the logs for cache indicators
tail -f logs/server.log | grep -E "CACHE|CACHEABLE"
```

**Look for:**
```
[request_id] Static system prompt set (45231 chars) - CACHEABLE
[request_id] 🟢 CACHE HIT: 44,000 tokens read from cache (saved ~$0.1188)
[request_id] 🔵 CACHE WRITE: 45,000 tokens written to cache
```

## What to Look For

### ✅ Good Signs (Caching Working)

1. **Turn 1**: Large prompt token count (~40-60k)
2. **Turn 2+**: Dramatic reduction (~4-8k tokens, 85-90% less)
3. **Logs show**: `🟢 CACHE HIT` messages
4. **Cost**: Significantly lower than expected without caching

### ❌ Bad Signs (Caching Not Working)

1. **All turns**: Similar token counts (~40-60k each)
2. **No reduction**: Turn 2 has same tokens as Turn 1
3. **Logs show**: No cache hit messages
4. **Cost**: Same as if no caching existed

### ⚠️ Partial Caching (Cache Invalidated)

1. **Turn 1-2**: Good reduction (cache working)
2. **Turn 3**: Sudden spike (cache invalidated!)
3. **Turn 4+**: Good reduction again (new cache)
4. **Logs show**: Cache hits, then miss, then hits again

This indicates the system prompt changed mid-session.

## Diagnosing Issues

### Issue 1: Project Context Invalidates Cache

**Symptom:** Cache works for turns 0-2, then breaks on turn 3

**Cause:** Server code removes project context after turn 3:
```python
include_full_context = (agent_turns < 3)  # Only first 3 turns
```

**Fix:** Keep project context consistent:
```python
# Option A: Always include (recommended)
include_full_context = True

# Option B: Never include
include_full_context = False
```

### Issue 2: Memory Context Changes

**Symptom:** Random cache misses throughout session

**Cause:** Memory context updates between turns

**Fix:** Freeze memory context at session start:
```python
# At session start (turn 0)
session_memory_context = memory.get_context() if memory else None

# Use frozen context for all turns
static_prompt = build_static_system_prompt(
    memory_context=session_memory_context  # Don't re-fetch
)
```

### Issue 3: API Doesn't Report Cache Usage

**Symptom:** Token counts drop but no `cache_read_input_tokens` in response

**Cause:** Some providers don't expose cache metrics

**Fix:** Infer from token reduction:
```python
if turn > 1 and turn_tokens_in < previous_turn_tokens_in * 0.5:
    logger.info(f"[{request_id}] 🟢 INFERRED CACHE HIT: {turn_tokens_in:,} tokens (down from {previous_turn_tokens_in:,})")
```

## Expected Results by Provider

### Venice AI (Anthropic Claude)
- ✅ **Automatic caching** for system prompts
- ✅ **Reports cache usage** via `cache_read_input_tokens`
- ✅ **5-minute cache lifetime**
- ✅ **90% cost reduction** on cached tokens

### Together AI (Llama, Mixtral, etc.)
- ✅ **Automatic caching** (enabled Feb 2026)
- ⚠️ **May not report cache usage** explicitly
- ✅ **5-minute cache lifetime**
- ✅ **90% cost reduction** on cached tokens

## Interpreting Your Session Stats

Your reported stats:
- 11 turns
- 155,498 input tokens
- Average: 14,136 tokens/turn

**Analysis:**
- Without caching: ~50k/turn × 11 = 550k tokens
- With perfect caching: ~50k + 10×4k = 90k tokens
- **Your actual: 155k tokens (73% more than expected)**

**Likely scenario:**
1. Turns 0-2: Full prompt with project context (~50k each = 150k)
2. Turn 3: Prompt rebuilt without context → cache miss (~40k)
3. Turns 4-11: Cache hits on new prompt (~4k × 8 = 32k)
4. **Total: ~222k** (still higher than your 155k)

**Alternative:** Cache is working but prompt is smaller than estimated, or some turns hit cache and others don't.

## Recommended Actions

1. **Run test script** to verify cache works in isolation
2. **Check server logs** for cache hit messages (after applying fix)
3. **Fix project context issue** (keep it consistent)
4. **Monitor next session** to see if cost improves

## Files Modified

- ✅ `test_prompt_caching.py` - Standalone cache testing script
- ✅ `venice-web-ui/server.py` - Added cache hit logging
- ✅ `CACHE_INVESTIGATION.md` - Detailed analysis
- ✅ `RUN_CACHE_INVESTIGATION.md` - This file

## Questions to Answer

1. **Does caching work at all?** → Run test script
2. **Is our code invalidating the cache?** → Check logs for "CACHEABLE" and cache hits
3. **Is the project context the problem?** → Compare turns 0-2 vs 3+ in logs
4. **Are we calculating costs correctly?** → Verify token counts match API usage

## Success Criteria

After fixes, you should see:
- ✅ Turn 1: ~50k tokens
- ✅ Turn 2+: ~4-8k tokens (85-90% reduction)
- ✅ 11-turn session: ~90-100k total tokens (not 155k)
- ✅ Cost: ~$0.35 (not $0.60)
- ✅ Logs: Multiple "🟢 CACHE HIT" messages

## Need Help?

If cache still not working after investigation:
1. Share test script output
2. Share relevant server logs (grep for "CACHE")
3. Share session stats from a fresh session
4. Check if model supports caching (some don't)
