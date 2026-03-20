# Semantic Chunking: Splitting by Meaning, Not Characters

## The Core Idea

Semantic chunking splits text where the _meaning_ changes, not where arbitrary character counts or formatting markers happen to fall. It uses embeddings to detect topic shifts — when adjacent sentences stop being similar, that's a chunk boundary.

The premise: meaning boundaries matter more than formatting boundaries.

---

## Why Recursive Chunking Isn't Enough

Recursive chunking respects structural boundaries (paragraphs, sentences). But structure doesn't always align with meaning:

**Problem 1: One paragraph, multiple topics**

```
"Our Q3 revenue increased 15% year-over-year, driven primarily by enterprise sales. 
In related news, we've appointed Sarah Chen as our new CFO, effective next month. 
She previously served as VP of Finance at TechGlobal for eight years."
```

This is one paragraph. Recursive chunking keeps it as one chunk. But it contains two distinct topics: revenue performance and executive appointment. Query "Q3 revenue" retrieves the whole chunk, including irrelevant CFO information.

**Problem 2: Related content across paragraphs**

```
"Refunds are processed within 5-7 business days.

The refund amount will be credited to your original payment method. For credit card 
purchases, please allow an additional 2-3 days for the credit to appear."
```

Two paragraphs, but one topic (refunds). Recursive chunking might split them if each paragraph is close to chunk_size. Now the refund policy is fragmented.

Semantic chunking addresses both: it keeps related sentences together regardless of paragraph boundaries, and splits unrelated sentences even within a paragraph.

---

## How Semantic Chunking Works

### The Basic Algorithm

1. Split document into sentences
2. Generate an embedding for each sentence
3. Compare embeddings of adjacent sentences (cosine similarity)
4. When similarity drops below a threshold → insert chunk boundary
5. Group consecutive sentences between boundaries into chunks

### Step-by-Step Example

```
Document:
"Machine learning models require training data. The quality of data directly impacts 
model performance. Data preprocessing is therefore critical. In other news, our 
company picnic is scheduled for next Friday. Please RSVP by Wednesday."

Sentences:
S1: "Machine learning models require training data."
S2: "The quality of data directly impacts model performance."
S3: "Data preprocessing is therefore critical."
S4: "In other news, our company picnic is scheduled for next Friday."
S5: "Please RSVP by Wednesday."
```

**Step 1: Embed each sentence**

```
E1 = embed(S1)  # Vector about ML/training data
E2 = embed(S2)  # Vector about data quality/ML
E3 = embed(S3)  # Vector about data preprocessing
E4 = embed(S4)  # Vector about company picnic
E5 = embed(S5)  # Vector about RSVP
```

**Step 2: Compute similarity between adjacent pairs**

```
sim(E1, E2) = 0.87  # High — both about data in ML context
sim(E2, E3) = 0.82  # High — both about data importance
sim(E3, E4) = 0.23  # LOW — topic shift from ML to picnic
sim(E4, E5) = 0.71  # Moderate — both about picnic event
```

**Step 3: Apply threshold (e.g., 0.5)**

```
E1→E2: 0.87 > 0.5 → No boundary
E2→E3: 0.82 > 0.5 → No boundary
E3→E4: 0.23 < 0.5 → BOUNDARY HERE
E4→E5: 0.71 > 0.5 → No boundary
```

**Step 4: Form chunks**

```
Chunk 1: "Machine learning models require training data. The quality of data 
directly impacts model performance. Data preprocessing is therefore critical."

Chunk 2: "In other news, our company picnic is scheduled for next Friday. 
Please RSVP by Wednesday."
```

The ML content stays together. The picnic content stays together. The topic shift creates the boundary — not paragraph markers or character counts.

---

## The Similarity Threshold Problem

The threshold is the critical parameter, and there's no universal correct value.

**Threshold too high (e.g., 0.9):**

- Almost every sentence pair falls below threshold
- Result: every sentence becomes its own chunk
- Chunks are tiny, lack context

**Threshold too low (e.g., 0.3):**

- Almost nothing falls below threshold
- Result: entire document becomes one chunk
- No meaningful splitting happens

**The tuning challenge:**

- Different documents have different "baseline" similarity
- Technical documents: adjacent sentences often highly similar (0.7-0.9)
- News articles: topic shifts are common, baseline similarity lower (0.5-0.7)
- A threshold that works for legal documents might over-split blog posts

