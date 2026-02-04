# Proposal: Semantic Search Integration for Gondola v2.1

## Overview
Gondola currently relies on keyword-based matching and file structure analysis to understand codebases. While effective for direct lookups, it struggles with "conceptual" searches (e.g., finding where UI logic is registered when the files don't use the word 'registry').

This proposal adds a **Semantic Search** layer using local embeddings to allow the agent to navigate by meaning.

## Core Components

### 1. Local Embedding Engine
- **Library**: `sentence-transformers`
- **Model**: `all-MiniLM-L6-v2` (Fast, small, CPU-optimized)
- **Function**: Converts code summaries, function names, and file descriptions into 384-dimensional vectors.

### 2. Upgraded Project Index (`ProjectIndex`)
- **New Data**: `.gondola_index.json` will now store a `vectors` dictionary mapping file paths to their embedding vectors.
- **Incremental Indexing**: Only re-embeds files when their content hash changes.
- **Hybrid Scoring**: Files are ranked using a combination of:
    - **Keyword match** (High precision for known names)
    - **Vector similarity** (High recall for conceptual matches)

### 3. New Agent Tool: `semantic_search`
- **Input**: Natural language query (e.g., "how is the theme applied to the body?")
- **Output**: List of files ranked by semantic relevance with context snippets.
- **Benefit**: Allows the agent to find code locations even when it doesn't know the exact filenames or variable names.

## Implementation Plan

1. **Phase 1: Foundation**
   - Install `sentence-transformers` and `numpy`.
   - Update `ProjectIndex` to support vector storage and loading.

2. **Phase 2: Indexing**
   - Implement `ProjectIndex._generate_embeddings()`.
   - Update the `build()` process to generate vectors for all indexed files.

3. **Phase 3: Integration**
   - Implement the `semantic_search` logic.
   - Update `get_relevant_files` to use the hybrid scoring system.

4. **Phase 4: Tool Exposure**
   - Add `semantic_search` to the tool mixin and schema.
   - Update the System Prompt to encourage semantic exploration when lost.

## Success Criteria
- Agent can find `js/ui/settings.js` when asked about "adding items to the menu" even if the word "menu" isn't prominent in the file summary.
- Search remains fast (sub-second response for local projects).
- No external API keys required for searching.
