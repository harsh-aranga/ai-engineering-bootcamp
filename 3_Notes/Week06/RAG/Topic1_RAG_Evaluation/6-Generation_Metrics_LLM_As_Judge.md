# Generation Metrics & LLM-as-Judge

## The Core Insight

Retrieval metrics tell you if you found the right documents. But that's only half the story. The LLM still has to:

1. **Use the retrieved context correctly** (not hallucinate)
2. **Actually answer the question** (not ramble)
3. **Give a correct answer** (not confidently wrong)

Generation metrics measure what happens _after_ retrieval — the quality of the final answer.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Where Generation Metrics Fit                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   [Query] ──► [Retriever] ──► [Context] ──► [LLM] ──► [Answer]      │
│                    │              │            │           │        │
│                    ▼              ▼            ▼           ▼        │
│              ┌──────────┐  ┌───────────┐  ┌────────┐  ┌─────────┐   │
│              │Recall@K  │  │ Context   │  │Faithful│  │ Answer  │   │
│              │Precision │  │ Relevance │  │ -ness  │  │Relevance│   │
│              │MRR, NDCG │  │           │  │        │  │Correct- │   │
│              └──────────┘  └───────────┘  └────────┘  │ness     │   │
│                                                       └─────────┘   │
│              ◄─── Retrieval ───►  ◄───── Generation Metrics ──────► │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

The challenge: these metrics can't be computed with simple formulas like Recall or Precision. You need an LLM to judge the output — hence **LLM-as-Judge**.

---

## The Four Generation Metrics

### 1. Faithfulness

**Question**: Is the answer supported by the retrieved context?

This is hallucination detection. The LLM might generate plausible-sounding content that isn't grounded in the provided context.

```
Context: "Our refund policy allows returns within 30 days of purchase."

Query: "What's the refund policy?"

Answer A: "You can return items within 30 days of purchase."
  → Faithful ✓ (directly supported by context)

Answer B: "You can return items within 30 days, and we offer free return shipping."
  → NOT Faithful ✗ (free shipping not mentioned in context)
```

**What it catches**:

- Hallucinated facts
- LLM injecting parametric knowledge instead of using context
- Made-up details, statistics, or claims

**What it misses**:

- Whether the context was relevant in the first place
- Whether the answer addresses the question

### 2. Answer Relevance

**Question**: Does the answer actually address the question asked?

The answer might be faithful to context but completely miss the point.

```
Query: "How do I reset my password?"

Context: [Correct documentation about password reset]

Answer A: "Go to Settings > Security > Reset Password, then follow the prompts."
  → Relevant ✓ (directly answers how to reset)

Answer B: "Password security is very important for protecting your account. 
          We use industry-standard encryption..."
  → NOT Relevant ✗ (talks about passwords but doesn't answer "how to reset")
```

**What it catches**:

- Tangential responses
- Answers that discuss the topic but don't address the specific question
- Incomplete answers that miss the core ask

**What it misses**:

- Whether the answer is factually correct
- Whether it's grounded in context

### 3. Context Relevance

**Question**: Is the retrieved context relevant to the question?

This is actually a retrieval quality metric, but it's evaluated differently — by looking at the context content, not just document IDs.

```
Query: "What's the pricing for enterprise plans?"

Context A: "Enterprise plans start at $500/month with custom pricing 
           for larger deployments..."
  → Relevant ✓ (directly addresses pricing question)

Context B: "Our company was founded in 2015 in San Francisco. 
           We serve over 10,000 enterprise customers..."
  → NOT Relevant ✗ (mentions "enterprise" but not pricing)
```

**What it catches**:

- Retrieval failures that other metrics missed (high similarity but low relevance)
- Semantic mismatches where keywords match but meaning doesn't
- Context that's topically related but doesn't help answer the question

**What it misses**:

- Whether the LLM used the context correctly
- Whether the final answer is good

### 4. Correctness

**Question**: Is the answer factually correct?

This requires ground truth — you need to know the right answer to judge correctness.

