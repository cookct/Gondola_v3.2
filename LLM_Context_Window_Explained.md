# How an LLM Context Window Works

## What It Is
- The context window is the maximum amount of text (tokens) an LLM can process at once
- It includes both the input prompt AND the model's generated output
- Think of it as the model's "working memory" for a single conversation or task

## Token Basics
- Text is broken into tokens (roughly 4 characters per token in English)
- A word like "apple" is typically 1 token; "antidisestablishmentarianism" might be 3-4 tokens
- Different models have different tokenizers, so counts vary slightly

## How It Works
- When you send a prompt, the model converts it to tokens
- The model processes all tokens simultaneously (not sequentially like reading)
- Each token can "attend to" all previous tokens in the window
- The model predicts the next token based on patterns learned during training

## Key Limitations
- Once the context window is full, older content gets pushed out
- Information outside the window is completely inaccessible to the model
- Larger context windows require more compute and memory (quadratically for attention)

## Context Window Sizes (Examples)
- GPT-3: ~4K tokens
- GPT-4 Turbo: 128K tokens
- Claude 3: Up to 200K tokens
- Some models now support 1M+ tokens

## Practical Implications
- Long conversations may lose earlier context
- Large documents need chunking or summarization strategies
- RAG (Retrieval Augmented Generation) helps by fetching relevant info on-demand
- System prompts and few-shot examples consume part of the window

## Attention Mechanism
- The "self-attention" mechanism lets each token look at all other tokens
- This is why context matters—every word can influence every other word
- Attention scales as O(n²), making large windows computationally expensive