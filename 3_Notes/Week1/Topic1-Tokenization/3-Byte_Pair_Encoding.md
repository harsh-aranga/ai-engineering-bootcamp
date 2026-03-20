---

---
# Resources

| Title                         | Link                                                                                    | Notes                       |
| ----------------------------- | --------------------------------------------------------------------------------------- | --------------------------- |
| Implementing BPE From Scratch | https://sebastianraschka.com/blog/2025/bpe-from-scratch.html                            | Check Later                 |
| Hugging Face on BPE           | https://huggingface.co/learn/llm-course/en/chapter6/5                                   | Nice article explaining BPE |
| Karpathy MinBPE               | https://github.com/karpathy/minbpe                                                      | MinBPE GitHub code          |
| FastAI MinBPE                 | https://www.fast.ai/posts/2025-10-16-karpathy-tokenizers.html                           | FastAI explaining BPE       |
| OpenAI TikToken               | https://github.com/openai/tiktoken                                                      | GitHub code                 |
| GoPenAI Medium On BBPE        | https://blog.gopenai.com/byte-level-byte-pair-encoding-bbpe-in-modern-llms-e85695b90685 | Must read                   |
# What is BPE?
* Byte-Pair Encoding (BPE) was initially developed as an algorithm to compress texts, and then used by OpenAI for tokenization when pretraining the GPT model. It’s used by a lot of Transformer models, including GPT, GPT-2, RoBERTa, BART, and DeBERTa.
* **History:** Byte-pair encoding was first introduced in 1994 as a simple data compression technique by iteratively replacing the most frequent pair of bytes in a sequence with a single, unused byte. 
* It has been adapted for natural language processing, particularly for tokenization. Here, instead of bytes, BPE merges frequent characters or character sequences.
---
# History of BPE
BPE was first introduced by Philip Gage in 1994 as a simple data compression algorithm. Its core idea was to iteratively replace the most common pair of adjacent bytes in a file with a byte that does not occur in the file, thus reducing file size.

In 2015, Sennrich, Haddow, and Birch adapted BPE for NLP, using it to segment words into subword units for neural machine translation. This innovation allowed translation models to handle rare and compound words more effectively.

---
# Byte-Pair Encoding Algorithm Overview (Word-Level)
Byte-pair encoding consists of two main phases:
## 1. Vocabulary Construction
This phase takes the set of words along with their frequencies to iteratively construct a set of vocabularies (tokens). It does so by repeatedly merging the most frequent pairs of characters or tokens. The size of this vocabulary is a parameter that can be adjusted.
Vocabulary construction has 3 stages in its process
### 1. Pre-Tokenization
BPE relies on a pre-tokenization step that first splits the training text into words. For example, consider this sample text [1]:

> **_“low low low low low lower lower newest newest newest newest newest newest widest widest widest”_**

The pre-tokenization can be as simple as space tokenization or a more advanced rule-based method. The key step is to split the text into words based on spaces and append a special end-of-word symbol `_` to each word. This symbol is important as it marks word boundaries, which prevents the algorithm from confusing the end of one word with the start of another.
### 2. Frequency Assignment
Following this, we count the frequency of each unique word in the text. Using our example, we would get the following set of unique words along with their respective frequencies:

> **_(low_: 5, lower_: 2, newest_: 6, widest_: 3)_**

This set is used by BPE to construct vocabularies
### 3. Vocabulary Construction/BPE Merge Learning
The vocabulary construction involves the following steps, using the set of unique words and their frequencies obtained from pre-tokenization:

> **_(low_: 5, lower_: 2, newest_: 6, widest_: 3)_**
#### **1. Base Vocabulary Creation**
Create the base vocabulary from all unique symbols (characters) present in the word set:

> **_vocabs = (l, o, w, e, r, n, s, t, i, d, _)_**
#### **2. Represent the Words with Base Vocabs**
Express each word as symbols from the base vocabulary:

> **_((l, o, w, _): 5, (l, o, w, e, r, _): 2, (n, e, w, e, s, t, _): 6, (w, i, d, e, s, t, _): 3)_**
#### **3. Vocabulary Merging**
Iteratively merge the most frequent pairs of symbols:
- **Merge 1:** Merge the most frequent pair _(e, s),_ which occurs _6 + 3 = 9_ times, to form the newly merged symbol _‘es’._ Update the vocabulary and replace every occurrence of _(e, s)_ with _‘es’_:

> **_vocabs = (l, o, w, e, r, n, s, t, i, d, _, es)_**
> 
> **_((l, o, w, _): 5, (l, o, w, e, r, _): 2, (n, e, w, es, t, _): 6, (w, i, d, es, t, _): 3)_**

