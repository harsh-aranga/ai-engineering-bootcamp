# Note 3: Mitigation Strategies — Constraining Generation and Retrieval Anchoring

## Mitigation Philosophy

Detection catches hallucinations after they happen. Mitigation prevents them from happening in the first place.

```
PREVENTION (Best)
  │
  ├─→ Prompt constraints
  ├─→ Retrieval anchoring  
  ├─→ Generation parameters
  │
  ↓
DETECTION (Second line)
  │
  ├─→ Faithfulness checking
  ├─→ Claim verification
  │
  ↓
RECOVERY (Last resort)
  │
  ├─→ Regeneration
  ├─→ Abstention
  └─→ Human escalation
```

The goal: make hallucination **structurally harder**, not just catch it afterward. Every mitigation technique adds friction to the hallucination path while keeping the faithful path smooth.

---

## Technique 1: Prompt-Based Constraints

The simplest and often most effective mitigation: tell the model explicitly what you want and don't want.

### Explicit Grounding Instructions

**Weak prompt (invites hallucination):**

```
Answer the user's question using the context provided.
```

**Strong prompt (constrains to context):**

```
Answer the user's question based ONLY on the provided context.

RULES:
1. Use ONLY information explicitly stated in the context
2. Do NOT add information from your general knowledge
3. Do NOT infer or extrapolate beyond what the context says
4. If the context doesn't contain the answer, say so clearly
```

The difference matters because LLMs are trained to be helpful. Without explicit constraints, they'll blend context with parametric knowledge to give a "better" answer — which is exactly how extrinsic hallucination happens.

### "I Don't Know" Training

Models resist saying "I don't know" because their training optimizes for helpfulness. You must explicitly teach abstention:

```python
GROUNDED_SYSTEM_PROMPT = """You are a research assistant that answers questions based ONLY on the provided context.

CRITICAL RULES:
1. Use ONLY information from the provided context
2. If the context doesn't contain the answer, respond with:
   "I don't have information about this in the available documents."
3. If you're unsure whether something is in the context, say:
   "I'm not certain this is fully supported by the documents."
4. Do NOT use your general knowledge to fill gaps
5. Partial information is okay — answer what you can, flag what you can't

GOOD RESPONSES:
- "According to the documents, the refund period is 30 days."
- "The documents mention refunds but don't specify the time period."
- "I don't have information about shipping policies in these documents."

BAD RESPONSES:
- Providing specific details not in the context
- Making reasonable assumptions without flagging them
- Saying "I don't know" to something that IS in the context
"""
```

### Quote-Forcing

Require the model to include direct quotes from the context. This makes hallucination harder because inventing exact quotes is more difficult than inventing paraphrased claims:

```python
QUOTE_FORCING_PROMPT = """Answer the question using ONLY the provided context.

FORMAT REQUIREMENTS:
1. Include at least one direct quote from the context
2. Use quotation marks for exact quotes
3. After each quote, cite which paragraph it came from

Example format:
The refund policy states: "Returns are accepted within 30 days" (Paragraph 2).
This means you have approximately one month to return items.

If you cannot find a relevant quote, say: "I cannot find specific information about this in the provided documents."
"""
```

Quote-forcing has a side benefit: it makes verification easier. You can check if the quoted text actually appears in the context.

### Instruction Hierarchy

When you have multiple instruction sources, establish clear precedence:

```
PRIORITY ORDER:
1. System prompt safety rules (never violate)
2. Grounding constraints (only use context)
3. Context content (the retrieved documents)
4. User's specific question
```

Implementation:

```python
def build_rag_prompt(
    system_rules: str,
    grounding_instructions: str,
    context: str,
    query: str
) -> list[dict]:
    """
    Build prompt with clear instruction hierarchy.
    """
    return [
        {
            "role": "system",
            "content": f"""SYSTEM RULES (Highest Priority):
{system_rules}

GROUNDING INSTRUCTIONS (Must Follow):
{grounding_instructions}"""
        },
        {
            "role": "user",
            "content": f"""CONTEXT (Your Only Information Source):
{context}

---

USER QUESTION:
{query}

Remember: Answer based ONLY on the context above."""
        }
    ]
```

