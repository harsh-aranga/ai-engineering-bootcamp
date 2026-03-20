# Note 2: Detection Techniques — Grounding, Self-Consistency, and Citation Verification

## Detection Approach Taxonomy

Before diving into specific techniques, understand the three fundamental detection paradigms:

|Approach|What It Compares|Requires Context?|Best For|
|---|---|---|---|
|**Reference-based**|Answer vs. provided context|Yes|RAG systems, grounded generation|
|**Reference-free**|Answer vs. itself (consistency)|No|Open-domain, no gold standard|
|**Hybrid**|Both signals combined|Optional|High-stakes applications|

```
REFERENCE-BASED:
   Context ────┐
               ├──→ Compare ──→ Faithfulness Score
   Answer ─────┘
   
   "Is this answer supported by the given context?"

REFERENCE-FREE:
   Answer₁ ────┐
   Answer₂ ────┼──→ Compare ──→ Consistency Score
   Answer₃ ────┘
   
   "Do multiple generations agree with each other?"

HYBRID:
   Context ─────────┐
   Answer ──────────┼──→ Weighted ──→ Combined Score
   Multiple Answers ┘      Fusion
   
   "Does the answer match context AND is it self-consistent?"
```

For RAG systems, **reference-based detection is primary** — you have retrieved context, so use it. Reference-free approaches become useful when you want an additional signal or when context relevance is uncertain.

---

## Technique 1: Faithfulness Checking (LLM-as-Judge)

The most common and effective approach: use another LLM to verify whether the answer is supported by the context.

### How It Works

```
Input: (Context, Question, Answer)
       ↓
   Judge LLM evaluates:
   "Is every claim in the answer supported by the context?"
       ↓
Output: Score (0.0–1.0) + Reasoning
```

### Implementation

