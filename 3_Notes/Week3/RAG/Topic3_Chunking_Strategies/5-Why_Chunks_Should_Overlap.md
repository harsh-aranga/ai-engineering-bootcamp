# Chunk Overlap: Why It Exists and How Much to Use

## The Problem Overlap Solves

When you split a document into chunks, you create artificial boundaries. Information that flows across those boundaries gets separated.

```
Original text:
"Refunds are processed within 5-7 business days. The refund amount will be 
credited to your original payment method. For credit card purchases, please 
allow an additional 2-3 days for the credit to appear on your statement."

Chunked without overlap (chunk size ~80 chars):
Chunk 1: "Refunds are processed within 5-7 business days. The refund amount will be"
Chunk 2: "credited to your original payment method. For credit card purchases, please"
Chunk 3: "allow an additional 2-3 days for the credit to appear on your statement."
```

User query: "How long until the refund appears on my credit card?"

The answer requires information from Chunk 1 (5-7 days) AND Chunk 3 (additional 2-3 days). But they're separate chunks. If your retrieval returns only Chunk 3, the LLM gets partial context and might give an incomplete answer.

---

## How Overlap Fixes This

Overlap means adjacent chunks share some content. The end of Chunk N repeats at the beginning of Chunk N+1.

```
Chunked WITH overlap (chunk size ~80, overlap ~30):
Chunk 1: "Refunds are processed within 5-7 business days. The refund amount will be"
Chunk 2: "The refund amount will be credited to your original payment method. For credit"
Chunk 3: "credit card purchases, please allow an additional 2-3 days for the credit to"
Chunk 4: "days for the credit to appear on your statement."
```

Now "refund amount" and "credit card" appear in multiple chunks. A query about credit card refunds has better odds of retrieving a chunk that contains enough context to answer correctly.

---

## The Mechanics

```
Text:      [===========================================]
           0         20        40        60        80

No overlap:
Chunk 1:   [====================]
                                 ^-- chunk boundary at 40
Chunk 2:                        [====================]

With overlap of 10:
Chunk 1:   [====================]
                          ^-- Chunk 2 starts at 30 (40 - 10 overlap)
Chunk 2:             [====================]
                              ^-- shared region (30-40)
```

The formula:

- Chunk 1: positions 0 to chunk_size (0-40)
- Chunk 2: positions (chunk_size - overlap) to (2 × chunk_size - overlap) → (30-70)
- Chunk 3: positions (2 × chunk_size - 2 × overlap) to ... → (60-100)

Each chunk starts `(chunk_size - overlap)` characters after the previous one.

---

## What Overlap Actually Buys You

### 1. Context Continuity

Sentences that reference previous sentences ("This process...", "The result...", "It also...") now have their antecedent in the same chunk.

Without overlap:

```
Chunk 1: "The API uses OAuth 2.0 for authentication."
Chunk 2: "It requires a valid access token for each request."
```

"It" in Chunk 2 refers to "The API" in Chunk 1. Without overlap, Chunk 2 is ambiguous.

With overlap:

```
Chunk 2: "...OAuth 2.0 for authentication. It requires a valid access token..."
```

Now the reference is clear within the chunk.

### 2. Retrieval Redundancy

If a concept spans a boundary, it now exists in multiple chunks. Query matching has multiple chances to find relevant content.

### 3. Embedding Quality

Embeddings of chunks with abrupt starts/ends are worse than embeddings of coherent text. Overlap smooths the boundaries.

---

## The Costs of Overlap

Nothing is free:

### 1. More Chunks = More Storage

```
Document: 10,000 characters
Chunk size: 500 characters

No overlap:     10,000 / 500 = 20 chunks
50 char overlap: 10,000 / (500 - 50) = 22.2 → 23 chunks
100 char overlap: 10,000 / (500 - 100) = 25 chunks
200 char overlap: 10,000 / (500 - 200) = 33 chunks
```

More chunks = more vectors in your database = more storage cost.

### 2. More Chunks = More Embedding Calls

Each chunk needs to be embedded. 25 chunks vs 20 chunks = 25% more embedding API calls.

### 3. Redundant Content in Retrieved Results

If you retrieve top-5 chunks and they overlap heavily, you're wasting context window on repeated text.

```
Retrieved chunks (high overlap scenario):
Chunk 3: "...payment processing. Refunds take 5-7 days. The amount..."
Chunk 4: "...Refunds take 5-7 days. The amount will be credited to your..."
Chunk 5: "...The amount will be credited to your original payment method..."
```