---

## Technique 2: Retrieval Anchoring

The quality of retrieved context directly impacts hallucination risk. Better retrieval = better grounding = less hallucination.

### More Chunks = More Grounding (With Trade-offs)

```
Few chunks (k=3):
  + Less noise
  + Cheaper
  - Might miss relevant info → model fills gaps with hallucination

Many chunks (k=10):
  + More complete information
  + Harder for model to claim "not in context"
  - More noise / irrelevant content
  - Higher token cost
  - Model might get confused by contradictions
```

**Finding the right k:**

```python
def adaptive_retrieval(
    query: str,
    retriever,
    min_chunks: int = 3,
    max_chunks: int = 10,
    relevance_threshold: float = 0.7
) -> list[dict]:
    """
    Retrieve more chunks if initial results aren't highly relevant.
    """
    # Start with more chunks, filter by relevance
    candidates = retriever.retrieve(query, k=max_chunks)
    
    # Keep chunks above relevance threshold
    relevant = [c for c in candidates if c["score"] >= relevance_threshold]
    
    # Ensure minimum
    if len(relevant) < min_chunks:
        relevant = candidates[:min_chunks]
    
    return relevant
```

### Higher Relevance Threshold

Low relevance chunks are dangerous — they occupy context space without helping, and the model might try to use them anyway:

```python
def filtered_retrieval(
    query: str,
    retriever,
    k: int = 5,
    relevance_threshold: float = 0.6
) -> tuple[list[dict], bool]:
    """
    Filter by relevance, flag if we're working with weak retrieval.
    
    Returns:
        (chunks, has_strong_context)
    """
    chunks = retriever.retrieve(query, k=k)
    
    # Calculate relevance distribution
    scores = [c["score"] for c in chunks]
    top_score = max(scores) if scores else 0
    avg_score = sum(scores) / len(scores) if scores else 0
    
    # Filter to relevant chunks
    relevant = [c for c in chunks if c["score"] >= relevance_threshold]
    
    # Determine if we have strong context
    has_strong_context = (
        len(relevant) >= 2 and
        top_score >= 0.75 and
        avg_score >= relevance_threshold
    )
    
    return relevant, has_strong_context
```

### Chunk Metadata for Accountability

Include source information in the prompt so the model (and you) can trace claims:

```python
def format_chunks_with_metadata(chunks: list[dict]) -> str:
    """
    Format chunks with source metadata for traceability.
    """
    formatted = []
    
    for i, chunk in enumerate(chunks):
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", "Unknown")
        date = metadata.get("date", "Unknown date")
        section = metadata.get("section", "")
        
        header = f"[Source {i+1}: {source}"
        if section:
            header += f", Section: {section}"
        header += f", Date: {date}]"
        
        formatted.append(f"{header}\n{chunk['text']}")
    
    return "\n\n---\n\n".join(formatted)


# Example output in prompt:
"""
[Source 1: company_handbook.pdf, Section: HR Policies, Date: 2024-01-15]
Employees are entitled to 20 days of paid time off per year...

---

[Source 2: benefits_guide.pdf, Section: Leave Policies, Date: 2024-03-01]
PTO requests must be submitted at least 2 weeks in advance...
"""
```

This metadata serves multiple purposes:

- Model can cite sources accurately
- You can verify citations
- Dates help identify stale information
- Sections help with granular verification

### Retrieval Confidence as Generation Gate

Don't generate if retrieval failed:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class RetrievalResult:
    chunks: list[dict]
    query: str
    confidence: float  # 0.0–1.0
    should_proceed: bool
    abstention_reason: Optional[str]

