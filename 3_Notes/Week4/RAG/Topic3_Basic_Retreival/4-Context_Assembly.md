# Context Assembly: How to Format Retrieved Chunks for the LLM

## Why This Matters

The effectiveness of a RAG system doesn't just depend on retrieving the right information; it significantly relies on how that information is presented to the Large Language Model. The prompt acts as the bridge between the retrieved context and the generation process.

You can have perfect retrieval and still get terrible answers. The LLM needs to understand:

1. What role it should play
2. What context it's been given
3. What constraints apply
4. What the user is actually asking

Even with strong retrieval and a capable LLM, poor prompts yield unfocused or hallucinatory responses. Conversely, a precise prompt can make modest retrieval results usable and trustworthy.

---

## The Anatomy of a RAG Prompt

The Role (System Message): This sets the LLM's persona and rules. The Context (The Ingredients): This is the retrieved text you got from your index. It's the only information the LLM is allowed to use. The Query (The Request): This is the user's original question.

### Basic Structure

```
┌─────────────────────────────────────────┐
│           SYSTEM INSTRUCTIONS           │
│  - Role definition                      │
│  - Behavioral constraints               │
│  - Output format requirements           │
├─────────────────────────────────────────┤
│              CONTEXT                    │
│  - Retrieved chunk 1 + metadata         │
│  - Retrieved chunk 2 + metadata         │
│  - Retrieved chunk 3 + metadata         │
├─────────────────────────────────────────┤
│            USER QUERY                   │
│  - The original question                │
├─────────────────────────────────────────┤
│         ANSWER INSTRUCTIONS             │
│  - How to format the response           │
│  - Citation requirements                │
│  - Fallback behavior                    │
└─────────────────────────────────────────┘
```

---

## Context Injection Methods

### Method 1: Simple Concatenation

The most straightforward approach is simply prepending or appending the retrieved context directly to the original user query. Often, a separator or introductory phrase is used.

```python
def simple_concatenation(chunks: list[str], query: str) -> str:
    context = "\n\n".join(chunks)
    
    prompt = f"""Context:
{context}

Based on the context above, answer the following question:
{query}"""
    
    return prompt
```

**Pros**: Easy to implement **Cons**: If many passages are retrieved, the original query might get "lost" in the noise, or important context might appear too far from the query for the LLM to focus on effectively.

### Method 2: Templated Injection (Recommended)

A more structured and generally preferred method involves using prompt templates. These are pre-defined strings with placeholders for the query and the context.

```python
from string import Template

RAG_TEMPLATE = Template("""You are an expert assistant answering questions based on provided documents.

INSTRUCTIONS:
1. Use ONLY the information in the CONTEXT section below
2. If the answer is not in the context, say "I cannot answer based on the provided documents"
3. Cite your sources using [Source: document_name]

CONTEXT:
$context

USER QUESTION: $query

ANSWER:""")

def templated_injection(chunks: list[dict], query: str) -> str:
    # Format each chunk with its metadata
    formatted_chunks = []
    for i, chunk in enumerate(chunks, 1):
        formatted = f"[Document {i}: {chunk['source']}]\n{chunk['content']}"
        formatted_chunks.append(formatted)
    
    context = "\n\n---\n\n".join(formatted_chunks)
    
    return RAG_TEMPLATE.substitute(context=context, query=query)
```

---

## The Critical Components

### 1. System Instructions: Set the Rules

Key Rule for RAG Prompts: Always frame the prompt with clear instructions to rely only on the provided context.

```python
SYSTEM_PROMPT = """You are a factual assistant that answers questions using ONLY the provided context.

RULES:
1. Base your answer ONLY on the information in the CONTEXT section
2. Do not use prior knowledge or training data
3. If the context doesn't contain the answer, respond: "Based on the provided documents, I cannot answer this question"
4. Cite sources using the format [Source: X] immediately after each fact
5. If information conflicts between sources, acknowledge the discrepancy
"""
```

Start prompts with negative constraints—"Do not invent facts; do not reveal PII; do not provide legal advice." These reduce risk exposure.

### 2. Context Formatting: Make It Parseable

The shift to a JSON-based prompt format yielded significant improvements, particularly in presenting the context as a list of distinct, relevant chunks. This organization enhanced the LLM's reasoning by preventing chunks from being blended.

**Option A: Numbered chunks with metadata**

```python
def format_chunks_numbered(chunks: list[dict]) -> str:
    """Format chunks as numbered entries with metadata."""
    formatted = []
    
    for i, chunk in enumerate(chunks, 1):
        entry = f"""[{i}] Source: {chunk['source']}
Date: {chunk.get('date', 'Unknown')}
Relevance Score: {chunk.get('score', 'N/A'):.2f}

{chunk['content']}"""
        formatted.append(entry)
    
    return "\n\n" + "="*50 + "\n\n".join(formatted)
```