- **Merge 2:** Merge the most frequent pair _(es, t),_ which occurs _6 + 3 = 9_ times, to form the newly merged symbol _‘est’._ Update the vocabulary and replace every occurrence of _(es, t)_ with _‘est’_:

> **_vocabs = (l, o, w, e, r, n, s, t, i, d, _, es, est)_**
> 
> **_((l, o, w, _): 5, (l, o, w, e, r, _): 2, (n, e, w, est, _): 6, (w, i, d, est, _): 3)_**

- **Merge 3:** Merge the most frequent pair _(est, _),_ which occurs _6 + 3 = 9_ times, to form the newly merged symbol _‘est_’._ Update the vocabulary and replace every occurrence of _(est, _)_ with _‘est_’_:

> **_vocabs = (l, o, w, e, r, n, s, t, i, d, _, es, est, est_)_**
> 
> **_((l, o, w, _): 5, (l, o, w, e, r, _): 2, (n, e, w, est_): 6, (w, i, d, est_): 3)_**

- **Merge 4:** Merge the most frequent pair _(l, o),_ which occurs _5 + 2 = 7_ times, to form the newly merged symbol _‘lo’._ Update the vocabulary and replace every occurrence of _(l, o)_ with _‘lo’_:

> **_vocabs = (l, o, w, e, r, n, s, t, i, d, _, es, est, est_, lo)_**
> 
> **_((lo, w, _): 5, (lo, w, e, r, _): 2, (n, e, w, est_): 6, (w, i, d, est_): 3)_**

- **Merge 5:** Merge the most frequent pair _(lo, w),_ which occurs _5 + 2 = 7_ times, to form the newly merged symbol _‘low’._ Update the vocabulary and replace every occurrence of _(lo, w)_ with _‘low’_:

> **_vocabs = (l, o, w, e, r, n, s, t, i, d, _, es, est, est_, lo, low)_**
> 
> **_((low, _): 5, (low, e, r, _): 2, (n, e, w, est_): 6, (w, i, d, est_): 3)_**
#### 4. Final Vocabulary & Merge Rules

Continue merging until reaching the desired vocabulary size. The final vocabulary and merge rules after our five merges would be:

> **_vocabs = (l, o, w, e, r, n, s, t, i, d, _, es, est, est_, lo, low)_**
> 
> **_(e, s) → es, (es, t) → est, (est, _) → est_, (l, o) → lo, (lo, w) → low_**

## 2. Tokenization
This phase uses the constructed vocabulary and the learned merge rules to tokenize new text. It does so by breaking down the new text into the tokens that were identified in the vocabulary construction phase.
Let’s tokenize a sample new text:

> **_“newest binded lowers”_**
### 1. Pre-Tokenization for New Text
Similar to the initial step, we pre-tokenize the new text by splitting it into words and appending the end-of-word symbol _‘_’_. The pre-tokenized text is:

> **_(newest_, binded_, lowers_)_**
### 2. Apply Merge Rules
We first break down the pre-tokenized text into characters:

> **_((n, e, w, e, s, t, _), (b, i, n, d, e, d, _), (l, o, w, e, r, s, _))_**

Then, we apply the merged rules in their learned order. In our case, the order is:

> **_(e, s) → es, (es, t) → est, (est, _) → est_, (l, o) → lo, (lo, w) → low_**

- **Apply Merge Rule (e, s) → es:**

> **_((n, e, w, es, t, _), (b, i, n, d, e, d, _), (l, o, w, e, r, s, _))_**

- **Apply Merge Rule (es, t) → est:**

> **_((n, e, w, est, _), (b, i, n, d, e, d, _), (l, o, w, e, r, s, _))_**

- **Apply Merge Rule (est, _) → est_:**

> **_((n, e, w, est_), (b, i, n, d, e, d, _), (l, o, w, e, r, s, _))_**

- **Apply Merge Rule (l, o) → lo:**

> **_((n, e, w, est_), (b, i, n, d, e, d, _), (lo, w, e, r, s, _))_**

- **Apply Merge Rule (lo, w) → low:**

> **_((n, e, w, est_), (b, i, n, d, e, d, _), (low, e, r, s, _))_**

Any token not in the vocabulary will be replaced by an unknown token _“[UNK]”_:

> **_vocabs = (l, o, w, e, r, n, s, t, i, d, _, es, est, est_, lo, low)_**
> 
> **_((n, e, w, est_), ([UNK], i, n, d, e, d, _), (low, e, r, s, _))_**
### 3. Result of Tokenization
The new text is tokenized into the following sequence:

> **_“newest binded lowers” =_**
> 
> **_[n, e, w, est_, [UNK], i, n, d, e, d, _, low, e, r, s, _]_**

Through this process, BPE efficiently tokenizes new text using the vocabulary and merge rules, which includes handling unknown words or subwords with unknown tokens.

---
# Byte-Pair Encoding Algorithm Overview (Byte-Level)

## Core Concept
Instead of starting with characters, byte-level BPE starts with **256 raw bytes** (0x00 to 0xFF) as the base vocabulary. This means:
- **No unknown tokens** - any Unicode text can be represented
- Works for **any language** without special casing
- Handles emojis, special characters, multilingual text seamlessly

---
## Basic Process

### Step 1: Text to Bytes
```python
text = "Dog is barking."
tokens = list(text.encode("utf-8"))
# [68, 111, 103, 32, 105, 115, 32, 98, 97, 114, 107, 105, 110, 103, 46]
```

Each byte is a number from 0-255. Initial vocabulary = 256 bytes.
### Step 2: Find Frequent Pairs
Count adjacent byte pairs across entire corpus:
```python
# Example frequency counts:
# (105, 110) = "in" → 1000 times
# (110, 103) = "ng" → 850 times
# (32, 116) = " t" → 720 times
```
### Step 3: Merge Most Frequent Pair
```python
# Merge (105, 110) into new token ID 256
bytes([105, 110]).decode("utf-8")  # "in"

# Update tokens:
# [98, 97, 114, 107, 256, 103, 46]  # "bark" + token_256 + "g."
```
### Step 4: Repeat
Continue until vocabulary reaches target size (e.g., 50,257 for GPT-2).

---
## Critical Production Detail: Regex Pre-tokenization

**PROBLEM:** Raw byte-level BPE creates garbage tokens.
### Without Regex (Bad)
```python
text = "Dog is barking. barking. barking."
# Converts to single byte stream:
# [68, 111, 103, 32, 105, 115, 32, 98, 97, 114, 107, 105, 110, 103, 46, ...]

# Frequent pairs:
# (103, 46) = "g." appears 3 times ← USELESS TOKEN!
# (32, 98) = " b" appears 3 times ← WASTE OF VOCAB SPACE!
```

**Result:** Learns tokens like `"g."`, `" the"`, `"ing,"` - too specific, not reusable.

---
### With Regex Pre-tokenization (Good - GPT-2/GPT-4 approach)

**GPT-2 Regex Pattern:**
```python
pattern = r"""'s|'t|'re|'ve|'m|'ll|'d| ?\w+| ?\d+| ?[^\s\w\d]+|\s+"""
```

**What it does:**
- Keeps words together (`dog` stays as one chunk)
- Separates punctuation (`.` is its own chunk)
- Handles contractions (`don't` → `don`, `'t`)
- Groups numbers together
- Preserves leading spaces on words (` dog` vs `dog`)

**Example:**
```python
import re
text = "Dog is barking. barking. barking."
chunks = re.findall(pattern, text)
# ['Dog', ' is', ' barking', '.', ' barking', '.', ' barking', '.']
```

**Now apply BPE to EACH chunk separately:**
```
Chunk: ' barking' → [32, 98, 97, 114, 107, 105, 110, 103]
Chunk: '.'        → [46]

BPE merges happen WITHIN chunks:
- (105, 110) = "in" in ' barking' → valid merge ✓
- (110, 103) = "ng" in ' barking' → valid merge ✓
- (103, 46) = "g." NEVER appears (different chunks) → no garbage ✓
```

**Result:** Learns useful subwords like `"ing"`, `"ed"`, `"pre"` instead of `"g."` or `" the"`.

---
## Visual Comparison

### Without Regex:
```
"barking." as one stream:
[98, 97, 114, 107, 105, 110, 103, 46]
 b   a   r   k   i   n   g   .
                             ↑
                   Can merge (103, 46) → "g." token (BAD)
```
### With Regex:
```
"barking" chunk: [98, 97, 114, 107, 105, 110, 103]
"." chunk:       [46]

Separate chunks → (103, 46) never adjacent → no merge ✓
```

---
## Decoding: Handling Invalid UTF-8

**Problem:** During merging, you might create byte sequences that aren't valid UTF-8.
```python
# This can crash:
bytes([105, 200]).decode("utf-8")  # UnicodeDecodeError!
```

**Solution:** Always use error handling
```python
bytes([105, 200]).decode("utf-8", errors="replace")  # → "i�"
```

**GPT models use:**
- `errors="replace"` - replaces invalid bytes with �
- OR byte-to-unicode mapping tables to ensure every byte is decodable