def assess_retrieval_quality(
    query: str,
    chunks: list[dict],
    min_chunks: int = 2,
    min_top_score: float = 0.6,
    min_avg_score: float = 0.5
) -> RetrievalResult:
    """
    Assess if retrieval is good enough to proceed with generation.
    """
    if not chunks:
        return RetrievalResult(
            chunks=[],
            query=query,
            confidence=0.0,
            should_proceed=False,
            abstention_reason="No relevant documents found"
        )
    
    scores = [c["score"] for c in chunks]
    top_score = max(scores)
    avg_score = sum(scores) / len(scores)
    
    # Check minimum requirements
    if len(chunks) < min_chunks:
        return RetrievalResult(
            chunks=chunks,
            query=query,
            confidence=0.2,
            should_proceed=False,
            abstention_reason=f"Only found {len(chunks)} relevant documents"
        )
    
    if top_score < min_top_score:
        return RetrievalResult(
            chunks=chunks,
            query=query,
            confidence=0.3,
            should_proceed=False,
            abstention_reason="Retrieved documents have low relevance to your question"
        )
    
    # Calculate overall confidence
    confidence = (top_score + avg_score) / 2
    
    return RetrievalResult(
        chunks=chunks,
        query=query,
        confidence=confidence,
        should_proceed=True,
        abstention_reason=None
    )
```

---

## Technique 3: Generation-Time Constraints

Control how the model generates, not just what you tell it.

### Temperature Control

Lower temperature = more deterministic = less creative deviation = less hallucination.

**Doc reference:** OpenAI API documentation confirms temperature range 0–2, with lower values producing more focused output.

```python
from openai import OpenAI

client = OpenAI()

def generate_grounded_response(
    query: str,
    context: str,
    temperature: float = 0.3  # Low for factual tasks
) -> str:
    """
    Generate with low temperature for factual grounding.
    
    Temperature guidance:
    - 0.0–0.3: Factual, deterministic (RAG, Q&A)
    - 0.4–0.7: Balanced (general conversation)
    - 0.8–1.2: Creative (brainstorming, writing)
    - >1.2: High variance, risk of incoherence
    """
    response = client.responses.create(
        model="gpt-4.1",
        input=f"""Context: {context}

Question: {query}

Answer based ONLY on the context:""",
        temperature=temperature
    )
    
    return response.output_text
```

**Important caveat:** Some newer reasoning models (GPT-5 series) don't support temperature as a parameter — they manage it internally. Check model documentation.

### Anthropic Example

**Doc reference:** Anthropic Messages API (https://docs.anthropic.com/en/api/messages)

```python
from anthropic import Anthropic

client = Anthropic()

def generate_grounded_response_anthropic(
    query: str,
    context: str,
    temperature: float = 0.3
) -> str:
    """
    Generate with low temperature using Claude.
    """
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=temperature,
        system="You are a research assistant. Answer ONLY based on the provided context. If the context doesn't contain the answer, say so.",
        messages=[{
            "role": "user",
            "content": f"""Context:
{context}

Question: {query}"""
        }]
    )
    
    return message.content[0].text
```

### Shorter max_tokens = Less Drift

Longer responses have more opportunity to drift from source material:

```python
def generate_with_length_control(
    query: str,
    context: str,
    max_tokens: int = 300  # Constrain length
) -> str:
    """
    Shorter responses = less room to hallucinate.
    
    Guidance:
    - Simple factual Q&A: 100–200 tokens
    - Explanatory answers: 200–400 tokens
    - Detailed analysis: 400–800 tokens
    
    Beyond 800 tokens, hallucination risk increases significantly.
    """
    response = client.responses.create(
        model="gpt-4.1",
        input=f"""Context: {context}

Question: {query}

Provide a concise, focused answer based ONLY on the context.""",
        max_tokens=max_tokens,
        temperature=0.3
    )
    
    return response.output_text
