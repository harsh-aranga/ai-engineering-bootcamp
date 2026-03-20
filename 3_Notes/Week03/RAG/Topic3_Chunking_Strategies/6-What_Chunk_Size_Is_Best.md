# Chunk Size Tradeoffs: Retrieval Precision vs. Context Completeness

## The Core Tension

Chunk size is a balancing act between two competing goals:

|Small Chunks|Large Chunks|
|---|---|
|More precise retrieval — query matches exactly what's relevant|More complete context — retrieved content can stand alone|
|Risk: fragments lack context, can't answer questions fully|Risk: retrieval brings irrelevant content along with relevant|

There's no universally correct chunk size. The right size depends on your content, your queries, and your retrieval strategy.

---

## What Happens at Each Extreme

### Too Small (50-100 tokens)

```
Chunk: "Refunds take 5-7 business days."
```

**Retrieval:** Very precise. Query "how long do refunds take" matches this chunk perfectly.

**Problem:** No context. Which refunds? Under what conditions? What payment methods? The LLM has one sentence and must guess or hallucinate the rest.

**Symptoms:**

- LLM responses are vague or incomplete
- Follow-up questions needed for basic clarification
- High retrieval scores but poor answer quality
- Multiple chunks retrieved but they don't connect coherently

### Too Large (2000+ tokens)

```
Chunk: [Contains: company overview, product descriptions, pricing tables, 
refund policy, shipping information, contact details, FAQ section...]
```

**Retrieval:** Query "refund policy" matches because the word "refund" appears somewhere in this wall of text.

**Problem:** 90% of retrieved content is irrelevant. The LLM must wade through noise to find signal. Context window fills with junk.

**Symptoms:**

- Retrieved chunks have low relevance density
- LLM responses include off-topic information
- Context window fills up fast with few useful chunks
- Embedding quality degrades (too many topics averaged into one vector)

---

## The Embedding Problem with Large Chunks

Embeddings represent the "average meaning" of text. Large chunks with multiple topics produce embeddings that are mediocre matches for all topics rather than strong matches for any.

```
Large chunk topics: [refunds, shipping, product specs, company history]
Embedding: somewhere in the middle of all four concepts

Query: "refund policy"
Similarity: 0.6 (weak match — embedding is diluted)

Smaller chunk topic: [refunds only]  
Embedding: focused on refund concept

Query: "refund policy"
Similarity: 0.85 (strong match — embedding is focused)
```

Large chunks hurt retrieval precision at the embedding level, not just at the content level.

---

## The Context Problem with Small Chunks

Small chunks may retrieve precisely, but they lack self-contained meaning.

```
Query: "What are the requirements for a refund?"

Retrieved chunk: "Items must be in original packaging."

Missing context from adjacent chunks:
- "Refunds are available within 30 days of purchase."
- "Electronics require the original receipt."
- "Clearance items are final sale."
```