**Option B: XML-style tagging (works well with Claude)**

```python
def format_chunks_xml(chunks: list[dict]) -> str:
    """Format chunks with XML tags for clear boundaries."""
    formatted = []
    
    for i, chunk in enumerate(chunks, 1):
        entry = f"""<document id="{i}" source="{chunk['source']}" date="{chunk.get('date', 'unknown')}">
{chunk['content']}
</document>"""
        formatted.append(entry)
    
    return "\n\n".join(formatted)
```

**Option C: JSON structure**

```python
import json

def format_chunks_json(chunks: list[dict]) -> str:
    """Format chunks as JSON for structured parsing."""
    formatted = []
    
    for i, chunk in enumerate(chunks, 1):
        entry = {
            "id": i,
            "source": chunk['source'],
            "date": chunk.get('date'),
            "score": chunk.get('score'),
            "content": chunk['content']
        }
        formatted.append(entry)
    
    return json.dumps(formatted, indent=2)
```

Attach metadata (date, source type, confidence score) to each chunk and instruct the model how to use it.

### 3. Include Metadata for Better Grounding

This pattern enforces provenance and makes it straightforward to debug which chunks influenced the result.

```python
def format_chunk_with_rich_metadata(chunk: dict) -> str:
    """Include all useful metadata for grounding and debugging."""
    
    return f"""[CONTEXT]
Source: {chunk['source']}
Document Type: {chunk.get('doc_type', 'Unknown')}
Last Updated: {chunk.get('date', 'Unknown')}
Relevance Score: {chunk.get('score', 0):.3f}
Chunk ID: {chunk.get('chunk_id', 'N/A')}

Content:
{chunk['content']}
[/CONTEXT]"""
```

**Why metadata matters:**

- **Source**: Enables citations, builds trust
- **Date**: Helps LLM prioritize recent information
- **Score**: Can instruct LLM to weight higher-confidence chunks
- **Chunk ID**: Essential for debugging and audit trails

---

## The Lost-in-the-Middle Problem

When models must access relevant information in the middle of long contexts, they tend to ignore the provided documents. There is substantial performance degradation when we include 10+ retrieved documents.

When your RAG system dumps 10–20 retrieved chunks into a prompt, the most relevant information might be positioned exactly where the LLM isn't looking.

### The Attention Pattern

```
┌──────────────────────────────────────────────────┐
│                  PROMPT                          │
├──────────────────────────────────────────────────┤
│  Beginning    │     Middle     │      End       │
│  ████████████ │     ░░░░░      │  ████████████  │
│  HIGH         │     LOW        │  HIGH          │
│  ATTENTION    │     ATTENTION  │  ATTENTION     │
└──────────────────────────────────────────────────┘
```

The accuracy is better if the document containing the correct answer is near the top or bottom of the context.

### Solution: Strategic Reordering

Research on Position Engineering shows that by simply re-ordering the documents you retrieve to place the most critical information at the top or bottom of the prompt, you can get a massive performance boost for zero extra cost.

Recognizing the "lost-in-the-middle" phenomenon, we propose reordering retrieved documents based on their retrieval scores. By prioritizing documents with higher scores at the beginning and end of the input sequences, we guide the LLMs' attention towards more relevant information.

```python
def reorder_for_attention(chunks: list[dict]) -> list[dict]:
    """
    Reorder chunks to place most relevant at beginning and end.
    
    Strategy: Interleave by relevance
    - Most relevant → position 0 (beginning)
    - Second most relevant → position -1 (end)
    - Third most relevant → position 1
    - Fourth most relevant → position -2
    ... and so on
    
    Result: Least relevant chunks end up in the middle.
    """
    
    # Sort by score descending
    sorted_chunks = sorted(chunks, key=lambda x: x.get('score', 0), reverse=True)
    
    if len(sorted_chunks) <= 2:
        return sorted_chunks
    
    reordered = [None] * len(sorted_chunks)
    left = 0
    right = len(sorted_chunks) - 1
    
    for i, chunk in enumerate(sorted_chunks):
        if i % 2 == 0:
            reordered[left] = chunk
            left += 1
        else:
            reordered[right] = chunk
            right -= 1
    
    return reordered


# Example usage
chunks = [
    {"content": "Most relevant", "score": 0.95},
    {"content": "Second most", "score": 0.88},
    {"content": "Third", "score": 0.82},
    {"content": "Fourth", "score": 0.75},
    {"content": "Fifth (least)", "score": 0.68},
]

reordered = reorder_for_attention(chunks)
# Result order: [0.95, 0.82, 0.68, 0.75, 0.88]
# Highest at start, second-highest at end, lowest in middle
```

Retrieves chunks from storage, identifies and extracts middle sections, reorders to position middles at start or end, and builds a reordered context for LLM input.