```

### Combined Generation Parameters

```python
@dataclass
class GenerationConfig:
    """Configuration for hallucination-resistant generation."""
    temperature: float = 0.3
    max_tokens: int = 500
    model: str = "gpt-4.1"
    
    # Thresholds for proceeding
    min_retrieval_confidence: float = 0.6
    min_faithfulness_score: float = 0.7

def safe_generate(
    query: str,
    context: str,
    config: GenerationConfig
) -> dict:
    """Generate with all hallucination-resistant parameters."""
    
    response = client.responses.create(
        model=config.model,
        input=f"""You are a research assistant. Answer ONLY based on the provided context.
If the context doesn't contain the answer, say: "I don't have information about this."

Context:
{context}

Question: {query}""",
        temperature=config.temperature,
        max_tokens=config.max_tokens
    )
    
    return {
        "answer": response.output_text,
        "config": config
    }
```

---

## Technique 4: Abstention Design

When to refuse to answer, and how to do it helpfully.

### When to Abstain

```python
@dataclass
class AbstentionDecision:
    should_abstain: bool
    reason: str
    confidence: float
    partial_answer: Optional[str] = None

def decide_abstention(
    retrieval_confidence: float,
    faithfulness_score: float,
    context_coverage: float,  # How much of the query is addressed
    thresholds: dict
) -> AbstentionDecision:
    """
    Decide whether to abstain based on multiple signals.
    """
    # Hard abstention: retrieval failed
    if retrieval_confidence < thresholds.get("min_retrieval", 0.4):
        return AbstentionDecision(
            should_abstain=True,
            reason="no_relevant_context",
            confidence=retrieval_confidence
        )
    
    # Hard abstention: answer not grounded
    if faithfulness_score < thresholds.get("min_faithfulness", 0.5):
        return AbstentionDecision(
            should_abstain=True,
            reason="answer_not_grounded",
            confidence=faithfulness_score
        )
    
    # Soft abstention: partial coverage
    if context_coverage < thresholds.get("min_coverage", 0.7):
        return AbstentionDecision(
            should_abstain=False,  # Don't fully abstain
            reason="partial_coverage",
            confidence=context_coverage,
            partial_answer="can_answer_partially"
        )
    
    # No abstention needed
    return AbstentionDecision(
        should_abstain=False,
        reason="sufficient_grounding",
        confidence=min(retrieval_confidence, faithfulness_score)
    )
```

### How to Abstain Helpfully

Bad abstention:

```
"I don't know."
```

Good abstention:

```
"I don't have information about shipping times in the available documents. 
The documents I have access to cover return policies and refund procedures. 
Would you like to know about those instead, or should I search for 
shipping-related documents?"
```

```python
def generate_helpful_abstention(
    query: str,
    available_topics: list[str],
    abstention_reason: str
) -> str:
    """
    Generate a helpful abstention message.
    """
    reason_messages = {
        "no_relevant_context": (
            f"I couldn't find documents relevant to your question about "
            f"this topic in the available materials."
        ),
        "answer_not_grounded": (
            f"I found some related information, but I'm not confident "
            f"I can give you an accurate answer based on the documents."
        ),
        "partial_coverage": (
            f"The documents partially address your question, but some "
            f"aspects aren't covered."
        )
    }
    
    base_message = reason_messages.get(
        abstention_reason,
        "I don't have enough information to answer accurately."
    )
    
    # Add context about what IS available
    if available_topics:
        topics_str = ", ".join(available_topics[:5])
        base_message += f"\n\nThe documents I have access to cover: {topics_str}."
    
    # Offer alternatives
    base_message += "\n\nWould you like me to search for additional documents, or can I help with something else?"
    
    return base_message
