# Reranking Models: Cohere, BGE, and Sentence-Transformers

## Overview: The Reranker Landscape

Reranking models fall into three categories:

|Category|Examples|Trade-off|
|---|---|---|
|**Managed APIs**|Cohere Rerank, Voyage Rerank|Easy setup, pay-per-use, no GPU needed|
|**Open-source (lightweight)**|sentence-transformers cross-encoders, BGE-reranker-base|Fast, free, runs on modest hardware|
|**Open-source (LLM-based)**|BGE-reranker-v2-gemma, BGE-reranker-v2-minicpm|Higher quality, needs GPU, slower|

The decision depends on: latency requirements, cost constraints, deployment environment, and quality needs.

---

## 1. Cohere Rerank (Managed API)

### What It Is

Cohere Rerank is a hosted reranking service. You send a query + documents via API, get back relevance scores. No model hosting, no GPU management.

### Current Models (as of early 2025)

|Model|Languages|Context|Notes|
|---|---|---|---|
|`rerank-v4.0-pro`|100+ languages|4096 tokens|Highest quality|
|`rerank-v4.0-fast`|100+ languages|4096 tokens|Faster, slightly lower quality|
|`rerank-v3.5`|100+ languages|4096 tokens|Previous generation|

### Usage

```python
import cohere

co = cohere.ClientV2(api_key="YOUR_API_KEY")

query = "What is RLHF?"
documents = [
    "RLHF uses human feedback to fine-tune language models.",
    "Reinforcement learning is a type of machine learning.",
    "The Python programming language was created by Guido van Rossum.",
    "InstructGPT was trained using RLHF to follow instructions better.",
]

response = co.rerank(
    model="rerank-v3.5",
    query=query,
    documents=documents,
    top_n=3  # Return top 3 most relevant
)

for result in response.results:
    print(f"Score: {result.relevance_score:.4f} | Index: {result.index}")
    print(f"  {documents[result.index][:60]}...")
```

### Key Features

1. **Automatic chunking:** Long documents are chunked internally; final score = max score across chunks
2. **Structured data support:** Pass YAML-formatted strings for tables, JSON, etc.
3. **Multilingual:** Single model handles 100+ languages
4. **Score interpretation:** Scores are 0-1, but **relative ranking matters more than absolute values**

### Pricing Consideration

Cohere charges per "search unit" (query + documents scored). At scale, costs add up. Calculate:

```
Monthly cost = queries/month × avg_docs_per_query × price_per_1000_docs
```

### When to Use Cohere

✅ Prototyping and MVPs (fast to integrate) ✅ No GPU infrastructure available ✅ Multilingual requirements out of the box ✅ Enterprise support/SLA needed

❌ High-volume, cost-sensitive applications ❌ Air-gapped or on-prem requirements ❌ Need to fine-tune on domain data

---

## 2. BGE Reranker (Open Source, BAAI)

### What It Is

BGE (BAAI General Embedding) rerankers are open-source cross-encoder models from the Beijing Academy of Artificial Intelligence. They're among the top performers on reranking benchmarks.

### Model Family

|Model|Base|Size|Speed|Quality|Use Case|
|---|---|---|---|---|---|
|`bge-reranker-base`|XLM-RoBERTa|278M|Fast|Good|General purpose|
|`bge-reranker-large`|XLM-RoBERTa|560M|Medium|Better|When quality matters|
|`bge-reranker-v2-m3`|BGE-M3|568M|Medium|Better|Multilingual|
|`bge-reranker-v2-gemma`|Gemma-2B|2B|Slow|High|Best quality (English)|
|`bge-reranker-v2-minicpm-layerwise`|MiniCPM-2B|2B|Configurable|High|Quality + flexibility|
|`bge-reranker-v2.5-gemma2-lightweight`|Gemma2-9B|9B|Configurable|Highest|SOTA, with compression|

### Usage with FlagEmbedding

```python
from FlagEmbedding import FlagReranker

# Lightweight model — good balance of speed and quality
reranker = FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=True)

# Single pair
score = reranker.compute_score(['What is RLHF?', 'RLHF trains models using human feedback.'])
print(f"Raw score: {score}")  # Raw logit, can be negative

# Normalized to 0-1 range
score = reranker.compute_score(
    ['What is RLHF?', 'RLHF trains models using human feedback.'],
    normalize=True
)
print(f"Normalized score: {score}")  # 0-1 via sigmoid

# Multiple pairs (batched)
scores = reranker.compute_score([
    ['What is RLHF?', 'RLHF trains models using human feedback.'],
    ['What is RLHF?', 'Python is a programming language.'],
    ['What is RLHF?', 'InstructGPT uses RLHF for alignment.'],
])
print(scores)  # List of scores
```