You retrieved 3 chunks but got maybe 1.5 chunks worth of unique information.

### 4. Can Overlap Be Too Large?

Yes. If overlap approaches chunk_size, you're barely moving forward:

```
Chunk size: 500, Overlap: 450

Chunk 1: positions 0-500
Chunk 2: positions 50-550   (only 50 new characters!)
Chunk 3: positions 100-600
...
```

A 10,000 character document becomes 200 chunks instead of 20. Ridiculous storage and embedding costs for minimal benefit.

---

## How Much Overlap: Practical Guidelines

|Overlap % of Chunk Size|When to Use|
|---|---|
|0%|Testing, or when chunks are already semantically complete (e.g., one chunk per section)|
|10-15%|Default starting point. Balances context continuity with cost|
|20-25%|Documents with many cross-sentence references, complex prose|
|30%+|Rarely justified. Consider if your chunk size is too small instead|

**Common defaults:**

- Chunk size 500, overlap 50-75 (10-15%)
- Chunk size 1000, overlap 100-150 (10-15%)
- Chunk size 200, overlap 30-50 (15-25%) — smaller chunks need proportionally more overlap

---

## The Real Question: Is Overlap Even Necessary?

Overlap is a **patch for bad boundaries**. If your chunking strategy creates good boundaries (semantic chunking, structure-aware splitting), overlap matters less.

Think about it:

- If each chunk is a complete, coherent section → no context bleeds across boundaries → overlap adds little value
- If chunks are arbitrarily split mid-thought → overlap is essential to maintain any coherence

**Recursive chunking with paragraph/sentence boundaries** → lower overlap needed (10%)

**Fixed-size chunking with no boundary awareness** → higher overlap needed (20%+)

**Semantic chunking** → minimal overlap needed (maybe 5-10% for safety, or even 0%)

---

## Overlap Strategy by Chunking Method

|Chunking Method|Recommended Overlap|Reasoning|
|---|---|---|
|Fixed-size|15-20%|Boundaries are arbitrary, need more overlap to maintain coherence|
|Recursive|10-15%|Boundaries respect sentences/paragraphs, less bleeding|
|Semantic|0-10%|Boundaries are meaning-based, overlap is mostly redundant|
|Structure-aware (headers/sections)|0-5%|Each chunk is a complete unit, overlap rarely helps|

---

## Testing If Your Overlap Is Right

**Too little overlap:**

- Retrieved chunks feel incomplete, start/end abruptly
- LLM responses miss context that exists in adjacent chunks
- Queries about concepts spanning boundaries fail

**Too much overlap:**

- Retrieved top-k chunks contain heavy repetition
- Storage/embedding costs higher than expected
- Diminishing returns — increasing overlap doesn't improve retrieval quality

**Empirical test:**

1. Run the same queries with 0%, 10%, 20% overlap
2. Measure retrieval quality (are correct chunks retrieved?)
3. Measure answer quality (does the LLM produce correct answers?)
4. Pick the lowest overlap that maintains quality

---

## Key Insight

Overlap is a tradeoff lever, not a magic fix. It compensates for imperfect chunk boundaries at the cost of storage and redundancy.

The better your chunking strategy (semantic > recursive > fixed), the less overlap you need. If you find yourself needing 30%+ overlap to get decent retrieval, the real problem is probably your chunking strategy, not your overlap setting.

---

## Optimization: Overlap Deduplication at Retrieval Time

Overlap exists to improve retrieval — but you don't need to send repeated content to the LLM. Store overlap metadata with each chunk, then strip it at retrieval time when consecutive chunks are returned.

**Store with each chunk:**

```python
{
    "content": "...",
    "doc_id": "doc_123",
    "chunk_index": 3,
    "overlap_chars": 50  # or overlap_tokens
}
```

**At retrieval time:**

1. Sort retrieved chunks by `doc_id` and `chunk_index`
2. Identify consecutive chunks from the same document
3. Strip `overlap_chars` from the start of each chunk after the first in a consecutive sequence
4. Send deduplicated content to LLM

**Result:** You get retrieval benefits of overlap without wasting context window on repeated text.

This matters most when:

- Context window is tight (8k-16k models)
- Overlap is aggressive (20%+)
- Retrieval frequently returns consecutive chunks

At 20% overlap across multiple consecutive chunks, you can recover 15-25% of your context budget — significant when every token counts.

---

Let me know when you're ready for the next topic — chunk size tradeoffs.