```

### Partial Abstention

Answer what you can, flag what you can't:

```python
def generate_partial_answer(
    query: str,
    context: str,
    answerable_aspects: list[str],
    unanswerable_aspects: list[str]
) -> str:
    """
    Generate answer for what's covered, abstain on what's not.
    """
    prompt = f"""Based on the context below, answer the question.

IMPORTANT:
- Answer the aspects that ARE covered in the context
- For aspects NOT covered, explicitly say "This information is not in the available documents"
- Do NOT guess or fill in gaps

Aspects covered in context: {', '.join(answerable_aspects)}
Aspects NOT covered: {', '.join(unanswerable_aspects)}

Context:
{context}

Question: {query}

Answer (addressing covered aspects, noting gaps):"""
    
    response = client.responses.create(
        model="gpt-4.1",
        input=prompt,
        temperature=0.3
    )
    
    return response.output_text


# Example output:
"""
Based on the available documents:

**Refund period:** You have 30 days from purchase to request a refund.

**Required condition:** Items must be in original packaging.

**Processing time:** This information is not in the available documents. 
I'd recommend contacting customer service for current processing times.
"""
```

---

## Technique 5: Multi-Step Verification Flow

Generate, verify, and regenerate if needed.

### Basic Generate-Verify-Regenerate

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class VerifiedResponse:
    answer: str
    faithfulness_score: float
    attempts: int
    final_status: str  # "verified", "regenerated", "abstained"
    issues_found: list[str]

class VerifiedGenerator:
    """
    Generate with verification loop.
    """
    
    def __init__(
        self,
        model: str = "gpt-4.1",
        max_attempts: int = 2,
        faithfulness_threshold: float = 0.75
    ):
        self.client = OpenAI()
        self.model = model
        self.max_attempts = max_attempts
        self.threshold = faithfulness_threshold
    
    def generate(
        self,
        query: str,
        context: str
    ) -> VerifiedResponse:
        """
        Generate → Verify → Regenerate if needed → Abstain if still failing.
        """
        all_issues = []
        
        for attempt in range(self.max_attempts):
            # Generate
            answer = self._generate(query, context, attempt)
            
            # Verify
            verification = self._verify(query, context, answer)
            
            if verification["score"] >= self.threshold:
                return VerifiedResponse(
                    answer=answer,
                    faithfulness_score=verification["score"],
                    attempts=attempt + 1,
                    final_status="verified" if attempt == 0 else "regenerated",
                    issues_found=all_issues
                )
            
            # Track issues for next attempt
            all_issues.extend(verification.get("issues", []))
        
        # All attempts failed — abstain
        return VerifiedResponse(
            answer=self._generate_abstention(query, all_issues),
            faithfulness_score=verification["score"],
            attempts=self.max_attempts,
            final_status="abstained",
            issues_found=all_issues
        )
    
    def _generate(
        self,
        query: str,
        context: str,
        attempt: int
    ) -> str:
        """Generate answer, with stricter prompt on retry."""
        
        if attempt == 0:
            instruction = "Answer based ONLY on the provided context."
        else:
            instruction = """Answer based ONLY on the provided context.
            
STRICT RULES (previous attempt had issues):
- Quote directly from the context when possible
- Do NOT add any information not explicitly stated
- If unsure, say "I'm not certain" rather than guessing
- Shorter, more focused answers are better"""
        
        response = self.client.responses.create(
            model=self.model,
            input=f"""{instruction}

Context:
{context}

Question: {query}""",
            temperature=0.2 if attempt == 0 else 0.1  # Lower temp on retry
        )
        
        return response.output_text
    
    def _verify(
        self,
        query: str,
        context: str,
        answer: str
    ) -> dict:
        """Verify faithfulness."""
        prompt = f"""Evaluate if this answer is fully supported by the context.

Context:
{context}

Question: {query}

Answer: {answer}

Respond in JSON:
{{
    "score": <0.0-1.0>,
    "issues": [<list of unsupported claims>]
}}"""
        
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0
        )
        
        import json
        try:
            text = response.output_text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            return json.loads(text.strip())
        except:
            return {"score": 0.0, "issues": ["Failed to parse verification"]}
    
    def _generate_abstention(
        self,
        query: str,
        issues: list[str]
    ) -> str:
        """Generate helpful abstention message."""
        return (
            f"I wasn't able to provide a fully accurate answer to your question. "
            f"The available documents don't seem to contain complete information "
            f"about this topic. Could you rephrase your question or ask about "
            f"a related topic?"
        )


# Usage
generator = VerifiedGenerator(
    max_attempts=2,
    faithfulness_threshold=0.75
)

result = generator.generate(query, context)
print(f"Status: {result.final_status}")
print(f"Attempts: {result.attempts}")
print(f"Score: {result.faithfulness_score:.2f}")
print(f"Answer: {result.answer}")
```