### LangChain's Built-in Solution

```python
from langchain.document_transformers import LongContextReorder

reordering = LongContextReorder()
reordered_docs = reordering.transform_documents(documents)
```

We should put the least similar ones in the middle, not at the bottom.

---

## Handling "No Relevant Results"

RAG is great for grounding an LLM, but certain questions exceed your knowledge base. If your system only sees incomplete data, you might risk partial answers or fictional details. Sometimes the ideal response is "I'm not certain."

```python
def build_prompt_with_fallback(
    chunks: list[dict],
    query: str,
    min_confidence: float = 0.5
) -> str:
    """Build prompt with explicit fallback instructions."""
    
    # Check if we have confident results
    high_confidence_chunks = [c for c in chunks if c.get('score', 0) >= min_confidence]
    
    if not high_confidence_chunks:
        # No confident matches - instruct explicit fallback
        return f"""You are a helpful assistant.

The knowledge base was searched but no relevant documents were found for this question.

USER QUESTION: {query}

INSTRUCTIONS:
1. Acknowledge that the available documents don't contain information about this topic
2. Do NOT make up an answer
3. Suggest what type of information might help answer this question

RESPONSE:"""
    
    # Normal case - confident results exist
    context = format_chunks_numbered(high_confidence_chunks)
    
    return f"""You are a factual assistant. Answer based ONLY on the provided context.

CONTEXT:
{context}

USER QUESTION: {query}

If the context doesn't contain sufficient information to answer, say so clearly.

ANSWER:"""
```

If the context does not contain the answer, state that.

---

## Citation Requirements

For production RAG, you need more than a generic answer; you need groundedness and citations. The prompt should instruct the LLM to integrate citations immediately after the relevant fact.

```python
CITATION_PROMPT = """You are a research assistant that provides well-cited answers.

CONTEXT:
{context}

USER QUESTION: {query}

INSTRUCTIONS:
1. Answer using ONLY information from the context
2. After EVERY factual claim, include a citation in this format: [Source: document_name, Section: X]
3. If multiple sources support a claim, cite all of them
4. If sources conflict, present both views with their citations
5. Never make claims without citations

Example format:
"The company's revenue grew by 15% in Q3 [Source: Financial Report, Section: Executive Summary]. 
However, operating costs also increased [Source: Financial Report, Section: Cost Analysis]."

ANSWER:"""
```

Provenance: Always return chunk citations alongside answers. Maintain logs mapping answers to source chunks.

---

## Token Budget Management

If k=5 chunks push you over the limit, the API call will fail. A common pattern is to retrieve, check the total token length, and truncate the context if necessary before sending it to the LLM.

```python
import tiktoken

def build_prompt_with_budget(
    chunks: list[dict],
    query: str,
    system_prompt: str,
    model: str = "gpt-4o-mini",
    max_context_tokens: int = 8000,
    response_budget: int = 1000
) -> tuple[str, list[dict]]:
    """
    Build prompt while respecting token limits.
    
    Returns: (formatted_prompt, chunks_used)
    """
    
    encoder = tiktoken.encoding_for_model(model)
    
    # Calculate fixed costs
    system_tokens = len(encoder.encode(system_prompt))
    query_tokens = len(encoder.encode(query))
    formatting_overhead = 100  # For separators, instructions, etc.
    
    available_for_context = (
        max_context_tokens 
        - system_tokens 
        - query_tokens 
        - response_budget 
        - formatting_overhead
    )
    
    # Greedily add chunks until budget exhausted
    used_chunks = []
    total_tokens = 0
    
    for chunk in chunks:
        chunk_tokens = len(encoder.encode(chunk['content']))
        
        if total_tokens + chunk_tokens <= available_for_context:
            used_chunks.append(chunk)
            total_tokens += chunk_tokens
        else:
            # Check if we can fit a truncated version
            remaining = available_for_context - total_tokens
            if remaining > 100:  # Worth truncating
                truncated_content = encoder.decode(
                    encoder.encode(chunk['content'])[:remaining]
                )
                truncated_chunk = {**chunk, 'content': truncated_content + "... [truncated]"}
                used_chunks.append(truncated_chunk)
            break
    
    # Build the final prompt
    context = format_chunks_numbered(used_chunks)
    prompt = f"{system_prompt}\n\nCONTEXT:\n{context}\n\nQUESTION: {query}\n\nANSWER:"
    
    return prompt, used_chunks
```

---

## Complete Production Template

