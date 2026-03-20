# Fixed-Size Chunking: The Baseline Strategy

## What It Is

Fixed-size chunking splits text at exact character (or token) counts, regardless of content. You define a chunk size, the algorithm walks through the document, and cuts every N characters.

It's the "dumb but fast" approach — and understanding why it's dumb helps you appreciate what smarter strategies fix.

---

## How It Works Mechanically

```
Document: "The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs."

Chunk size: 30 characters
Overlap: 0

Result:
Chunk 0: "The quick brown fox jumps over"
Chunk 1: " the lazy dog. Pack my box wit"
Chunk 2: "h five dozen liquor jugs."
```

Notice Chunk 1 starts with a space and ends mid-word ("wit"). The algorithm doesn't care — it just counts characters.

---

## Character Count vs Token Count

**Character-based:** Split every N characters. Simple, but tokens (what the model actually processes) vary in length. "the" is 3 characters, 1 token. "uncharacteristically" is 20 characters, potentially 3-4 tokens.

**Token-based:** Split every N tokens. More accurate for model limits, but requires tokenizing first (slower). Different models use different tokenizers, so token counts vary.

**Practical choice:** For chunking, character-based is usually fine. You're not hitting exact limits — you're targeting approximate sizes. If your embedding model handles 512 tokens, chunking at ~2000 characters gives you safety margin (average ~4 chars/token for English).

---

## The Overlap Parameter

Without overlap, adjacent chunks share nothing:

```
Chunk size: 50, Overlap: 0

Chunk 0: "Customers may return items within 30 days of pur"
Chunk 1: "chase. Refunds are processed within 5-7 business"
Chunk 2: " days to the original payment method."
```

The phrase "30 days of purchase" is split. "5-7 business days" is split. Neither chunk contains a complete policy statement.

With overlap, chunks share trailing/leading content:

```
Chunk size: 50, Overlap: 15

Chunk 0: "Customers may return items within 30 days of pur"
Chunk 1: "30 days of purchase. Refunds are processed withi"
Chunk 2: "processed within 5-7 business days to the origin"
Chunk 3: "days to the original payment method."
```

Now "30 days of purchase" appears complete in Chunk 1. "5-7 business days" spans Chunks 2-3 but at least one chunk has most of the context.

**How overlap works mechanically:**

- Chunk 0 ends at position 50
- Chunk 1 starts at position 35 (50 - 15 overlap)
- Chunk 1 ends at position 85
- Chunk 2 starts at position 70 (85 - 15 overlap)
- And so on

---

## What Fixed-Size Chunking Breaks

### 1. Sentences Split Mid-Thought

```
"The API rate limit is 100 requests per minute. Exceeding this"
"limit will result in HTTP 429 errors."
```

Query "What happens if I exceed rate limit?" might retrieve only the second chunk. The answer ("HTTP 429") is there, but the context ("100 requests per minute") is gone.

### 2. Code Blocks Mangled

```python
# Original code in document:
def calculate_discount(price, rate):
    if rate > 0.5:
        raise ValueError("Discount rate cannot exceed 50%")
    return price * (1 - rate)
```

Fixed chunking might split:

```
Chunk 1: "def calculate_discount(price, rate):\n    if rate > 0.5:\n        raise ValueError"
Chunk 2: "(\"Discount rate cannot exceed 50%\")\n    return price * (1 - rate)"
```

Neither chunk is valid Python. Neither chunk explains the complete function behavior.

### 3. Tables and Structured Data Destroyed

```
| Feature    | Free Tier | Pro Tier |
|------------|-----------|----------|
| API Calls  | 1000/mo   | Unlimited|
| Support    | Email     | 24/7     |
```

Split mid-table, you get:

```
Chunk 1: "| Feature    | Free Tier | Pro Tier |\n|------------|------"
Chunk 2: "-----|----------|\n| API Calls  | 1000/mo   | Unlimited|\n| Sup"
```

Completely unusable. Query "What's included in Pro tier?" retrieves garbage.

### 4. Headers Separated from Content

```
## Refund Policy

Customers may return items within 30 days...
```

If the chunk boundary falls right after "## Refund Policy", you get:

```
Chunk 1: "...previous section content.\n\n## Refund Policy"
Chunk 2: "\n\nCustomers may return items within 30 days..."
```

Chunk 1 has the header but no content. Chunk 2 has content but no header. Query "refund policy" might retrieve Chunk 1 (matches the header) but the actual policy is in Chunk 2.

---

## When Fixed-Size Is Acceptable

Despite its flaws, fixed-size chunking works okay for:

1. **Homogeneous prose** — Long-form text with no structure, no code, no tables. A novel, for example.
    
2. **Speed-critical pipelines** — No parsing overhead, no sentence detection, just slice and go.
    
3. **Baseline comparison** — You implement fixed-size first, measure retrieval quality, then compare against smarter strategies. Without a baseline, you can't prove recursive/semantic chunking is actually better _for your data_.
    
4. **When you'll retrieve many chunks** — If your top-k is 10-20, overlapping chunks and redundancy matter less. You're likely to get both halves of a split sentence.
    

---

## Implementation Sketch

The core logic is trivial:

```python
def fixed_size_chunk(text: str, chunk_size: int, overlap: int = 0) -> list[str]:
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap  # Next chunk starts `overlap` characters back
        
        # Prevent infinite loop if overlap >= chunk_size
        if overlap >= chunk_size:
            start = end
    
    return chunks
```

That's it. No parsing, no boundary detection, no intelligence. Slice the string, move forward, repeat.

---

## The Key Insight

Fixed-size chunking treats text as a blob of characters, not as structured information. It has no concept of:

- Sentences
- Paragraphs
- Code blocks
- Tables
- Headers
- Semantic meaning

This is why it's the baseline, not the solution. You implement it to understand the problem, then move to recursive and semantic strategies that respect content structure.

---

The recursive chunking strategy addresses the "splits mid-sentence" problem by trying paragraph and sentence boundaries first. That's your next topic.