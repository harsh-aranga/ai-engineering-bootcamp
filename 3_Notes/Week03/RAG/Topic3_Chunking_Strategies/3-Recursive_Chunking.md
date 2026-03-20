# Recursive Chunking: Respecting Natural Boundaries

## The Core Idea

Recursive chunking tries to split text at natural boundaries — paragraphs first, then sentences, then words — rather than at arbitrary character positions. It's "recursive" because when a chunk is too large, the algorithm recursively applies smaller separators until the chunk fits within the size limit.

The goal: chunks that are both within size limits AND contain coherent, complete thoughts.

---

## How It Works Mechanically

You define a hierarchy of separators, from largest to smallest:

```
Separators (in priority order):
1. "\n\n"  — Paragraph breaks (double newline)
2. "\n"    — Line breaks (single newline)
3. ". "    — Sentence endings
4. " "     — Word boundaries
5. ""      — Character-level (last resort)
```

The algorithm:

1. Try to split text using the first separator (`\n\n`)
2. For each resulting piece:
    - If it's within chunk_size → keep it
    - If it's too large → recursively split using the _next_ separator in the hierarchy
3. Continue until all pieces fit within chunk_size

---

## Step-by-Step Example

```
Document:
"# Introduction

This is the first paragraph. It explains the basics.

This is the second paragraph. It goes into more detail about the topic and provides examples that help clarify the concepts being discussed."

Chunk size: 80 characters
Separators: ["\n\n", "\n", ". ", " "]
```

**Step 1: Split on `\n\n` (paragraphs)**

```
Piece 1: "# Introduction"                                    → 14 chars ✓
Piece 2: "This is the first paragraph. It explains the basics." → 52 chars ✓
Piece 3: "This is the second paragraph. It goes into more detail about the topic and provides examples that help clarify the concepts being discussed." → 141 chars ✗ TOO LARGE
```

**Step 2: Piece 3 is too large, split it on `". "` (sentences)**

```
Piece 3a: "This is the second paragraph."                     → 30 chars ✓
Piece 3b: "It goes into more detail about the topic and provides examples that help clarify the concepts being discussed." → 110 chars ✗ STILL TOO LARGE
```

**Step 3: Piece 3b is still too large, split on `" "` (words)**

Now the algorithm splits at word boundaries, grouping words until hitting the size limit:

```
Piece 3b-1: "It goes into more detail about the topic and provides examples that help" → 73 chars ✓
Piece 3b-2: "clarify the concepts being discussed." → 37 chars ✓
```

**Final chunks:**

```
Chunk 0: "# Introduction"
Chunk 1: "This is the first paragraph. It explains the basics."
Chunk 2: "This is the second paragraph."
Chunk 3: "It goes into more detail about the topic and provides examples that help"
Chunk 4: "clarify the concepts being discussed."
```

Notice: Chunks 1 and 2 are complete sentences. Chunk 3-4 had to split mid-sentence (because the sentence exceeded 80 chars), but at least it split at a word boundary, not mid-word.

---

## Why the Hierarchy Matters

Each separator level represents a different granularity of meaning:

|Separator|What It Preserves|
|---|---|
|`\n\n`|Entire paragraphs — complete thoughts, full context|
|`\n`|Lines — often complete statements, especially in lists/code|
|`.`|Sentences — grammatically complete units|
||Words — at least you don't split "refund" into "ref" and "und"|
|`""`|Characters — last resort, equivalent to fixed-size|

The algorithm always prefers higher-level splits. It only drops to sentence-level if paragraphs are too large. It only drops to word-level if sentences are too large.

---

## What Recursive Chunking Fixes (vs Fixed-Size)

### 1. Sentences Stay Intact (Usually)

Fixed-size:

```
"The API rate limit is 100 reque" | "sts per minute."
```

Recursive (if sentence fits in chunk_size):

```
"The API rate limit is 100 requests per minute."
```

The complete sentence becomes one chunk.

### 2. Paragraphs Stay Together When Possible

If a paragraph is 400 characters and your chunk_size is 500, the entire paragraph becomes one chunk. No arbitrary mid-paragraph splits.

### 3. Code Blocks Have Better Odds

Code often has `\n` between lines. Recursive chunking tries to keep related lines together:

```python
def calculate_total(items):
    subtotal = sum(item.price for item in items)
    tax = subtotal * 0.08
    return subtotal + tax
```

If this block is under chunk_size, it stays as one chunk. If it's too large, it splits at `\n` (line breaks) — not mid-line.

---

## What Recursive Chunking Still Breaks

### 1. Long Sentences

A 500-character sentence will be split at word boundaries, which is better than mid-word, but still breaks the thought:

```
"The comprehensive refund policy stipulates that customers who purchased items through our online portal between January and March of the fiscal year are entitled to" | "a full refund within 90 days provided they retain the original receipt and packaging materials."
```

Two chunks, neither complete.

### 2. No Semantic Awareness

Recursive chunking doesn't understand _meaning_. If a paragraph discusses two unrelated topics, it stays as one chunk:

```
"Our refund policy allows returns within 30 days. In other news, we're excited to announce our new CEO, Jane Smith, who previously led operations at TechCorp."
```

This is one paragraph, so it becomes one chunk. Query "refund policy" retrieves the chunk, but 60% of it is about the new CEO.

### 3. Structured Content Without Proper Markers

Tables don't have `\n\n` between rows. Markdown lists don't always have double newlines. Recursive chunking can still mangle these if the separators don't match the structure.

### 4. Separator Choice Is Content-Dependent

The default `["\n\n", "\n", ". ", " "]` works for English prose. It fails for:

- Code with `//` or `#` comments (no `.` sentence endings)
- Languages that don't use `.` for sentence endings
- Markdown with single-newline paragraphs

You need to tune separators for your content type.

---

## The Overlap Problem in Recursive Chunking

Overlap in recursive chunking is trickier than fixed-size. If you split on paragraph boundaries and add overlap, what do you overlap?

**Option 1: Character-based overlap after splitting**

Split on separators, then take the last N characters of each chunk and prepend to the next. This can re-introduce mid-word splits at overlap boundaries.

**Option 2: Overlap by separator units**

Overlap by sentences or lines, not characters. Last sentence of Chunk N becomes first sentence of Chunk N+1.

Most implementations (including LangChain's `RecursiveCharacterTextSplitter`) use character-based overlap applied after the recursive splitting. It's a pragmatic compromise.

---

## LangChain's RecursiveCharacterTextSplitter

LangChain's implementation is the de facto standard for recursive chunking. Key parameters:

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,           # Target size in characters
    chunk_overlap=50,         # Characters of overlap
    separators=["\n\n", "\n", ". ", " "],  # Hierarchy
    length_function=len,      # How to measure size (can swap for token counter)
    is_separator_regex=False  # Treat separators as literals, not regex
)

chunks = splitter.split_text(document)
```

**What it does internally:**

1. Splits on first separator
2. If any piece > chunk_size, recursively splits with next separator
3. Merges small adjacent pieces (under chunk_size) back together
4. Applies overlap between final chunks

The "merge small pieces" step is important — it prevents a document with many short paragraphs from becoming hundreds of tiny chunks.

---

## Choosing Separators for Your Content

Default `["\n\n", "\n", ". ", " "]` works for general prose. Adjust for:

**Markdown documents:**

```python
separators=[
    "\n## ",      # H2 headers (major sections)
    "\n### ",     # H3 headers (subsections)
    "\n\n",       # Paragraphs
    "\n",         # Lines
    ". ",         # Sentences
    " "           # Words
]
```

**Python code:**

```python
separators=[
    "\nclass ",   # Class definitions
    "\ndef ",     # Function definitions
    "\n\n",       # Blank lines between blocks
    "\n",         # Individual lines
    " "           # Words (last resort)
]
```

**Legal/formal documents:**

```python
separators=[
    "\n\nSection ",    # Major sections
    "\n\nArticle ",    # Articles
    "\n\n",            # Paragraphs
    ";\n",             # Clause endings
    ". ",              # Sentences
    " "
]
```

The principle: separators should reflect your document's actual structure.

---

## Recursive vs Fixed-Size: When to Choose

|Scenario|Better Choice|
|---|---|
|Prose-heavy documents (articles, docs)|Recursive|
|Raw logs, data dumps|Fixed-size (no structure to preserve)|
|Code repositories|Recursive with code-aware separators|
|Mixed content (prose + code + tables)|Recursive, but expect imperfect results|
|Speed-critical, quality-tolerant|Fixed-size|
|Quality-critical, speed-tolerant|Recursive (or semantic)|

---

## The Key Insight

Recursive chunking is a heuristic, not a solution. It assumes that paragraph breaks and sentence endings correlate with meaning boundaries. That's often true — but not always.

When a single paragraph discusses multiple topics, recursive chunking can't help. When meaning flows across paragraph boundaries, recursive chunking might split it.

Semantic chunking (next topic) attempts to solve this by actually measuring meaning similarity between sentences. But it's computationally expensive and has its own failure modes.

For most production RAG systems, recursive chunking with tuned separators is the sweet spot — good enough quality, reasonable speed, predictable behavior.

---