### Usage with Transformers (Direct)

```python
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_name = 'BAAI/bge-reranker-v2-m3'
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)
model.eval()

pairs = [
    ['What is RLHF?', 'RLHF trains models using human feedback.'],
    ['What is RLHF?', 'Python is a programming language.'],
]

with torch.no_grad():
    inputs = tokenizer(
        pairs,
        padding=True,
        truncation=True,
        return_tensors='pt',
        max_length=512
    )
    scores = model(**inputs).logits.view(-1).float()
    
print(scores)  # tensor([5.2617, -8.1875])

# Apply sigmoid for 0-1 scores
normalized = torch.sigmoid(scores)
print(normalized)  # tensor([0.9948, 0.0003])
```

### LLM-Based Rerankers (Higher Quality)

For maximum quality, use the LLM-based variants:

```python
from FlagEmbedding import FlagLLMReranker

# Gemma-based reranker (2B params)
reranker = FlagLLMReranker('BAAI/bge-reranker-v2-gemma', use_fp16=True)
score = reranker.compute_score(['query', 'passage'])
```

### Layerwise Reranking (Speed-Quality Trade-off)

The `minicpm-layerwise` model lets you choose which layers to use for scoring — earlier layers are faster but less accurate:

```python
from FlagEmbedding import LayerWiseFlagLLMReranker

reranker = LayerWiseFlagLLMReranker(
    'BAAI/bge-reranker-v2-minicpm-layerwise',
    use_fp16=True
)

# Use layer 28 (full model, highest quality)
score_full = reranker.compute_score(['query', 'passage'], cutoff_layers=[28])

# Use layer 8 (faster, lower quality)
score_fast = reranker.compute_score(['query', 'passage'], cutoff_layers=[8])
```

### When to Use BGE

✅ Self-hosted / on-prem requirements ✅ Cost-sensitive (no per-query charges) ✅ Need to fine-tune on domain data ✅ Multilingual with `bge-reranker-v2-m3` ✅ Maximum quality with LLM-based variants

❌ No GPU available (CPU inference is slow) ❌ Need managed service / SLA

---

## 3. Sentence-Transformers Cross-Encoders

### What It Is

The `sentence-transformers` library provides pre-trained cross-encoder models, primarily trained on MS MARCO (Bing search queries + relevant passages). These are lightweight, battle-tested, and easy to use.

### Available Models

|Model|Params|Speed|Quality|Notes|
|---|---|---|---|---|
|`cross-encoder/ms-marco-TinyBERT-L-2-v2`|4M|Very fast|Lower|When latency is critical|
|`cross-encoder/ms-marco-MiniLM-L-6-v2`|22M|Fast|Good|**Best speed/quality trade-off**|
|`cross-encoder/ms-marco-MiniLM-L-12-v2`|33M|Medium|Better|More accurate than L-6|
|`cross-encoder/ms-marco-electra-base`|110M|Slower|High|ELECTRA-based|

### Usage

```python
from sentence_transformers import CrossEncoder

# Load the model
model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

# Score pairs
scores = model.predict([
    ("What is RLHF?", "RLHF uses human feedback to train language models."),
    ("What is RLHF?", "Python is a programming language."),
    ("What is RLHF?", "InstructGPT was trained using RLHF."),
])

print(scores)
# array([ 8.123, -4.567,  6.789], dtype=float32)
```

**Note:** MS MARCO models output raw logits (can be negative). The ranking is what matters, not the absolute value. If you need 0-1 scores:

```python
import torch

model = CrossEncoder(
    'cross-encoder/ms-marco-MiniLM-L-6-v2',
    default_activation_function=torch.nn.Sigmoid()
)

scores = model.predict([...])  # Now 0-1
```

### The `.rank()` Method

Convenience method for reranking:

```python
from sentence_transformers import CrossEncoder

model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

query = "What is RLHF?"
documents = [
    "RLHF uses human feedback to train language models.",
    "Python is a programming language.",
    "InstructGPT was trained using RLHF.",
    "Reinforcement learning from human feedback aligns AI with human values.",
]

results = model.rank(query, documents, return_documents=True, top_k=3)

for r in results:
    print(f"Rank {r['corpus_id']}: Score {r['score']:.2f}")
    print(f"  {r['text'][:60]}...")
```

### When to Use Sentence-Transformers

✅ Quick prototyping (pip install + 2 lines of code) ✅ Lightweight deployment (MiniLM is only 22M params) ✅ English-focused use cases (trained on MS MARCO) ✅ Familiar API if already using sentence-transformers

❌ Multilingual (use BGE or Cohere instead) ❌ Need SOTA quality (BGE LLM-based models are better)