```
Query: "When was the company founded?"

Ground Truth: "2015"

Answer A: "The company was founded in 2015."
  → Correct ✓

Answer B: "The company was founded in 2013."
  → NOT Correct ✗
```

**What it catches**:

- Factually wrong answers (regardless of faithfulness)
- Subtle errors in dates, numbers, names
- Misinterpretation of context

**What it requires**:

- Ground truth answers for your eval set
- This is expensive — you need human-verified correct answers

---

## How They Relate: The Diagnostic Matrix

These metrics interact. Different failure combinations point to different root causes:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Generation Metrics Diagnostic Matrix             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Context     Faithful-   Answer      What's Wrong                  │
│   Relevance   ness        Relevance                                 │
│   ─────────   ─────────   ─────────   ─────────────────────────     │
│      ✓           ✓           ✓        All good! System working.     │
│                                                                     │
│      ✗           -           -        Retrieval problem.            │
│                                       Fix chunking, embeddings,     │
│                                       or retrieval strategy.        │
│                                                                     │
│      ✓           ✗           ✓        Hallucination problem.        │
│                                       LLM ignoring context.         │
│                                       Fix prompt or use better      │
│                                       model.                        │
│                                                                     │
│      ✓           ✓           ✗        Answer formulation problem.   │
│                                       LLM has right info but        │
│                                       rambles or misses the point.  │
│                                       Fix output prompt.            │
│                                                                     │
│      ✓           ✗           ✗        Complete generation failure.  │
│                                       Context is fine, LLM is       │
│                                       broken. Check model, prompt,  │
│                                       or temperature.               │
│                                                                     │
│      ✗           ✓           ✓        Lucky guess or parametric     │
│                                       knowledge. Dangerous — works  │
│                                       until it doesn't.             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**The sneaky failure**: Context Relevance low, but Faithfulness and Answer Relevance high. This means the LLM gave a good answer _despite_ bad retrieval — probably from its parametric knowledge. It works until you ask something outside its training data.

---

## LLM-as-Judge: The Evaluation Pattern

These metrics can't be computed with formulas. You need another LLM to evaluate the outputs.

### The Basic Pattern

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM-as-Judge Pattern                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Inputs to Judge:                                                  │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  • Query (what the user asked)                              │   │
│   │  • Context (what was retrieved)                             │   │
│   │  • Answer (what the LLM generated)                          │   │
│   │  • [Optional] Ground truth (for correctness)                │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  Judge LLM with evaluation prompt:                          │   │
│   │  "Given this query, context, and answer, rate [metric]      │   │
│   │   on a scale of 0-1..."                                     │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  Output: Score (0.0 to 1.0) + Optional reasoning            │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Why LLM-as-Judge Works

1. **Language understanding**: Judging faithfulness requires understanding meaning, not just keyword matching
2. **Nuance**: "Partially correct" answers need graded scoring
3. **Flexibility**: Same pattern works for different metrics with different prompts
4. **Scale**: Once you have the prompts, evaluation scales easily

### Why LLM-as-Judge Can Fail

1. **Judge bias**: The judge LLM has its own biases and errors
2. **Self-preference**: If the same model generates and judges, it may favor its own style
3. **Prompt sensitivity**: Small prompt changes can shift scores significantly
4. **Cost**: Running a judge LLM on every eval example adds up
5. **Non-determinism**: Same input can produce different scores (temperature > 0)

---

## Implementation: Faithfulness