**Doc reference:** OpenAI Responses API (https://platform.openai.com/docs/api-reference/responses), Anthropic Messages API (https://docs.anthropic.com/en/api/messages)

```python
# OpenAI Responses API implementation
from openai import OpenAI
from dataclasses import dataclass
from typing import Optional
import json

@dataclass
class FaithfulnessResult:
    score: float
    is_faithful: bool
    issues: list[str]
    reasoning: str

class FaithfulnessChecker:
    """
    LLM-as-Judge for verifying answer faithfulness to context.
    """
    
    def __init__(
        self,
        model: str = "gpt-4.1",
        threshold: float = 0.7
    ):
        self.client = OpenAI()
        self.model = model
        self.threshold = threshold
    
    def check(
        self,
        query: str,
        context: str,
        answer: str
    ) -> FaithfulnessResult:
        """
        Check if answer is faithful to context.
        
        Returns FaithfulnessResult with score, issues, and reasoning.
        """
        prompt = f"""You are a factual accuracy checker. Evaluate whether the answer is fully supported by the given context.

CONTEXT:
{context}

QUESTION: {query}

ANSWER: {answer}

EVALUATION CRITERIA:
1. Every claim in the answer must be supported by the context
2. The answer must not add information beyond what's in the context
3. The answer must not contradict the context
4. If the answer says "I don't know" when context lacks info, that's GOOD

Respond in JSON format:
{{
    "score": <0.0 to 1.0, where 1.0 = fully supported>,
    "issues": [<list of unsupported or contradicted claims, or empty list>],
    "reasoning": "<brief explanation of your evaluation>"
}}"""

        response = self.client.responses.create(
            model=self.model,
            input=prompt
        )
        
        return self._parse_response(response.output_text)
    
    def _parse_response(self, text: str) -> FaithfulnessResult:
        """Parse JSON response from judge."""
        try:
            # Handle potential markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            data = json.loads(text.strip())
            score = float(data.get("score", 0.0))
            
            return FaithfulnessResult(
                score=score,
                is_faithful=score >= self.threshold,
                issues=data.get("issues", []),
                reasoning=data.get("reasoning", "")
            )
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback for malformed response
            return FaithfulnessResult(
                score=0.0,
                is_faithful=False,
                issues=["Failed to parse judge response"],
                reasoning=f"Parse error: {str(e)}"
            )


# Usage
checker = FaithfulnessChecker(threshold=0.75)

context = """
Our refund policy allows returns within 30 days of purchase.
Items must be in original packaging. Refunds are processed
to the original payment method.
"""

query = "What's your refund policy?"

# Test case 1: Faithful answer
answer_good = "You can return items within 30 days if they're in original packaging. Refunds go to your original payment method."

result = checker.check(query, context, answer_good)
print(f"Score: {result.score}, Faithful: {result.is_faithful}")
# Expected: High score, is_faithful=True

# Test case 2: Hallucinated answer
answer_bad = "You can return items within 30 days. Processing takes 3-5 business days and you'll receive store credit."

result = checker.check(query, context, answer_bad)
print(f"Score: {result.score}, Faithful: {result.is_faithful}")
print(f"Issues: {result.issues}")
# Expected: Lower score, issues include the invented claims
```

**Anthropic equivalent:**

```python
# Anthropic Messages API implementation
from anthropic import Anthropic

class FaithfulnessCheckerAnthropic:
    """
    LLM-as-Judge using Claude for faithfulness checking.
    """
    
    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        threshold: float = 0.7
    ):
        self.client = Anthropic()
        self.model = model
        self.threshold = threshold
    
    def check(
        self,
        query: str,
        context: str,
        answer: str
    ) -> FaithfulnessResult:
        """Check answer faithfulness using Claude."""
        
        prompt = f"""You are a factual accuracy checker. Evaluate whether the answer is fully supported by the given context.

CONTEXT:
{context}

QUESTION: {query}

ANSWER: {answer}

EVALUATION CRITERIA:
1. Every claim in the answer must be supported by the context
2. The answer must not add information beyond what's in the context
3. The answer must not contradict the context
4. If the answer says "I don't know" when context lacks info, that's GOOD

Respond in JSON format:
{{
    "score": <0.0 to 1.0, where 1.0 = fully supported>,
    "issues": [<list of unsupported or contradicted claims, or empty list>],
    "reasoning": "<brief explanation of your evaluation>"
}}"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return self._parse_response(message.content[0].text)
```

### Prompt Design Considerations

The judge prompt structure matters significantly:

```python
# WEAK prompt — too vague
weak_prompt = "Is this answer correct based on the context?"

# STRONG prompt — specific criteria
strong_prompt = """
Evaluate the answer against these specific criteria:
1. SUPPORTED: Every factual claim appears in the context
2. NO ADDITIONS: No information added beyond context
3. NO CONTRADICTIONS: Nothing that conflicts with context
4. APPROPRIATE ABSTENTION: Says "I don't know" when context lacks info
"""
```

**Key prompt elements:**

- Explicit evaluation criteria (not just "is it accurate?")
- Request for structured output (JSON, specific format)
- Ask for reasoning (helps catch edge cases)
- Define what "good" looks like (including abstention)

### Limitations of LLM-as-Judge

|Limitation|Impact|Mitigation|
|---|---|---|
|Judge can hallucinate|Misses actual issues, invents false positives|Use structured prompts, spot-check results|
|Same blind spots|GPT judging GPT may share biases|Cross-model judging (Claude judges GPT)|
|Latency + cost|Extra LLM call per response|Sample checking, batch processing|
|Calibration drift|Scores inconsistent over time|Regular benchmark testing|

### Cross-Model Judging

Using a different model family to judge can catch blind spots:

```python
class CrossModelChecker:
    """
    Use Claude to judge GPT outputs (or vice versa).
    Different model families have different failure modes.
    """
    
    def __init__(self):
        self.openai_client = OpenAI()
        self.anthropic_client = Anthropic()
    
    def generate_with_openai(self, query: str, context: str) -> str:
        """Generate answer with GPT."""
        response = self.openai_client.responses.create(
            model="gpt-4.1",
            input=f"Context: {context}\n\nQuestion: {query}\n\nAnswer:"
        )
        return response.output_text
    
    def judge_with_anthropic(
        self,
        query: str,
        context: str,
        answer: str
    ) -> FaithfulnessResult:
        """Use Claude to judge GPT's answer."""
        # Claude judges GPT output — different training, different blind spots
        checker = FaithfulnessCheckerAnthropic()
        return checker.check(query, context, answer)
```

---

## Technique 2: Entailment-Based Detection

Use Natural Language Inference (NLI) models to check if the context "entails" (logically implies) the answer.

### How It Works

```
NLI Task:
  Premise: "The refund period is 30 days."
  Hypothesis: "You can return items within a month."
  
  Output: ENTAILMENT (premise supports hypothesis)

Apply to RAG:
  Premise: Retrieved context
  Hypothesis: Each claim in the answer
  
  If ENTAILMENT → Claim is supported
  If CONTRADICTION → Hallucination detected
  If NEUTRAL → Potentially unsupported
```

### Implementation

```python
from transformers import pipeline
from dataclasses import dataclass

@dataclass
class EntailmentResult:
    label: str  # entailment, contradiction, neutral
    score: float
    
@dataclass
class ClaimVerification:
    claim: str
    result: EntailmentResult
    is_supported: bool

class EntailmentChecker:
    """
    Use NLI model for fast, deterministic faithfulness checking.
    
    Pros: Fast, no LLM costs, deterministic
    Cons: Less nuanced than LLM judge, may miss subtle issues
    """
    
    def __init__(self, model_name: str = "facebook/bart-large-mnli"):
        self.nli = pipeline("zero-shot-classification", model=model_name)
    
    def check_entailment(
        self,
        premise: str,
        hypothesis: str
    ) -> EntailmentResult:
        """
        Check if premise entails hypothesis.
        """
        result = self.nli(
            hypothesis,
            candidate_labels=["entailment", "contradiction", "neutral"],
            hypothesis_template="This text: {}",
            multi_label=False
        )
        
        # Get top label and score
        top_label = result["labels"][0]
        top_score = result["scores"][0]
        
        return EntailmentResult(label=top_label, score=top_score)
    
    def verify_claims(
        self,
        context: str,
        claims: list[str]
    ) -> list[ClaimVerification]:
        """
        Verify each claim against the context.
        """
        results = []
        
        for claim in claims:
            entailment = self.check_entailment(context, claim)
            
            # Only "entailment" counts as supported
            is_supported = (
                entailment.label == "entailment" and 
                entailment.score > 0.7
            )
            
            results.append(ClaimVerification(
                claim=claim,
                result=entailment,
                is_supported=is_supported
            ))
        
        return results


# Usage
checker = EntailmentChecker()

context = "The API rate limit is 1000 requests per minute."

claims = [
    "You can make up to 1000 API calls per minute.",  # Entailed
    "The rate limit is 500 requests per minute.",     # Contradiction
    "Exceeding the limit returns a 429 error.",       # Neutral (not stated)
]

for verification in checker.verify_claims(context, claims):
    print(f"Claim: {verification.claim}")
    print(f"  Label: {verification.result.label}, Score: {verification.result.score:.2f}")
    print(f"  Supported: {verification.is_supported}")
```

### When to Use Entailment vs. LLM-as-Judge

|Scenario|Use Entailment|Use LLM-as-Judge|
|---|---|---|
|High volume, low latency|✅|❌|
|Cost-sensitive|✅|❌|
|Nuanced claims, complex reasoning|❌|✅|
|Need detailed explanations|❌|✅|
|Deterministic results required|✅|❌|
|Subtle paraphrasing|❌|✅|

**Practical pattern:** Use entailment as a fast first pass, escalate to LLM-as-Judge for uncertain cases.

---

## Technique 3: Self-Consistency Checking

Generate multiple answers and check if they agree. Disagreement signals potential hallucination.

### How It Works

```
Query + Context
    ↓
Generate N answers (with temperature > 0)
    ↓
┌─────────────────────────────────────┐
│ Answer 1: "Refund period is 30 days" │
│ Answer 2: "Refund period is 30 days" │
│ Answer 3: "Refund period is 30 days" │
└─────────────────────────────────────┘
    ↓
High agreement → High confidence
    
vs.

┌─────────────────────────────────────┐
│ Answer 1: "Refund period is 30 days" │
│ Answer 2: "Refund period is 60 days" │
│ Answer 3: "Returns within 2 weeks"   │
└─────────────────────────────────────┘
    ↓
Low agreement → Low confidence → Potential hallucination
```

### SelfCheckGPT Approach

The SelfCheckGPT paper formalizes this: if the model is hallucinating, it will generate inconsistent content across samples because there's no grounding.

```python
from openai import OpenAI
from dataclasses import dataclass
import re

@dataclass
class ConsistencyResult:
    answers: list[str]
    agreement_score: float  # 0.0–1.0
    is_consistent: bool
    disagreements: list[str]

class SelfConsistencyChecker:
    """
    Generate multiple answers and check consistency.
    Based on SelfCheckGPT approach.
    """
    
    def __init__(
        self,
        model: str = "gpt-4.1",
        n_samples: int = 3,
        temperature: float = 0.7,
        consistency_threshold: float = 0.8
    ):
        self.client = OpenAI()
        self.model = model
        self.n_samples = n_samples
        self.temperature = temperature
        self.threshold = consistency_threshold
    
    def generate_samples(
        self,
        query: str,
        context: str
    ) -> list[str]:
        """Generate multiple answer samples."""
        answers = []
        
        prompt = f"""Based ONLY on the following context, answer the question.

Context: {context}

Question: {query}

Answer:"""
        
        for _ in range(self.n_samples):
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                temperature=self.temperature
            )
            answers.append(response.output_text)
        
        return answers
    
    def check_consistency(
        self,
        answers: list[str]
    ) -> ConsistencyResult:
        """
        Check consistency across answer samples.
        Uses LLM to compare answers semantically.
        """
        if len(answers) < 2:
            return ConsistencyResult(
                answers=answers,
                agreement_score=1.0,
                is_consistent=True,
                disagreements=[]
            )
        
        # Use LLM to compare answers
        comparison_prompt = f"""Compare these {len(answers)} answers to the same question.
Identify any factual disagreements between them.

{chr(10).join(f'Answer {i+1}: {a}' for i, a in enumerate(answers))}

Respond in JSON format:
{{
    "agreement_score": <0.0 to 1.0, where 1.0 = complete agreement>,
    "disagreements": [<list of specific factual disagreements, or empty>]
}}"""
        
        response = self.client.responses.create(
            model=self.model,
            input=comparison_prompt,
            temperature=0  # Deterministic comparison
        )
        
        return self._parse_comparison(answers, response.output_text)
    
    def _parse_comparison(
        self,
        answers: list[str],
        response_text: str
    ) -> ConsistencyResult:
        """Parse consistency comparison result."""
        try:
            # Handle markdown code blocks
            text = response_text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            import json
            data = json.loads(text.strip())
            score = float(data.get("agreement_score", 0.0))
            
            return ConsistencyResult(
                answers=answers,
                agreement_score=score,
                is_consistent=score >= self.threshold,
                disagreements=data.get("disagreements", [])
            )
        except Exception as e:
            return ConsistencyResult(
                answers=answers,
                agreement_score=0.0,
                is_consistent=False,
                disagreements=[f"Parse error: {str(e)}"]
            )
    
    def check(
        self,
        query: str,
        context: str
    ) -> ConsistencyResult:
        """Full self-consistency check."""
        answers = self.generate_samples(query, context)
        return self.check_consistency(answers)


# Usage
checker = SelfConsistencyChecker(n_samples=3)

context = "Our API supports Python, JavaScript, and Go clients."
query = "What programming languages are supported?"

result = checker.check(query, context)
print(f"Agreement: {result.agreement_score:.2f}")
print(f"Consistent: {result.is_consistent}")
if result.disagreements:
    print(f"Disagreements: {result.disagreements}")
```

### Cost-Effectiveness Considerations

Self-consistency multiplies your LLM costs by N (number of samples). Use selectively:

```python
class AdaptiveConsistencyChecker:
    """
    Use self-consistency only when other signals are uncertain.
    """
    
    def __init__(self):
        self.faithfulness_checker = FaithfulnessChecker()
        self.consistency_checker = SelfConsistencyChecker()
    
    def check(
        self,
        query: str,
        context: str,
        answer: str
    ) -> dict:
        # First: fast faithfulness check
        faith_result = self.faithfulness_checker.check(query, context, answer)
        
        # If clearly faithful or clearly unfaithful, done
        if faith_result.score > 0.9 or faith_result.score < 0.3:
            return {
                "method": "faithfulness_only",
                "score": faith_result.score,
                "is_reliable": faith_result.is_faithful
            }
        
        # Uncertain zone (0.3–0.9): add self-consistency
        consistency_result = self.consistency_checker.check(query, context)
        
        # Combine signals
        combined_score = (faith_result.score + consistency_result.agreement_score) / 2
        
        return {
            "method": "combined",
            "faithfulness_score": faith_result.score,
            "consistency_score": consistency_result.agreement_score,
            "combined_score": combined_score,
            "is_reliable": combined_score > 0.7
        }
```

---

## Technique 4: Citation Verification

Require the model to cite specific passages, then verify those citations exist and support the claims.

### How It Works

```
Step 1: Generate answer WITH citations
   "The refund period is 30 days [Source: paragraph 2]."

Step 2: Verify citations exist
   Does "paragraph 2" exist in context? ✓

Step 3: Verify citations support claims
   Does paragraph 2 actually say "30 days"? ✓
```

### Implementation

```python
from openai import OpenAI
from dataclasses import dataclass
import re

@dataclass
class Citation:
    claim: str
    source_ref: str  # e.g., "[1]", "[paragraph 2]"
    source_text: str | None  # Actual text from context
    is_valid: bool
    is_supportive: bool

@dataclass
class CitationVerificationResult:
    answer: str
    citations: list[Citation]
    all_valid: bool
    all_supportive: bool
    uncited_claims: list[str]

class CitationVerifier:
    """
    Generate answers with citations and verify them.
    """
    
    def __init__(self, model: str = "gpt-4.1"):
        self.client = OpenAI()
        self.model = model
    
    def generate_with_citations(
        self,
        query: str,
        context: str
    ) -> str:
        """Generate answer that cites specific passages."""
        
        # Number paragraphs for easy citation
        paragraphs = context.split('\n\n')
        numbered_context = "\n\n".join(
            f"[{i+1}] {p}" for i, p in enumerate(paragraphs) if p.strip()
        )
        
        prompt = f"""Answer the question based ONLY on the context below.
For each claim, cite the source paragraph number in brackets.

CONTEXT:
{numbered_context}

QUESTION: {query}

ANSWER (with citations like [1], [2], etc.):"""
        
        response = self.client.responses.create(
            model=self.model,
            input=prompt
        )
        
        return response.output_text
    
    def extract_citations(self, answer: str) -> list[tuple[str, str]]:
        """Extract (claim, citation) pairs from answer."""
        # Pattern: sentence or clause followed by [N]
        pattern = r'([^.!?\[\]]+)\s*\[(\d+)\]'
        matches = re.findall(pattern, answer)
        return [(claim.strip(), ref) for claim, ref in matches]
    
    def verify_citations(
        self,
        query: str,
        context: str,
        answer: str
    ) -> CitationVerificationResult:
        """Full citation verification pipeline."""
        
        # Parse context into numbered paragraphs
        paragraphs = context.split('\n\n')
        paragraph_map = {
            str(i+1): p for i, p in enumerate(paragraphs) if p.strip()
        }
        
        # Extract citations from answer
        citation_pairs = self.extract_citations(answer)
        
        citations = []
        for claim, ref in citation_pairs:
            source_text = paragraph_map.get(ref)
            is_valid = source_text is not None
            
            # Check if source supports the claim
            is_supportive = False
            if is_valid:
                is_supportive = self._check_support(claim, source_text)
            
            citations.append(Citation(
                claim=claim,
                source_ref=f"[{ref}]",
                source_text=source_text,
                is_valid=is_valid,
                is_supportive=is_supportive
            ))
        
        # Find uncited claims (sentences without citations)
        uncited = self._find_uncited_claims(answer, citation_pairs)
        
        return CitationVerificationResult(
            answer=answer,
            citations=citations,
            all_valid=all(c.is_valid for c in citations),
            all_supportive=all(c.is_supportive for c in citations),
            uncited_claims=uncited
        )
    
    def _check_support(self, claim: str, source: str) -> bool:
        """Use LLM to check if source supports claim."""
        prompt = f"""Does this source text support the claim?

SOURCE: {source}

CLAIM: {claim}

Answer only: YES or NO"""
        
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0
        )
        
        return "YES" in response.output_text.upper()
    
    def _find_uncited_claims(
        self,
        answer: str,
        cited_pairs: list[tuple[str, str]]
    ) -> list[str]:
        """Find claims in answer that don't have citations."""
        cited_claims = {claim for claim, _ in cited_pairs}
        
        # Split answer into sentences
        sentences = re.split(r'[.!?]+', answer)
        
        uncited = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            # Check if this sentence (or part of it) is cited
            if not any(cited in sentence or sentence in cited for cited in cited_claims):
                # Skip meta-sentences like "Based on the context..."
                if not sentence.lower().startswith(('based on', 'according to', 'the context')):
                    uncited.append(sentence)
        
        return uncited


# Usage
verifier = CitationVerifier()

context = """
Our standard refund policy allows returns within 30 days of purchase.
Items must be in original condition with all packaging intact.

For electronics, the refund period is extended to 60 days.
Electronics must include all accessories and manuals.

Digital products are non-refundable once downloaded.
"""

query = "What's the refund policy for electronics?"

# Generate with citations
answer = verifier.generate_with_citations(query, context)
print(f"Answer: {answer}")

# Verify citations
result = verifier.verify_citations(query, context, answer)
print(f"All citations valid: {result.all_valid}")
print(f"All citations supportive: {result.all_supportive}")
for citation in result.citations:
    print(f"  '{citation.claim}' → {citation.source_ref}: valid={citation.is_valid}, supportive={citation.is_supportive}")
if result.uncited_claims:
    print(f"Uncited claims: {result.uncited_claims}")
```

### Catches Fabricated Sources

Citation verification specifically targets the "fabricated sources" hallucination type:

```
Without citation verification:
   Answer: "According to Section 5.3.2, refunds take 3-5 days."
   → Looks authoritative
   → Section 5.3.2 doesn't exist
   → Undetected hallucination

With citation verification:
   Answer: "Refunds take 3-5 days [3]"
   → Check: Does paragraph [3] exist? Yes
   → Check: Does paragraph [3] say "3-5 days"? No
   → DETECTED: Citation doesn't support claim
```

---

## Technique 5: Claim Extraction and Verification

Break the answer into atomic claims, then verify each independently.

### How It Works

```
Answer: "Refunds are processed within 30 days. Expedited 
        processing is available for $25. All refunds go 
        to the original payment method."
           ↓
Extract claims:
  1. "Refunds are processed within 30 days"
  2. "Expedited processing is available for $25"
  3. "Refunds go to the original payment method"
           ↓
Verify each:
  4. ✓ Supported by context
  5. ✗ NOT in context — hallucination!
  6. ✓ Supported by context
           ↓
Result: Claim 2 is hallucinated
```

### Implementation

```python
from openai import OpenAI
from dataclasses import dataclass
import json

@dataclass
class ClaimResult:
    claim: str
    is_supported: bool
    evidence: str | None
    confidence: float

@dataclass
class ClaimVerificationResult:
    answer: str
    claims: list[ClaimResult]
    supported_count: int
    unsupported_count: int
    overall_faithfulness: float

class ClaimExtractorVerifier:
    """
    Extract atomic claims and verify each independently.
    
    Most granular detection — identifies exactly which parts
    of an answer are hallucinated.
    """
    
    def __init__(self, model: str = "gpt-4.1"):
        self.client = OpenAI()
        self.model = model
    
    def extract_claims(self, answer: str) -> list[str]:
        """Break answer into atomic, verifiable claims."""
        
        prompt = f"""Extract all factual claims from this text.
Each claim should be:
- Atomic (one fact per claim)
- Self-contained (understandable without context)
- Verifiable (can be checked as true/false)

TEXT:
{answer}

Return a JSON array of claim strings:
["claim 1", "claim 2", ...]"""
        
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0
        )
        
        try:
            text = response.output_text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except:
            # Fallback: split by sentences
            import re
            return [s.strip() for s in re.split(r'[.!?]+', answer) if s.strip()]
    
    def verify_claim(
        self,
        claim: str,
        context: str
    ) -> ClaimResult:
        """Verify a single claim against context."""
        
        prompt = f"""Is this claim supported by the context?

CONTEXT:
{context}

CLAIM: {claim}

Respond in JSON:
{{
    "is_supported": true/false,
    "evidence": "<quote from context that supports/refutes, or null if not found>",
    "confidence": <0.0 to 1.0>
}}"""
        
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0
        )
        
        try:
            text = response.output_text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            data = json.loads(text.strip())
            
            return ClaimResult(
                claim=claim,
                is_supported=data.get("is_supported", False),
                evidence=data.get("evidence"),
                confidence=float(data.get("confidence", 0.0))
            )
        except:
            return ClaimResult(
                claim=claim,
                is_supported=False,
                evidence=None,
                confidence=0.0
            )
    
    def verify_answer(
        self,
        answer: str,
        context: str
    ) -> ClaimVerificationResult:
        """Full claim extraction and verification."""
        
        claims = self.extract_claims(answer)
        results = []
        
        for claim in claims:
            result = self.verify_claim(claim, context)
            results.append(result)
        
        supported = sum(1 for r in results if r.is_supported)
        unsupported = len(results) - supported
        
        faithfulness = supported / len(results) if results else 0.0
        
        return ClaimVerificationResult(
            answer=answer,
            claims=results,
            supported_count=supported,
            unsupported_count=unsupported,
            overall_faithfulness=faithfulness
        )


# Usage
verifier = ClaimExtractorVerifier()

context = """
The enterprise plan costs $99/month per seat.
It includes SSO, audit logs, and dedicated support.
Minimum commitment is 10 seats.
"""

answer = """
The enterprise plan is $99/month per seat with a minimum of 10 seats.
It includes SSO, audit logs, dedicated support with 24/7 availability,
and custom SLA guarantees.
"""

result = verifier.verify_answer(answer, context)
print(f"Faithfulness: {result.overall_faithfulness:.1%}")
print(f"Supported: {result.supported_count}, Unsupported: {result.unsupported_count}")

for claim in result.claims:
    status = "✓" if claim.is_supported else "✗"
    print(f"{status} {claim.claim}")
    if claim.evidence:
        print(f"   Evidence: {claim.evidence}")
```

### Trade-offs

|Aspect|Claim Extraction|LLM-as-Judge|
|---|---|---|
|Granularity|High (per-claim)|Low (whole answer)|
|LLM calls|Many (1 + N claims)|One|
|Latency|Higher|Lower|
|Cost|Higher|Lower|
|Actionability|High (know exactly what's wrong)|Medium|
|Best for|High-stakes, debugging|Fast checking|

---

## Choosing Your Detection Approach

### Decision Framework

```
START
  │
  ├─→ Latency critical? (< 500ms)
  │     YES → Entailment models (no LLM calls)
  │     NO  ↓
  │
  ├─→ Cost sensitive?
  │     YES → LLM-as-Judge (1 call)
  │     NO  ↓
  │
  ├─→ High stakes? (legal, medical, financial)
  │     YES → Claim extraction + verification
  │     NO  ↓
  │
  └─→ Standard RAG
        → LLM-as-Judge sufficient
```

### Recommended Combinations

**Basic RAG (internal tools, low stakes):**

```python
# Just LLM-as-Judge
checker = FaithfulnessChecker(threshold=0.7)
```

**Customer-facing RAG (moderate stakes):**

```python
# LLM-as-Judge + Citation verification
checker = FaithfulnessChecker(threshold=0.75)
citation_verifier = CitationVerifier()
```

**High-stakes RAG (legal, medical, compliance):**

```python
# Full pipeline
claim_verifier = ClaimExtractorVerifier()  # Granular
consistency_checker = SelfConsistencyChecker()  # Additional signal
cross_model_checker = CrossModelChecker()  # Different perspective
```

**High-volume, cost-sensitive:**

```python
# Sample-based checking
def sample_check(answers: list, sample_rate: float = 0.1):
    """Only check a random sample of answers."""
    import random
    checker = FaithfulnessChecker()
    
    sample = random.sample(answers, int(len(answers) * sample_rate))
    results = [checker.check(a.query, a.context, a.answer) for a in sample]
    
    # If sample shows problems, check more or alert
    avg_score = sum(r.score for r in results) / len(results)
    return avg_score
```

---

## Key Takeaways

1. **LLM-as-Judge is your starting point**: Simple, effective, and catches most issues. Use cross-model judging for additional robustness.
    
2. **Entailment models for speed**: When latency or cost matters more than nuance, NLI models provide fast, deterministic checking.
    
3. **Self-consistency adds signal**: Especially useful when you're uncertain about context relevance. High disagreement across samples indicates low confidence.
    
4. **Citation verification catches fabricated sources**: Force the model to cite, then verify those citations actually exist and support the claims.
    
5. **Claim extraction for granularity**: When you need to know exactly which part of an answer is hallucinated, break it into atomic claims and verify each.
    
6. **Layer approaches by stakes**: Low stakes = simple checking. High stakes = multiple complementary techniques.
    

---

## What's Next

Note 3 covers mitigation strategies: how to prevent hallucinations from occurring in the first place, including grounding prompts, abstention logic, and multi-step verification.