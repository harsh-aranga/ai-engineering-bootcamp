# Chunking Strategies: What, Why, and What Breaks Without It

## The Core Problem Chunking Solves

LLMs have context window limits. Embedding models have even tighter limits (typically 512-8192 tokens depending on model). You can't embed an entire 50-page document as one vector — the model physically can't process it, and even if it could, a single embedding for 50 pages would be so "averaged out" it would match almost anything vaguely related.

So you split documents into smaller pieces. That's chunking.

But _how_ you split determines whether your RAG system works or fails silently.

---

## What Happens Without Proper Chunking

### Scenario 1: No Chunking (Naive Approach)

You try to embed entire documents. What breaks:

- **Embedding model rejects it** — most models truncate at their token limit, so you lose everything after the first ~512 tokens
- **If it somehow works**, the embedding becomes a vague "average" of all topics in the document. Query "What's the refund policy?" matches a document about company history, products, AND refund policy equally poorly

### Scenario 2: Arbitrary Fixed-Size Chunking (The Default Trap)

You split every 500 characters, no thought given. What breaks:

```
Chunk 1: "...customers may return items within 30 days. Refunds are processed to the orig"
Chunk 2: "inal payment method within 5-7 business days. For damaged items, contact support..."
```

The refund policy is now split across two chunks. Query "How long do refunds take?" might retrieve Chunk 2 (mentions "5-7 business days") but misses the "30 days return window" context from Chunk 1. User gets incomplete answer.

### Scenario 3: Chunks Too Small

You split into 100-token chunks for "precision." What breaks:

```
Chunk: "Refunds are processed within 5-7 business days."
```

Technically correct, but zero context. _Which_ refunds? Under what conditions? The chunk is so small it can't stand alone. If retrieved, the LLM has to guess or hallucinate the missing context.

### Scenario 4: Chunks Too Large

You split into 2000-token chunks to "preserve context." What breaks:

```
Chunk: [Contains: company mission, product overview, pricing table, refund policy, contact info]
```

Query "refund policy" matches this chunk because the word "refund" appears. But the LLM now has to wade through 1800 tokens of irrelevant content to find the 200 tokens that matter. Wastes context window, increases hallucination risk, slows response.

---

## The Three Main Chunking Strategies

### 1. Fixed-Size Chunking

Split every N characters (or tokens). Simplest approach.

**How it works:**

- Set chunk size (e.g., 500 characters)
- Set overlap (e.g., 50 characters) — last 50 chars of Chunk 1 repeat as first 50 of Chunk 2
- Walk through document, cutting at exact positions

**Where it fails:**

- Cuts mid-sentence, mid-word, mid-code-block
- No awareness of content structure
- A sentence might be split: "The deadline is" | "tomorrow at 5pm"

**When it's acceptable:**

- Uniform, prose-heavy documents with no structure
- When you need speed and simplicity over quality
- As a baseline to compare against

### 2. Recursive Chunking

Split hierarchically: try paragraphs first, then sentences, then words. Respects natural boundaries.

**How it works:**

- Define separators in priority order: `["\n\n", "\n", ". ", " "]`
- Try to split on `\n\n` (paragraphs) first
- If resulting chunks are still too large, split those on `\n` (lines)
- Continue down the hierarchy until chunks are within size limit

**Why it's better:**

- Preserves sentence integrity (splits between sentences, not mid-sentence)
- Respects paragraph boundaries where possible
- Still hits target size, but with cleaner breaks

**Where it still fails:**

- Can't handle semantic boundaries (topic shifts within a paragraph)
- Code blocks, tables, lists still get mangled if they're larger than chunk size

### 3. Semantic Chunking

Split based on meaning, not character count. Most sophisticated.

**How it works (simple version):**

- Embed each sentence
- Compare embedding similarity between adjacent sentences
- When similarity drops sharply (topic shift), insert chunk boundary

**How it works (structured version):**

- Use document structure: headers, sections, code blocks
- Each logical section becomes a chunk
- Split large sections recursively

**Why it's better:**

- Chunks contain coherent, complete thoughts
- Retrieval finds topically unified content

**Where it fails:**

- Computationally expensive (embed every sentence)
- Chunk sizes vary wildly — some chunks tiny, some huge
- Requires tuning the "similarity threshold" for detecting topic shifts

---

## Overlap: Why Chunks Share Content

Without overlap:

```
Chunk 1: "Return items within 30 days."
Chunk 2: "Refunds processed in 5-7 days."
```

Query "return and refund timeline" might match one chunk but miss the other, even though they're semantically connected.

With 50-character overlap:

```
Chunk 1: "Return items within 30 days. Refunds processed"
Chunk 2: "30 days. Refunds processed in 5-7 days."
```

Now both chunks contain the transition. Query has better chance of finding the complete answer in at least one chunk.

**Trade-off:** Overlap increases storage (more total text) and embedding cost (more tokens to embed). Typical overlap: 10-20% of chunk size.

---

## The Mental Model

Think of chunking as preparing a book for a search index:

|Strategy|Analogy|
|---|---|
|No chunking|Index the entire book as one entry. Search "photosynthesis" returns the whole biology textbook.|
|Fixed-size|Tear pages into equal strips. Some strips have complete thoughts, some are gibberish mid-sentence.|
|Recursive|Tear at paragraph breaks when possible, sentence breaks when necessary. Readable strips.|
|Semantic|A librarian reads the book and marks topic boundaries. Each strip is one coherent topic.|

---

## What You're Optimizing For

Chunking is a tradeoff between:

1. **Retrieval precision** — Smaller chunks = more specific matches
2. **Context completeness** — Larger chunks = more context per retrieval
3. **Embedding quality** — Coherent chunks = better embeddings
4. **Cost** — More chunks = more embeddings to compute and store

There's no universal "right" answer. The right chunking strategy depends on:

- Your content type (prose vs. code vs. structured)
- Your query patterns (specific lookups vs. broad questions)
- Your retrieval top-k (retrieving 3 chunks vs. 10)

This is why you'll implement multiple strategies and compare — empirically, not theoretically.

---