```python
from openai import OpenAI
from typing import List, Tuple
from dataclasses import dataclass

client = OpenAI()


@dataclass
class FaithfulnessResult:
    """Result of faithfulness evaluation."""
    score: float  # 0.0 to 1.0
    reasoning: str
    unsupported_claims: List[str]


def evaluate_faithfulness(
    query: str,
    context: str,
    answer: str,
    model: str = "gpt-4o-mini"
) -> FaithfulnessResult:
    """
    Evaluate if the answer is faithful to (supported by) the context.
    
    Args:
        query: The original question
        context: The retrieved context provided to the LLM
        answer: The generated answer to evaluate
        model: Judge model to use
    
    Returns:
        FaithfulnessResult with score, reasoning, and unsupported claims
    """
    prompt = f"""You are evaluating whether an answer is faithful to the provided context.

An answer is faithful if ALL claims in the answer are directly supported by the context.
An answer is NOT faithful if it contains information not present in the context, 
even if that information might be true.

Query: {query}

Context:
{context}

Answer to evaluate:
{answer}

Evaluate the faithfulness of the answer.

Respond in this exact format:
SCORE: [0.0 to 1.0, where 1.0 means fully faithful]
UNSUPPORTED_CLAIMS: [List any claims not supported by context, or "None"]
REASONING: [Brief explanation of your score]"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0  # Deterministic for evaluation
    )
    
    return _parse_faithfulness_response(response.choices[0].message.content)


def _parse_faithfulness_response(response: str) -> FaithfulnessResult:
    """Parse the judge LLM's response into structured result."""
    lines = response.strip().split("\n")
    
    score = 0.0
    reasoning = ""
    unsupported = []
    
    for line in lines:
        if line.startswith("SCORE:"):
            try:
                score = float(line.replace("SCORE:", "").strip())
                score = max(0.0, min(1.0, score))  # Clamp to [0, 1]
            except ValueError:
                score = 0.0
        elif line.startswith("UNSUPPORTED_CLAIMS:"):
            claims = line.replace("UNSUPPORTED_CLAIMS:", "").strip()
            if claims.lower() != "none":
                unsupported = [c.strip() for c in claims.split(",")]
        elif line.startswith("REASONING:"):
            reasoning = line.replace("REASONING:", "").strip()
    
    return FaithfulnessResult(
        score=score,
        reasoning=reasoning,
        unsupported_claims=unsupported
    )


# Example usage
context = """Our refund policy allows returns within 30 days of purchase. 
Items must be in original packaging. Refunds are processed within 5-7 business days."""

query = "What is the refund policy?"

# Faithful answer
answer_faithful = "You can return items within 30 days if they're in original packaging. Refunds take 5-7 business days."

# Unfaithful answer (adds unsupported claim)
answer_unfaithful = "You can return items within 30 days. We also offer free return shipping labels."

result = evaluate_faithfulness(query, context, answer_faithful)
print(f"Faithful answer score: {result.score}")
print(f"Reasoning: {result.reasoning}")

result = evaluate_faithfulness(query, context, answer_unfaithful)
print(f"\nUnfaithful answer score: {result.score}")
print(f"Unsupported claims: {result.unsupported_claims}")
```

---

## Implementation: Answer Relevance