The LLM sees one fragment. The answer requires four. You either retrieve all four (more API calls, hope they're all in top-k) or the response is incomplete.

---

## Finding the Right Size: Factors to Consider

### 1. Query Granularity

**Specific factual queries:** "What's the API rate limit?" → Smaller chunks (200-400 tokens). Answer is a single fact. Precision matters.

**Exploratory queries:** "Explain how authentication works in this system." → Larger chunks (500-1000 tokens). Answer requires understanding a concept. Context matters.

**Match chunk size to expected query type.** If users ask both, consider different chunk sizes for different content types.

### 2. Content Structure

**Dense, factual content (API docs, specs, legal clauses):** → Smaller chunks. Each paragraph is self-contained. Precision helps.

**Narrative content (tutorials, explanations, stories):** → Larger chunks. Ideas flow across paragraphs. Context helps.

**Mixed content:** → Structure-aware chunking. Chunk by sections, not arbitrary size.

### 3. Retrieval Top-K

**Low top-k (3-5 chunks):** → Each chunk must be highly relevant and self-contained. Lean toward larger chunks with more context.

**High top-k (10-20 chunks):** → You'll retrieve more context anyway. Smaller chunks are fine — quantity compensates.

```
Small chunks + low top-k = fragmented context (bad)
Small chunks + high top-k = precise retrieval, sufficient context (good, but uses more tokens)
Large chunks + low top-k = fewer but more complete chunks (good)
Large chunks + high top-k = lots of irrelevant content retrieved (bad, wastes context)
```

### 4. Context Window Budget

**Tight budget (8k-16k context):** → Every token matters. Smaller, precise chunks minimize waste. But ensure chunks are self-contained.

**Large budget (128k+ context):** → Room for larger chunks with some irrelevant content. Err toward context completeness.

### 5. Embedding Model Max Tokens

Your chunks can't exceed what the embedding model accepts:

|Model|Max Tokens|
|---|---|
|`text-embedding-3-small/large`|8,191|
|`all-MiniLM-L6-v2`|256|
|`all-mpnet-base-v2`|384|

If using a local model with 256 token limit, chunks over ~200 tokens get truncated during embedding. The embedding only represents the first 256 tokens — the rest is invisible to retrieval.

---

## Chunk Size Ranges by Use Case

|Content Type|Recommended Size|Reasoning|
|---|---|---|
|FAQ, Q&A pairs|100-200 tokens|Each Q&A is self-contained. Precision matters.|
|API documentation|200-400 tokens|Functions/endpoints are discrete. One chunk per concept.|
|Legal/policy documents|300-500 tokens|Clauses are dense. Need precision but clauses reference each other.|
|Technical tutorials|400-800 tokens|Concepts span paragraphs. Context helps understanding.|
|Long-form articles|500-1000 tokens|Ideas flow continuously. Larger context preserves coherence.|
|Code files|Varies|Function/class level chunking. Size follows structure, not arbitrary limits.|

---

## The Empirical Approach

Theory only gets you so far. The right chunk size for YOUR data requires testing.

**Test methodology:**

1. **Pick 3 chunk sizes:** Small (200), medium (500), large (1000)
    
2. **Create test queries:** 20-50 queries representative of real usage
    
3. **Measure retrieval quality:**
    
    - Are the correct chunks in top-k?
    - What's the relevance of retrieved chunks? (manual scoring or LLM-as-judge)
4. **Measure answer quality:**
    
    - Does the LLM produce correct answers?
    - Are answers complete or do they miss information?
5. **Compare cost:**
    
    - How many chunks total? (storage)
    - How many tokens retrieved per query? (context usage)

**Common finding:** Medium chunk sizes (400-600 tokens) often win because they balance precision and context. But your data may differ.

---

## Hybrid Strategies

You don't have to pick one size for everything.

### 1. Parent-Child Chunking

Store chunks at two levels:

- **Child chunks (small):** Used for retrieval — precise matching
- **Parent chunks (large):** Retrieved after matching — complete context

```
Query matches child chunk (200 tokens, precise)
    ↓
Retrieve parent chunk (1000 tokens, complete context)
    ↓
Send parent to LLM
```

You get precise retrieval AND complete context.

### 2. Content-Type Specific Chunking

Different chunk sizes for different content:

```python
def get_chunk_size(doc_type: str) -> int:
    sizes = {
        "faq": 150,
        "api_reference": 300,
        "tutorial": 600,
        "legal": 400,
    }
    return sizes.get(doc_type, 500)  # default 500
```

### 3. Sliding Window with Multiple Sizes

Index the same content at multiple chunk sizes. Query matches might come from any level.

```
Document indexed as:
- 200-token chunks (for precise queries)
- 600-token chunks (for exploratory queries)
- Section-level chunks (for broad queries)
```

Trade-off: 3x storage cost, but retrieval can match at the right granularity.

---

## Quick Decision Framework

```
START
  │
  ├─ Is your content highly structured (API docs, FAQs, specs)?
  │     YES → 200-400 tokens
  │     NO ↓
  │
  ├─ Do users ask specific factual questions?
  │     YES → 300-500 tokens
  │     NO ↓
  │
  ├─ Do users ask exploratory/conceptual questions?
  │     YES → 500-800 tokens
  │     NO ↓
  │
  ├─ Is content narrative/flowing (articles, tutorials)?
  │     YES → 600-1000 tokens
  │     NO ↓
  │
  └─ Default: 400-600 tokens, then test and adjust
```

---

## Key Insight

Chunk size isn't about finding a magic number — it's about understanding the tradeoff between retrieval precision and context completeness for YOUR specific use case.

Start with a reasonable default (400-600 tokens), measure what actually happens with your queries, and adjust based on evidence. If retrieval is precise but answers are incomplete, go larger. If retrieval brings irrelevant content, go smaller.

The right answer is empirical, not theoretical.