---

## Variations on the Basic Approach

### 1. Sliding Window Comparison

Instead of comparing only adjacent sentences, compare each sentence to a window of previous sentences:

```
Window size: 3

For S5, compare to average of [S2, S3, S4], not just S4
```

This smooths out noise from single outlier sentences.

### 2. Percentile-Based Thresholds

Instead of a fixed threshold, use the Nth percentile of all similarity scores:

```
All similarities: [0.87, 0.82, 0.23, 0.71, 0.65, 0.78, 0.31, 0.69]
20th percentile: ~0.31

Split at the lowest 20% of similarity scores
```

This adapts to each document's similarity distribution.

### 3. Gradient-Based Detection

Look for _drops_ in similarity rather than absolute values:

```
sim(S1,S2) = 0.85
sim(S2,S3) = 0.83  → drop of 0.02
sim(S3,S4) = 0.45  → drop of 0.38  ← SIGNIFICANT DROP
sim(S4,S5) = 0.72  → increase of 0.27
```

A large _change_ in similarity signals a topic shift, even if absolute values are moderate.

### 4. Combining with Size Constraints

Pure semantic chunking can produce wildly varying chunk sizes. A long section on one topic becomes one huge chunk. A rapid topic-switching section becomes many tiny chunks.

Solution: Apply semantic chunking first, then split oversized chunks using recursive strategy, and merge undersized adjacent chunks if their similarity is above threshold.

### 5. Standard Deviation Threshold for Semantic Chunking

This is one of the `breakpoint_threshold_type` options in LangChain's `SemanticChunker`.
**How It Works**
1. Compute similarity (or distance) between all adjacent sentence pairs
2. Calculate the **mean** and **standard deviation** of all these scores
3. Mark a boundary where the distance is **X standard deviations above the mean**

```
Distances: [0.15, 0.12, 0.18, 0.71, 0.14, 0.16, 0.68, 0.13]

Mean: 0.28
Std Dev: 0.24

Threshold (mean + 1.5 * std): 0.28 + 0.36 = 0.64

Boundaries at: 0.71 ✓, 0.68 ✓ (both exceed 0.64)
```

**Why Use It**
It's **outlier detection**. Instead of asking "is this similarity low?" you're asking "is this similarity unusually low compared to this document's pattern?"

| Method             | Question It Answers                                |
| ------------------ | -------------------------------------------------- |
| Absolute threshold | "Is similarity below 0.5?"                         |
| Percentile         | "Is this in the bottom 20% of similarities?"       |
| Standard deviation | "Is this statistically unusual for this document?" |

Standard deviation is more sensitive to documents with consistent similarity — a small drop stands out as an outlier. Percentile treats all documents the same regardless of variance.

**When to Use**
- Documents with **consistent similarity** (technical docs, formal writing) — small drops are meaningful
- When you want **fewer, more confident** boundaries — outliers only

Percentile is more commonly used because it's simpler to tune ("bottom 10%" is intuitive). Standard deviation requires understanding your data's variance.

---

## Implementation Approaches

### Simple Implementation (Conceptual)

```python
from sentence_transformers import SentenceTransformer
import numpy as np

def semantic_chunk(text: str, threshold: float = 0.5) -> list[str]:
    # Split into sentences (simplified — production needs better sentence detection)
    sentences = text.replace('\n', ' ').split('. ')
    sentences = [s.strip() + '.' for s in sentences if s.strip()]
    
    if len(sentences) <= 1:
        return [text]
    
    # Embed all sentences
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(sentences)
    
    # Find boundaries where similarity drops below threshold
    boundaries = [0]  # First sentence always starts a chunk
    
    for i in range(1, len(sentences)):
        similarity = np.dot(embeddings[i-1], embeddings[i]) / (
            np.linalg.norm(embeddings[i-1]) * np.linalg.norm(embeddings[i])
        )
        if similarity < threshold:
            boundaries.append(i)
    
    # Form chunks from boundaries
    chunks = []
    for i, start in enumerate(boundaries):
        end = boundaries[i+1] if i+1 < len(boundaries) else len(sentences)
        chunk = ' '.join(sentences[start:end])
        chunks.append(chunk)
    
    return chunks
```

### LlamaIndex's SemanticSplitterNodeParser

LlamaIndex provides a production implementation:

```python
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding

splitter = SemanticSplitterNodeParser(
    buffer_size=1,              # Sentences to compare on each side
    breakpoint_percentile_threshold=95,  # Top 5% similarity drops become boundaries
    embed_model=OpenAIEmbedding()
)

nodes = splitter.get_nodes_from_documents(documents)
```

Note: Verify current API against LlamaIndex documentation — this is a fast-moving library.

### LangChain's SemanticChunker

```python
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings

chunker = SemanticChunker(
    embeddings=OpenAIEmbeddings(),
    breakpoint_threshold_type="percentile",  # or "standard_deviation", "interquartile"
    breakpoint_threshold_amount=95
)

chunks = chunker.split_text(document)
```

Note: This is in `langchain_experimental` — API may change. Check current docs.

---

## The Cost Problem

Semantic chunking embeds every sentence individually. For a 10,000-word document:

- ~500 sentences
- 500 embedding API calls (or one batched call with 500 inputs)
- If using OpenAI's ada-002: ~500 × 30 tokens average = 15,000 tokens for embedding alone

Compare to recursive chunking: 0 embedding calls during chunking (embeddings happen later, once, for final chunks).

**Cost comparison for 1000 documents:**

|Strategy|Embedding Calls During Chunking|Embedding Calls for Final Chunks|
|---|---|---|
|Fixed/Recursive|0|~20,000 (assuming ~20 chunks/doc)|
|Semantic|~500,000 (every sentence)|~20,000 (final chunks)|

Semantic chunking adds 25× more embedding cost in this example.

---

## What Semantic Chunking Breaks

### 1. Sentence Detection Failures

Semantic chunking depends on accurate sentence splitting. If your sentence splitter fails:

```
"Dr. Smith earned her Ph.D. in 2019. She joined the company that year."
```

Naive splitting on `.` produces:

```
"Dr"
"Smith earned her Ph"
"D"
"in 2019"
"She joined the company that year"
```

Garbage in, garbage out. Embeddings of these fragments are meaningless, boundaries are random.

### 2. Short Documents

For a document with 5 sentences, you have 4 similarity comparisons. Statistical detection of "significant drops" is unreliable with so few data points.

### 3. Uniformly Similar or Dissimilar Content

If every sentence is about the same topic (a technical specification, for example), all similarities are high. No boundaries detected. Entire document becomes one chunk.

If every sentence jumps to a new topic (a list of unrelated FAQs), all similarities are low. Every sentence becomes its own chunk.

### 4. Cross-Sentence References

```
"The API returns a JSON response. It contains three fields: status, data, and error."
```

"It" refers to "JSON response" from the previous sentence. Semantically, these are tightly coupled. But embedding "It contains three fields: status, data, and error." in isolation might produce a generic embedding that doesn't match the API context.

Embeddings don't understand coreference. Similarity might be lower than expected for actually-related sentences.

---

## When to Use Semantic Chunking

**Good fit:**

- Documents with unpredictable structure (mixed content, no consistent formatting)
- High-value use cases where retrieval quality justifies embedding cost
- Exploratory/research phase: trying to understand your data's natural boundaries
- Smaller document sets where cost isn't prohibitive

**Poor fit:**

- High-volume pipelines (cost explodes)
- Well-structured documents (recursive chunking works fine, much cheaper)
- Real-time processing (sentence embedding adds latency)
- Documents with poor sentence boundaries (code, logs, tabular data)

---

## The Hybrid Reality

Production systems rarely use pure semantic chunking. More common:

1. **Recursive chunking as primary** — handles 80% of documents well
2. **Semantic chunking for edge cases** — documents that perform poorly with recursive
3. **Post-hoc analysis** — embed chunks after recursive splitting, merge chunks with high similarity, split chunks that embed poorly

Or:

1. **Structure-aware splitting first** — use document structure (headers, sections)
2. **Semantic splitting within sections** — apply semantic chunking only to large, unstructured sections

---

## The Key Insight

Semantic chunking is the most "intelligent" strategy — it actually measures meaning. But intelligence has costs: computational expense, dependency on good sentence detection, sensitivity to threshold tuning.

Recursive chunking is a heuristic that's "usually good enough." Semantic chunking is a more precise tool that's "sometimes much better, sometimes overkill, sometimes worse."

The right choice depends on your content, your quality requirements, and your budget. There's no universally correct answer — which is why you implement multiple strategies and compare empirically.

---