```python
@dataclass
class AnswerRelevanceResult:
    """Result of answer relevance evaluation."""
    score: float
    reasoning: str
    missing_aspects: List[str]


def evaluate_answer_relevance(
    query: str,
    answer: str,
    model: str = "gpt-4o-mini"
) -> AnswerRelevanceResult:
    """
    Evaluate if the answer addresses the question asked.
    
    Note: This doesn't need context — it's purely about 
    whether the answer matches the question's intent.
    
    Args:
        query: The original question
        answer: The generated answer to evaluate
        model: Judge model to use
    
    Returns:
        AnswerRelevanceResult with score and reasoning
    """
    prompt = f"""You are evaluating whether an answer is relevant to the question asked.

A relevant answer directly addresses what the user is asking for.
An irrelevant answer might discuss related topics but miss the actual question.

Question: {query}

Answer to evaluate:
{answer}

Evaluate the relevance of the answer to the question.

Respond in this exact format:
SCORE: [0.0 to 1.0, where 1.0 means fully addresses the question]
MISSING_ASPECTS: [What parts of the question weren't addressed, or "None"]
REASONING: [Brief explanation of your score]"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    return _parse_relevance_response(response.choices[0].message.content)


def _parse_relevance_response(response: str) -> AnswerRelevanceResult:
    """Parse the judge LLM's response."""
    lines = response.strip().split("\n")
    
    score = 0.0
    reasoning = ""
    missing = []
    
    for line in lines:
        if line.startswith("SCORE:"):
            try:
                score = float(line.replace("SCORE:", "").strip())
                score = max(0.0, min(1.0, score))
            except ValueError:
                score = 0.0
        elif line.startswith("MISSING_ASPECTS:"):
            aspects = line.replace("MISSING_ASPECTS:", "").strip()
            if aspects.lower() != "none":
                missing = [a.strip() for a in aspects.split(",")]
        elif line.startswith("REASONING:"):
            reasoning = line.replace("REASONING:", "").strip()
    
    return AnswerRelevanceResult(
        score=score,
        reasoning=reasoning,
        missing_aspects=missing
    )


# Example
query = "How do I reset my password?"

# Relevant answer
answer_relevant = "Go to Settings > Security > Reset Password. Click the reset link and follow the prompts."

# Irrelevant answer (topically related but doesn't answer)
answer_irrelevant = "Password security is crucial in today's digital landscape. We use AES-256 encryption to protect your credentials."

result = evaluate_answer_relevance(query, answer_relevant)
print(f"Relevant answer score: {result.score}")

result = evaluate_answer_relevance(query, answer_irrelevant)
print(f"Irrelevant answer score: {result.score}")
print(f"Missing: {result.missing_aspects}")
```

---

## Implementation: Context Relevance

```python
@dataclass
class ContextRelevanceResult:
    """Result of context relevance evaluation."""
    score: float
    reasoning: str
    relevant_portions: str
    irrelevant_portions: str


def evaluate_context_relevance(
    query: str,
    context: str,
    model: str = "gpt-4o-mini"
) -> ContextRelevanceResult:
    """
    Evaluate if the retrieved context is relevant to the query.
    
    This helps identify retrieval failures that weren't caught
    by embedding similarity.
    
    Args:
        query: The original question
        context: The retrieved context to evaluate
        model: Judge model to use
    
    Returns:
        ContextRelevanceResult with score and analysis
    """
    prompt = f"""You are evaluating whether retrieved context is relevant to a user's question.

Relevant context contains information that helps answer the question.
Irrelevant context might share keywords but doesn't help answer the question.

Question: {query}

Retrieved Context:
{context}

Evaluate how relevant this context is for answering the question.

Respond in this exact format:
SCORE: [0.0 to 1.0, where 1.0 means fully relevant to the question]
RELEVANT_PORTIONS: [Summarize parts that help answer the question, or "None"]
IRRELEVANT_PORTIONS: [Summarize parts that don't help, or "None"]
REASONING: [Brief explanation of your score]"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    return _parse_context_relevance_response(response.choices[0].message.content)


def _parse_context_relevance_response(response: str) -> ContextRelevanceResult:
    """Parse the judge LLM's response."""
    lines = response.strip().split("\n")
    
    score = 0.0
    reasoning = ""
    relevant = ""
    irrelevant = ""
    
    for line in lines:
        if line.startswith("SCORE:"):
            try:
                score = float(line.replace("SCORE:", "").strip())
                score = max(0.0, min(1.0, score))
            except ValueError:
                score = 0.0
        elif line.startswith("RELEVANT_PORTIONS:"):
            relevant = line.replace("RELEVANT_PORTIONS:", "").strip()
        elif line.startswith("IRRELEVANT_PORTIONS:"):
            irrelevant = line.replace("IRRELEVANT_PORTIONS:", "").strip()
        elif line.startswith("REASONING:"):
            reasoning = line.replace("REASONING:", "").strip()
    
    return ContextRelevanceResult(
        score=score,
        reasoning=reasoning,
        relevant_portions=relevant,
        irrelevant_portions=irrelevant
    )
```

---

## Implementation: Correctness