```python
from dataclasses import dataclass
from typing import Optional
import tiktoken

@dataclass
class RAGPromptConfig:
    system_role: str = "expert assistant"
    require_citations: bool = True
    allow_uncertainty: bool = True
    max_context_tokens: int = 6000
    response_budget: int = 1000
    temperature: float = 0.1

def build_production_rag_prompt(
    chunks: list[dict],
    query: str,
    config: RAGPromptConfig = RAGPromptConfig()
) -> dict:
    """
    Build a production-ready RAG prompt.
    
    Returns:
        {
            "messages": [...],  # OpenAI-compatible message format
            "chunks_used": [...],  # For logging/debugging
            "token_estimate": int
        }
    """
    
    # 1. Reorder for attention optimization
    reordered_chunks = reorder_for_attention(chunks)
    
    # 2. Build system message
    system_parts = [
        f"You are a {config.system_role} that answers questions based on provided documents.",
        "",
        "RULES:",
        "1. Use ONLY information from the CONTEXT section",
        "2. Do not use prior knowledge or make assumptions",
    ]
    
    if config.require_citations:
        system_parts.append(
            "3. Cite every factual claim using [Source: document_name]"
        )
    
    if config.allow_uncertainty:
        system_parts.append(
            f"{len(system_parts)}. If the context doesn't contain the answer, "
            "say: 'Based on the provided documents, I cannot answer this question.'"
        )
    
    system_prompt = "\n".join(system_parts)
    
    # 3. Format context with metadata
    context_parts = []
    for i, chunk in enumerate(reordered_chunks, 1):
        part = f"""--- Document {i} ---
Source: {chunk.get('source', 'Unknown')}
Date: {chunk.get('date', 'Not specified')}
Relevance: {chunk.get('score', 0):.2f}

{chunk['content']}
"""
        context_parts.append(part)
    
    context_str = "\n".join(context_parts)
    
    # 4. Build user message
    user_message = f"""CONTEXT:
{context_str}

USER QUESTION: {query}

Provide a comprehensive answer based on the context above."""
    
    # 5. Token counting and truncation
    encoder = tiktoken.encoding_for_model("gpt-4o-mini")
    
    system_tokens = len(encoder.encode(system_prompt))
    user_tokens = len(encoder.encode(user_message))
    total_tokens = system_tokens + user_tokens
    
    # Truncate if needed (simplified - production would be smarter)
    if total_tokens > config.max_context_tokens:
        # Remove chunks from middle until we fit
        while total_tokens > config.max_context_tokens and len(reordered_chunks) > 1:
            # Remove middle chunk
            mid = len(reordered_chunks) // 2
            reordered_chunks.pop(mid)
            
            # Rebuild and recount
            context_parts = [format_single_chunk(c, i) for i, c in enumerate(reordered_chunks, 1)]
            context_str = "\n".join(context_parts)
            user_message = f"CONTEXT:\n{context_str}\n\nUSER QUESTION: {query}\n\nProvide a comprehensive answer."
            total_tokens = system_tokens + len(encoder.encode(user_message))
    
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "chunks_used": reordered_chunks,
        "token_estimate": total_tokens + config.response_budget
    }
```

---

## Anti-Patterns to Avoid

### ❌ Dumping chunks without structure

```python
# BAD: No separation, no metadata, chunks blur together
prompt = f"Context: {chunk1} {chunk2} {chunk3}\nQuestion: {query}"
```

### ❌ Placing query before context

```python
# BAD: Query gets "lost" if context is long
prompt = f"Question: {query}\n\nContext: {long_context}"
```

### ❌ No instructions on handling missing information

```python
# BAD: LLM will hallucinate if context doesn't have the answer
prompt = f"Context: {context}\n\nAnswer this: {query}"
```

### ❌ Ignoring chunk order

```python
# BAD: Most relevant might end up in the middle
prompt = build_prompt(chunks)  # Using retrieval order directly
```

---

## Key Takeaways

1. **Structure matters** — Use clear sections: system instructions, context, query, answer format
    
2. **Include metadata** — Source, date, and score help the LLM prioritize and cite
    
3. **Reorder for attention** — Place most relevant chunks at beginning and end, not middle
    
4. **Handle empty results gracefully** — Explicit instructions prevent hallucination
    
5. **Require citations** — Forces grounding and enables verification
    
6. **Budget tokens carefully** — Calculate before calling, truncate intelligently
    
7. **Use separators** — Clear delimiters (`---`, XML tags, numbered lists) prevent chunk blurring
    
8. **Test with edge cases** — Out-of-domain queries, conflicting sources, insufficient context
    

---

## Quick Reference: Prompt Components

|Component|Purpose|Required?|
|---|---|---|
|System role|Sets behavior and constraints|Yes|
|Negative constraints|Prevents hallucination|Yes|
|Context section|Retrieved information|Yes|
|Source metadata|Enables citations|Recommended|
|Score metadata|Helps LLM prioritize|Optional|
|Query|User's question|Yes|
|Citation format|How to reference sources|Recommended|
|Fallback instruction|What to do when uncertain|Yes|
|Output format|Structure of response|Optional|