---

## Model Comparison

### Benchmark Performance (Approximate)

|Model|NDCG@10 (MS MARCO)|Latency (100 docs)|GPU Required|
|---|---|---|---|
|`ms-marco-MiniLM-L-6-v2`|~38%|~100ms|Optional|
|`bge-reranker-large`|~41%|~200ms|Recommended|
|`bge-reranker-v2-m3`|~42%|~250ms|Recommended|
|`bge-reranker-v2-gemma`|~44%|~800ms|Required|
|Cohere `rerank-v3.5`|~45%|~300ms (API)|No|

_Note: Exact numbers vary by benchmark and hardware. Test on your data._

### Decision Framework

```
START
  │
  ├── Need managed service / no GPU?
  │     └── YES → Cohere Rerank
  │
  ├── Need multilingual?
  │     └── YES → BGE-reranker-v2-m3 or Cohere
  │
  ├── Latency critical (< 100ms for 100 docs)?
  │     └── YES → ms-marco-MiniLM-L-6-v2 or TinyBERT
  │
  ├── Maximum quality, have GPU?
  │     └── YES → BGE-reranker-v2-gemma or minicpm-layerwise
  │
  └── Good balance, self-hosted?
        └── YES → bge-reranker-v2-m3 or bge-reranker-large
```

---

## Practical Implementation

### Unified Reranker Interface

Abstract away the model choice:

```python
from abc import ABC, abstractmethod
from typing import List, Tuple

class Reranker(ABC):
    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 10
    ) -> List[Tuple[int, float, str]]:
        """Returns list of (original_index, score, text) sorted by relevance."""
        pass


class SentenceTransformersReranker(Reranker):
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(model_name)
    
    def rerank(self, query: str, documents: List[str], top_k: int = 10):
        pairs = [(query, doc) for doc in documents]
        scores = self.model.predict(pairs)
        
        results = [
            (i, float(score), doc)
            for i, (score, doc) in enumerate(zip(scores, documents))
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


class BGEReranker(Reranker):
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        from FlagEmbedding import FlagReranker
        self.model = FlagReranker(model_name, use_fp16=True)
    
    def rerank(self, query: str, documents: List[str], top_k: int = 10):
        pairs = [[query, doc] for doc in documents]
        scores = self.model.compute_score(pairs, normalize=True)
        
        if isinstance(scores, float):
            scores = [scores]
        
        results = [
            (i, float(score), doc)
            for i, (score, doc) in enumerate(zip(scores, documents))
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


class CohereReranker(Reranker):
    def __init__(self, api_key: str, model: str = "rerank-v3.5"):
        import cohere
        self.client = cohere.ClientV2(api_key=api_key)
        self.model = model
    
    def rerank(self, query: str, documents: List[str], top_k: int = 10):
        response = self.client.rerank(
            model=self.model,
            query=query,
            documents=documents,
            top_n=top_k
        )
        
        return [
            (r.index, r.relevance_score, documents[r.index])
            for r in response.results
        ]
```

### Usage

```python
# Swap rerankers without changing downstream code
reranker = SentenceTransformersReranker()
# reranker = BGEReranker()
# reranker = CohereReranker(api_key="...")

query = "What is RLHF?"
documents = [...]

results = reranker.rerank(query, documents, top_k=5)
for idx, score, text in results:
    print(f"[{idx}] {score:.4f}: {text[:50]}...")
```

---

## Fine-Tuning Considerations

All three options support fine-tuning (with varying effort):

|Option|Fine-tuning Approach|
|---|---|
|**Cohere**|Not supported (as of early 2025, fine-tuning for rerank was deprecated)|
|**BGE**|Supported via FlagEmbedding library, requires labeled (query, positive, negative) triples|
|**Sentence-Transformers**|Supported via `CrossEncoderTrainer`, well-documented|

For domain-specific use cases (medical, legal, technical), fine-tuning can provide significant gains — but requires labeled data.

---

## Key Takeaways

1. **Cohere Rerank** = managed API, easy setup, multilingual, costs at scale
    
2. **BGE Rerankers** = open-source SOTA, range from lightweight to LLM-based, multilingual support
    
3. **Sentence-Transformers** = battle-tested, lightweight, English-focused, easiest to start with
    
4. **Start with `ms-marco-MiniLM-L-6-v2`** for prototyping — it's fast, free, and good enough to validate your pipeline
    
5. **Graduate to BGE or Cohere** when you need multilingual support or higher quality
    
6. **Benchmark on your data** — model rankings on public benchmarks may not match your domain
    
7. **The reranker choice matters less than having one** — even a simple reranker dramatically improves over bi-encoder retrieval alone