### Cost Consideration

Multi-step verification multiplies LLM calls:

```
Simple generation: 1 call
Generate + verify: 2 calls
Generate + verify + regenerate + verify: 4 calls
Generate + verify + regenerate + verify + abstain: 4 calls + abstention

Worst case: 2N + 1 calls (N = max_attempts)
```

**Cost optimization strategies:**

```python
class CostAwareVerifiedGenerator:
    """
    Only verify when needed, based on heuristics.
    """
    
    def should_verify(
        self,
        answer: str,
        context: str
    ) -> bool:
        """
        Quick heuristics to decide if full verification is needed.
        """
        # Heuristic 1: Answer much longer than context
        if len(answer) > len(context) * 0.5:
            return True  # Likely added information
        
        # Heuristic 2: Contains hedge words (model is uncertain)
        hedge_phrases = [
            "i think", "probably", "likely", "might be",
            "i believe", "it seems", "generally"
        ]
        if any(phrase in answer.lower() for phrase in hedge_phrases):
            return True
        
        # Heuristic 3: Contains specific numbers/dates not in context
        import re
        answer_numbers = set(re.findall(r'\d+', answer))
        context_numbers = set(re.findall(r'\d+', context))
        if answer_numbers - context_numbers:
            return True  # New numbers appeared
        
        return False  # Skip verification
    
    def generate(self, query: str, context: str) -> VerifiedResponse:
        answer = self._generate(query, context, attempt=0)
        
        if self.should_verify(answer, context):
            # Full verification path
            return self._verified_generate(query, context)
        else:
            # Skip verification
            return VerifiedResponse(
                answer=answer,
                faithfulness_score=0.9,  # Assumed high
                attempts=1,
                final_status="unverified",
                issues_found=[]
            )
```

---

## The Faithfulness-Helpfulness Trade-off

Every mitigation technique involves a trade-off:

```
STRICT GROUNDING                          LOOSE GROUNDING
      │                                         │
      ▼                                         ▼
More "I don't know"                    More answers given
Fewer hallucinations                   More hallucinations
Less helpful overall                   More helpful overall
Higher precision                       Higher recall
      │                                         │
      └──────────── Sweet Spot ─────────────────┘
```

### Finding Your Threshold

The right threshold depends on your use case:

|Use Case|Tolerance for Hallucination|Tolerance for "I Don't Know"|Recommended Threshold|
|---|---|---|---|
|Medical/Legal advice|Very Low|High|0.9+ faithfulness|
|Customer support|Low|Medium|0.75–0.85|
|Internal knowledge base|Medium|Low|0.65–0.75|
|Brainstorming assistant|High|Very Low|0.5–0.65|

### Measuring the Trade-off

