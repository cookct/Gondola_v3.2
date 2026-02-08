# Knowledge Semantic Search Integration

Keywords: knowledge, semantic_search, indexing, integration, fix

## Knowledge → Semantic Search Integration Fix

**What was fixed:**
1. Auto-reindex on knowledge save (knowledge_ops.py lines 81-88)
   - After save_knowledge() writes a file, it triggers project_index.build_index()
   - This ensures new knowledge is immediately searchable

2. Knowledge in semantic search results (code_ops.py lines 426-445, 465-480)
   - semantic_search() now calls get_relevant_knowledge() to check for saved knowledge
   - Knowledge entries get 0.95 relevance (higher than file matches)
   - Results include full knowledge_content so cheap models don't re-read files
   - UI shows "[KNOWLEDGE]" marker for knowledge entries

**How to use:**
1. Expensive model (Grok/Claude) analyzes complex task
2. Calls save_knowledge(keywords=["auth", "login"], content="Auth is in auth.py:45...")
3. Knowledge auto-reindexed and available immediately
4. Cheap model (Qwen/MiniMax) calls semantic_search("how does auth work?")
5. Gets knowledge entry with high relevance + full content

**Files modified:**
- venice/tools/knowledge_ops.py
- venice/tools/code_ops.py