---
## Why Non-English Costs More

**ASCII characters:** 1 byte = 1 character
```python
"hello".encode("utf-8")  # 5 bytes → ~2-3 tokens after BPE
```

**Non-ASCII (Hindi, Chinese, Emoji):** 2-4 bytes per character
```python
"नमस्ते".encode("utf-8")  # 18 bytes for 6 chars → ~8-12 tokens
"你好".encode("utf-8")     # 6 bytes for 2 chars → ~3-4 tokens
"😀".encode("utf-8")       # 4 bytes for 1 emoji → ~2-3 tokens
```

**Impact:**
- Hindi/Chinese text uses **2-3x more tokens** than English
- Direct cost impact on API usage (charged per token)
- Slower processing (more tokens to process)

---
## Production Checklist

When working with byte-level BPE:

✅ **Understand the base vocab is 256 bytes** (not characters)
✅ **Know that regex pre-tokenization prevents garbage tokens**
✅ **Remember non-English = more tokens = higher cost**
✅ **Use error handling when decoding bytes**
✅ **Vocabulary size = 256 base + N merges + special tokens**

---
## Key Differences: Word-Level vs Byte-Level BPE

| Aspect | Word-Level BPE | Byte-Level BPE |
|--------|---------------|----------------|
| Base vocab | Characters (a-z, A-Z, etc.) | 256 bytes (0x00-0xFF) |
| Unknown tokens | Needs `<UNK>` for rare chars | No `<UNK>` - everything is representable |
| Emoji handling | Often becomes `<UNK>` | Encoded as 4 bytes, mergeable |
| Multilingual | Needs special handling | Works automatically |
| Token efficiency | Good for ASCII text | Less efficient for non-ASCII |
| Production use | Rare (legacy models) | Standard (GPT-2/3/4, LLaMA, Claude) |

---
## Real-World Examples

### GPT-2 Tokenizer
- Vocabulary size: 50,257
  - 256 base bytes
  - 50,000 learned merges
  - 1 special token (`<|endoftext|>`)
- Uses regex pre-tokenization
- Byte-to-unicode mapping for safe decoding

### GPT-4 Tokenizer (tiktoken)
- Vocabulary size: ~100,000
- Same regex pattern as GPT-2 (with additions)
- More merges = longer common subwords = fewer tokens for same text
- **Why code uses fewer tokens in GPT-4:** Learned merges for common code patterns like `"def "`, `"import "`, `"return "`

---
## When This Knowledge Matters

**Production scenarios where byte-level BPE understanding is critical:**
1. **Token counting for cost estimation**
   - "How many tokens is this Hindi document?" → Need to know it's ~2-3x English  
2. **Context window optimization**
   - "Why does this fit in GPT-3 but not GPT-2?" → Different merge rules
3. **Debugging weird tokenization**
   - "Why is 'café' 2 tokens?" → é = 2 bytes in UTF-8  
4. **Cross-model compatibility**
   - "Can I use GPT-2 tokenizer for LLaMA?" → No, different merge rules
5. **Building custom tokenizers**
   - Need regex pre-tokenization or you'll learn garbage tokens

---
## Quick Reference: Common Byte Sequences
```python
# Space
" ".encode("utf-8")      # [32]

# Newline
"\n".encode("utf-8")     # [10]

# Common prefixes (after merging)
"un".encode("utf-8")     # [117, 110] → often merged
"re".encode("utf-8")     # [114, 101] → often merged
"ing".encode("utf-8")    # [105, 110, 103] → often merged

# Non-ASCII
"é".encode("utf-8")      # [195, 169] → 2 bytes
"😀".encode("utf-8")     # [240, 159, 152, 128] → 4 bytes
```

---
## Summary: The Full Pipeline

1. **Input:** "Dog is barking."
2. **Regex split:** `['Dog', ' is', ' barking', '.']`
3. **Encode each chunk to bytes:**
   - `'Dog'` → `[68, 111, 103]`
   - `' is'` → `[32, 105, 115]`
   - `' barking'` → `[32, 98, 97, 114, 107, 105, 110, 103]`
   - `'.'` → `[46]`
4. **Apply learned merges within each chunk:**
   - `[32, 98, 97, 114, 107, 105, 110, 103]` → `[32, 98, 97, 114, 107, 256, 103]` (if (105,110) merged to 256)
5. **Final token IDs:** `[68, 111, 103, 32, 105, 115, 32, 98, 97, 114, 107, 256, 103, 46]`
6. **Decoding:** Reverse the process - replace token IDs with bytes, concatenate, decode UTF-8