```python
@dataclass
class CorrectnessResult:
    """Result of correctness evaluation."""
    score: float
    reasoning: str
    errors: List[str]


def evaluate_correctness(
    query: str,
    answer: str,
    ground_truth: str,
    model: str = "gpt-4o-mini"
) -> CorrectnessResult:
    """
    Evaluate if the answer is factually correct compared to ground truth.
    
    This requires a known correct answer for comparison.
    
    Args:
        query: The original question
        answer: The generated answer to evaluate
        ground_truth: The known correct answer
        model: Judge model to use
    
    Returns:
        CorrectnessResult with score and identified errors
    """
    prompt = f"""You are evaluating whether an answer is factually correct.

Compare the generated answer against the known correct answer.
The generated answer doesn't need to be word-for-word identical,
but it must convey the same correct information.

Question: {query}

Known Correct Answer:
{ground_truth}

Generated Answer to Evaluate:
{answer}

Evaluate the correctness of the generated answer.

Respond in this exact format:
SCORE: [0.0 to 1.0, where 1.0 means fully correct]
ERRORS: [List any factual errors in the generated answer, or "None"]
REASONING: [Brief explanation of your score]"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    return _parse_correctness_response(response.choices[0].message.content)


def _parse_correctness_response(response: str) -> CorrectnessResult:
    """Parse the judge LLM's response."""
    lines = response.strip().split("\n")
    
    score = 0.0
    reasoning = ""
    errors = []
    
    for line in lines:
        if line.startswith("SCORE:"):
            try:
                score = float(line.replace("SCORE:", "").strip())
                score = max(0.0, min(1.0, score))
            except ValueError:
                score = 0.0
        elif line.startswith("ERRORS:"):
            error_text = line.replace("ERRORS:", "").strip()
            if error_text.lower() != "none":
                errors = [e.strip() for e in error_text.split(",")]
        elif line.startswith("REASONING:"):
            reasoning = line.replace("REASONING:", "").strip()
    
    return CorrectnessResult(
        score=score,
        reasoning=reasoning,
        errors=errors
    )
```

---

## Complete RAG Evaluation Pipeline

Putting all metrics together:

```python
from dataclasses import dataclass
from typing import Optional
import statistics


@dataclass
class RAGEvaluationResult:
    """Complete evaluation of a single RAG response."""
    query: str
    context: str
    answer: str
    ground_truth: Optional[str]
    
    # Scores
    faithfulness: float
    answer_relevance: float
    context_relevance: float
    correctness: Optional[float]  # None if no ground truth
    
    # Aggregate
    overall_score: float
    
    # Diagnostics
    faithfulness_details: FaithfulnessResult
    answer_relevance_details: AnswerRelevanceResult
    context_relevance_details: ContextRelevanceResult
    correctness_details: Optional[CorrectnessResult]


def evaluate_rag_response(
    query: str,
    context: str,
    answer: str,
    ground_truth: Optional[str] = None,
    model: str = "gpt-4o-mini"
) -> RAGEvaluationResult:
    """
    Run complete evaluation on a RAG response.
    
    Args:
        query: The original question
        context: The retrieved context
        answer: The generated answer
        ground_truth: Optional known correct answer
        model: Judge model to use
    
    Returns:
        RAGEvaluationResult with all metrics
    """
    # Run all evaluations
    faithfulness_result = evaluate_faithfulness(query, context, answer, model)
    relevance_result = evaluate_answer_relevance(query, answer, model)
    context_result = evaluate_context_relevance(query, context, model)
    
    correctness_result = None
    if ground_truth:
        correctness_result = evaluate_correctness(query, answer, ground_truth, model)
    
    # Compute overall score (simple average, could be weighted)
    scores = [
        faithfulness_result.score,
        relevance_result.score,
        context_result.score
    ]
    if correctness_result:
        scores.append(correctness_result.score)
    
    overall = statistics.mean(scores)
    
    return RAGEvaluationResult(
        query=query,
        context=context,
        answer=answer,
        ground_truth=ground_truth,
        faithfulness=faithfulness_result.score,
        answer_relevance=relevance_result.score,
        context_relevance=context_result.score,
        correctness=correctness_result.score if correctness_result else None,
        overall_score=overall,
        faithfulness_details=faithfulness_result,
        answer_relevance_details=relevance_result,
        context_relevance_details=context_result,
        correctness_details=correctness_result
    )


def evaluate_rag_dataset(
    eval_data: list[dict],
    model: str = "gpt-4o-mini"
) -> dict:
    """
    Evaluate a complete RAG eval dataset.
    
    Args:
        eval_data: List of dicts with query, context, answer, [ground_truth]
        model: Judge model to use
    
    Returns:
        Aggregate metrics and per-query results
    """
    results = []
    
    for item in eval_data:
        result = evaluate_rag_response(
            query=item["query"],
            context=item["context"],
            answer=item["answer"],
            ground_truth=item.get("ground_truth"),
            model=model
        )
        results.append(result)
    
    # Aggregate
    return {
        "mean_faithfulness": statistics.mean(r.faithfulness for r in results),
        "mean_answer_relevance": statistics.mean(r.answer_relevance for r in results),
        "mean_context_relevance": statistics.mean(r.context_relevance for r in results),
        "mean_correctness": statistics.mean(
            r.correctness for r in results if r.correctness is not None
        ) if any(r.correctness is not None for r in results) else None,
        "mean_overall": statistics.mean(r.overall_score for r in results),
        "per_query": results,
        "total_queries": len(results)
    }


# Example usage
eval_data = [
    {
        "query": "What is the refund policy?",
        "context": "Our refund policy allows returns within 30 days of purchase.",
        "answer": "You can return items within 30 days of purchase.",
        "ground_truth": "30-day return policy"
    },
    {
        "query": "How do I contact support?",
        "context": "For support, email help@company.com or call 1-800-HELP.",
        "answer": "You can reach support at help@company.com or 1-800-HELP.",
        "ground_truth": "Email help@company.com or call 1-800-HELP"
    }
]

results = evaluate_rag_dataset(eval_data)

print(f"Mean Faithfulness:      {results['mean_faithfulness']:.3f}")
print(f"Mean Answer Relevance:  {results['mean_answer_relevance']:.3f}")
print(f"Mean Context Relevance: {results['mean_context_relevance']:.3f}")
print(f"Mean Correctness:       {results['mean_correctness']:.3f}")
print(f"Mean Overall:           {results['mean_overall']:.3f}")
```

---

## LLM-as-Judge: Best Practices

### 1. Use a Different (Often Stronger) Model

If your RAG uses GPT-4o-mini, judge with GPT-4o. Avoids self-preference bias.

```python
# RAG pipeline
rag_model = "gpt-4o-mini"

# Evaluation
judge_model = "gpt-4o"  # Stronger model for judging
```

### 2. Temperature = 0 for Consistency

Evaluation should be deterministic. Same input → same score.

```python
response = client.chat.completions.create(
    model=model,
    messages=messages,
    temperature=0  # Always 0 for evaluation
)
```

### 3. Structured Output Prompts

Ask for specific format to make parsing reliable:

```
Respond in this exact format:
SCORE: [0.0 to 1.0]
REASONING: [explanation]
```

Or use JSON mode / structured outputs if available.

### 4. Calibrate with Human Labels

Run your judge on examples where you know the correct score. If the judge scores a clearly unfaithful answer as 0.9, your prompt needs work.

```python
# Calibration set with known scores
calibration = [
    {"query": "...", "context": "...", "answer": "...", "expected_faithfulness": 1.0},
    {"query": "...", "context": "...", "answer": "...", "expected_faithfulness": 0.0},
    # ...
]

# Run judge, compare to expected
for item in calibration:
    result = evaluate_faithfulness(item["query"], item["context"], item["answer"])
    diff = abs(result.score - item["expected_faithfulness"])
    if diff > 0.2:
        print(f"Calibration issue: expected {item['expected_faithfulness']}, got {result.score}")
```