```python
@dataclass
class TradeoffMetrics:
    """Metrics for faithfulness-helpfulness trade-off."""
    
    # Faithfulness metrics
    hallucination_rate: float  # % of answers with hallucinations
    avg_faithfulness_score: float
    
    # Helpfulness metrics
    abstention_rate: float  # % of queries that got "I don't know"
    answer_completeness: float  # % of query aspects addressed
    
    # Combined
    useful_accurate_rate: float  # % that are both helpful AND accurate

def evaluate_threshold(
    test_queries: list[dict],  # query, context, ground_truth
    generator,
    faithfulness_threshold: float
) -> TradeoffMetrics:
    """
    Evaluate a specific threshold on test data.
    """
    results = []
    
    for item in test_queries:
        result = generator.generate(
            item["query"],
            item["context"],
            threshold=faithfulness_threshold
        )
        
        # Check if abstained
        abstained = result.final_status == "abstained"
        
        # Check hallucination (if we have ground truth)
        has_hallucination = False
        if not abstained and "ground_truth" in item:
            has_hallucination = not answer_matches_ground_truth(
                result.answer,
                item["ground_truth"]
            )
        
        results.append({
            "abstained": abstained,
            "hallucinated": has_hallucination,
            "faithfulness": result.faithfulness_score
        })
    
    total = len(results)
    abstained_count = sum(1 for r in results if r["abstained"])
    answered = [r for r in results if not r["abstained"]]
    hallucinated_count = sum(1 for r in answered if r["hallucinated"])
    
    return TradeoffMetrics(
        hallucination_rate=hallucinated_count / len(answered) if answered else 0,
        avg_faithfulness_score=sum(r["faithfulness"] for r in results) / total,
        abstention_rate=abstained_count / total,
        answer_completeness=len(answered) / total,
        useful_accurate_rate=(len(answered) - hallucinated_count) / total
    )


# Sweep thresholds to find optimal
thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]
for t in thresholds:
    metrics = evaluate_threshold(test_data, generator, t)
    print(f"Threshold {t}:")
    print(f"  Hallucination rate: {metrics.hallucination_rate:.1%}")
    print(f"  Abstention rate: {metrics.abstention_rate:.1%}")
    print(f"  Useful+Accurate: {metrics.useful_accurate_rate:.1%}")
```

### Dynamic Thresholds

Different queries might warrant different thresholds:

```python
def get_dynamic_threshold(
    query: str,
    domain: str,
    user_context: dict
) -> float:
    """
    Adjust threshold based on query characteristics.
    """
    base_threshold = 0.75
    
    # Higher stakes = stricter threshold
    high_stakes_domains = ["medical", "legal", "financial", "compliance"]
    if domain in high_stakes_domains:
        base_threshold = 0.9
    
    # Explicit uncertainty in query = can be more lenient
    uncertainty_phrases = ["roughly", "approximately", "ballpark", "estimate"]
    if any(phrase in query.lower() for phrase in uncertainty_phrases):
        base_threshold -= 0.1
    
    # User preference for accuracy vs. coverage
    user_preference = user_context.get("accuracy_preference", "balanced")
    if user_preference == "strict":
        base_threshold += 0.1
    elif user_preference == "helpful":
        base_threshold -= 0.1
    
    return max(0.5, min(0.95, base_threshold))
```

---

## Key Takeaways

1. **Prevention beats detection**: Make hallucination structurally harder through prompt constraints, retrieval quality gates, and generation parameters.
    
2. **Explicit grounding instructions work**: "ONLY use the context" + "Say I don't know when unsure" dramatically reduces hallucination.
    
3. **Temperature matters**: Lower temperature (0.2–0.4) for factual tasks reduces creative drift.
    
4. **Gate on retrieval quality**: If retrieval failed, don't generate — abstain gracefully.
    
5. **Abstain helpfully**: "I don't know" is useless. "I don't have information about X, but I can help with Y" is useful.
    
6. **Multi-step verification adds confidence**: Generate → Verify → Regenerate costs more but catches issues before users see them.
    
7. **The trade-off is real**: Stricter grounding = fewer hallucinations but more "I don't know." Find the right threshold for your use case.
    

---

## What's Next

Note 4 covers putting it all together: building a complete HallucinationGuard that combines retrieval assessment, generation constraints, detection, and abstention into a single pipeline.