### 5. Include Reasoning in Output

Always ask for reasoning, not just a score. Helps debug when scores seem wrong.

---

## When LLM-as-Judge Fails

### 1. Sycophantic Scoring

The judge might be reluctant to give low scores, especially for plausible-sounding answers.

**Mitigation**: Include explicit examples of low-scoring answers in your prompt.

### 2. Length Bias

Longer answers often get higher scores (more "thorough"), even if they ramble.

**Mitigation**: Add "Brevity is acceptable. Score based on correctness and relevance, not length."

### 3. Style Over Substance

Judge may prefer certain phrasing styles regardless of correctness.

**Mitigation**: Use different judge models, compare scores, flag disagreements.

### 4. Context Window Limits

For long contexts, the judge may miss information or hallucinate.

**Mitigation**: Chunk evaluation if context is very long, or use models with larger context windows.

### 5. Domain-Specific Errors

Judge may not have domain expertise to correctly evaluate technical accuracy.

**Mitigation**: For specialized domains (legal, medical, code), human evaluation or specialized models may be necessary.

---

## RAGAS and Other Frameworks

Frameworks like RAGAS, TruLens, and DeepEval implement these patterns with additional sophistication:

**RAGAS** (RAG Assessment):

- Implements faithfulness, answer relevancy, context precision/recall
- Uses clever decomposition (breaks answer into claims, verifies each)
- Provides aggregate scores and component breakdowns

**TruLens**:

- Focus on "feedback functions" for various quality dimensions
- Built-in tracing and visualization
- Supports custom evaluation functions

**DeepEval**:

- Unit testing approach (pytest integration)
- CI/CD friendly
- Multiple built-in metrics

These frameworks save you from writing the parsing and aggregation code, but understand that underneath they're doing exactly what we've implemented: sending prompts to a judge LLM and parsing scores.

```python
# Example: RAGAS usage (conceptual)
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision

result = evaluate(
    dataset,  # Your eval dataset
    metrics=[faithfulness, answer_relevancy, context_precision]
)

print(result)  # Scores per metric
```

---

## Cost Considerations

LLM-as-Judge has real cost implications:

|Metric|LLM Calls per Query|Typical Tokens|
|---|---|---|
|Faithfulness|1|~500-1000|
|Answer Relevance|1|~300-500|
|Context Relevance|1|~500-1000|
|Correctness|1|~300-500|
|**Total**|**4**|**~1600-3000**|

For 100-query eval set:

- ~400 LLM calls
- ~200K tokens
- With GPT-4o-mini: ~$0.06 input + $0.24 output ≈ $0.30 per eval run
- With GPT-4o: ~$1.00 input + $4.00 output ≈ $5.00 per eval run

Not prohibitive, but scales with eval set size and frequency.

>**Note:** 
>The cost calculation above assumes one LLM call per metric (4 calls total) — shown separately in this note for conceptual clarity. Production pipelines combine all metrics into a single prompt, returning all scores in one call. This reduces cost and latency by ~4x. The numbers above represent worst-case; real implementations are significantly cheaper.

---

## Key Takeaways

1. **Four generation metrics**: Faithfulness (grounded in context?), Answer Relevance (addresses question?), Context Relevance (context helps?), Correctness (factually right?).
    
2. **LLM-as-Judge is the pattern**: Can't compute these with formulas. Use an LLM to evaluate the output.
    
3. **Different failures point to different problems**: Use the diagnostic matrix to identify whether the issue is retrieval, generation, or both.
    
4. **Judge with a different/stronger model**: Avoid self-preference bias. If RAG uses GPT-4o-mini, judge with GPT-4o.
    
5. **Temperature = 0 for evaluation**: Reproducible scores matter.
    
6. **Calibrate your judge**: Test on examples with known scores before trusting it on real data.
    
7. **Frameworks like RAGAS implement this**: But understand what's underneath — it's LLM calls with specific prompts.
    
8. **Correctness requires ground truth**: The most expensive metric to annotate, but the most definitive.