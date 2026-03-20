# Note 4: Building a Hallucination Detection Pipeline

## Pipeline Architecture

This note brings together the components from Notes 2 and 3 into a complete, production-ready pipeline.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HALLUCINATION GUARD PIPELINE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Query ──→ Retrieve ──→ [Relevance Check] ──→ Generate ──→ [Faithfulness]  │
│                              │                                   │          │
│                              ▼                                   ▼          │
│                        Low relevance?                      Low score?       │
│                              │                                   │          │
│                              ▼                                   ▼          │
│                     Early Abstention              Retry with stricter prompt│
│                                                          │                  │
│                                                          ▼                  │
│                                                   Still failing?            │
│                                                          │                  │
│                                                          ▼                  │
│                                                   Late Abstention           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

Each component has a single responsibility:

1. **Relevance Checker**: Gate on retrieval quality before generating
2. **Grounded Generator**: Generate with strict constraints
3. **Faithfulness Checker**: Verify answer against context
4. **Abstention Handler**: Produce helpful "I don't know" responses

---

## Component 1: Relevance Checker

**Purpose**: Determine if retrieved chunks are relevant enough to proceed with generation. If not, abstain early — don't waste tokens on a generation that can't be grounded.

**Doc reference:** OpenAI Responses API (https://platform.openai.com/docs/api-reference/responses)

```python
from dataclasses import dataclass
from openai import OpenAI
import json

@dataclass
class RelevanceResult:
    """Result of relevance assessment."""
    is_relevant: bool
    relevance_score: float  # 0.0–1.0
    relevant_chunk_indices: list[int]
    irrelevant_chunk_indices: list[int]
    reasoning: str
    should_proceed: bool

class RelevanceChecker:
    """
    Assess if retrieved chunks are relevant to the query.
    
    This is the first gate — if retrieval failed, don't bother generating.
    """
    
    def __init__(
        self,
        model: str = "gpt-4.1",
        relevance_threshold: float = 0.6,
        min_relevant_chunks: int = 1
    ):
        self.client = OpenAI()
        self.model = model
        self.relevance_threshold = relevance_threshold
        self.min_relevant_chunks = min_relevant_chunks
    
    def check(
        self,
        query: str,
        chunks: list[dict]
    ) -> RelevanceResult:
        """
        Check if chunks are relevant to the query.
        
        Args:
            query: The user's question
            chunks: List of {"text": str, "score": float, "metadata": dict}
        
        Returns:
            RelevanceResult with assessment
        """
        if not chunks:
            return RelevanceResult(
                is_relevant=False,
                relevance_score=0.0,
                relevant_chunk_indices=[],
                irrelevant_chunk_indices=[],
                reasoning="No chunks retrieved",
                should_proceed=False
            )
        
        # Format chunks for evaluation
        chunks_text = "\n\n".join(
            f"[Chunk {i}]: {c['text'][:500]}..."
            if len(c['text']) > 500 else f"[Chunk {i}]: {c['text']}"
            for i, c in enumerate(chunks)
        )
        
        prompt = f"""Evaluate if these retrieved chunks are relevant to answering the query.

QUERY: {query}

RETRIEVED CHUNKS:
{chunks_text}

For each chunk, assess:
1. Does it contain information that helps answer the query?
2. Is the information directly relevant or only tangentially related?

Respond in JSON:
{{
    "overall_relevance_score": <0.0-1.0>,
    "relevant_chunks": [<indices of relevant chunks>],
    "irrelevant_chunks": [<indices of irrelevant chunks>],
    "reasoning": "<brief explanation>"
}}"""
        
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0
        )
        
        return self._parse_response(response.output_text, len(chunks))
    
    def _parse_response(
        self,
        text: str,
        total_chunks: int
    ) -> RelevanceResult:
        """Parse LLM response into RelevanceResult."""
        try:
            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            data = json.loads(text.strip())
            score = float(data.get("overall_relevance_score", 0.0))
            relevant = data.get("relevant_chunks", [])
            irrelevant = data.get("irrelevant_chunks", [])
            
            # Determine if we should proceed
            should_proceed = (
                score >= self.relevance_threshold and
                len(relevant) >= self.min_relevant_chunks
            )
            
            return RelevanceResult(
                is_relevant=score >= self.relevance_threshold,
                relevance_score=score,
                relevant_chunk_indices=relevant,
                irrelevant_chunk_indices=irrelevant,
                reasoning=data.get("reasoning", ""),
                should_proceed=should_proceed
            )
        except (json.JSONDecodeError, KeyError) as e:
            # Conservative fallback: assume not relevant
            return RelevanceResult(
                is_relevant=False,
                relevance_score=0.0,
                relevant_chunk_indices=[],
                irrelevant_chunk_indices=list(range(total_chunks)),
                reasoning=f"Failed to parse relevance check: {str(e)}",
                should_proceed=False
            )
```

---

## Component 2: Grounded Generator

**Purpose**: Generate answers with strict grounding constraints. This is where prompt engineering from Note 3 is applied.

```python
@dataclass
class GenerationResult:
    """Result of grounded generation."""
    answer: str
    prompt_version: str  # "standard" or "strict"
    temperature: float

class GroundedGenerator:
    """
    Generate answers strictly grounded in provided context.
    
    Uses carefully designed prompts to minimize hallucination.
    """
    
    STANDARD_SYSTEM_PROMPT = """You are a research assistant that answers questions based ONLY on the provided context.

CRITICAL RULES:
1. Use ONLY information explicitly stated in the context
2. Do NOT add information from your general knowledge
3. Do NOT infer or extrapolate beyond what the context says
4. If the context doesn't contain the answer, say: "I don't have information about this in the available documents."
5. When possible, quote directly from the context
6. If you're uncertain, express that uncertainty

For each claim you make, ensure it's directly supported by the context."""

    STRICT_SYSTEM_PROMPT = """You are a research assistant. Your previous answer contained unsupported claims. Be MORE CAREFUL this time.

STRICT RULES (MUST FOLLOW):
1. Use ONLY information EXPLICITLY stated in the context
2. QUOTE directly from the context whenever possible
3. If something isn't EXPLICITLY stated, do NOT include it
4. Shorter, more focused answers are better
5. When in doubt, say "The documents don't specify this"
6. Do NOT guess, infer, or extrapolate

If you cannot find explicit support for a claim in the context, DO NOT make that claim."""

    def __init__(
        self,
        model: str = "gpt-4.1",
        standard_temperature: float = 0.3,
        strict_temperature: float = 0.1
    ):
        self.client = OpenAI()
        self.model = model
        self.standard_temperature = standard_temperature
        self.strict_temperature = strict_temperature
    
    def generate(
        self,
        query: str,
        context: str,
        strict_mode: bool = False
    ) -> GenerationResult:
        """
        Generate a grounded answer.
        
        Args:
            query: User's question
            context: Retrieved context (already filtered for relevance)
            strict_mode: If True, use stricter prompt (for retries)
        
        Returns:
            GenerationResult with answer and metadata
        """
        system_prompt = (
            self.STRICT_SYSTEM_PROMPT if strict_mode 
            else self.STANDARD_SYSTEM_PROMPT
        )
        temperature = (
            self.strict_temperature if strict_mode 
            else self.standard_temperature
        )
        
        user_prompt = f"""CONTEXT:
{context}

---

QUESTION: {query}

Answer based ONLY on the context above:"""
        
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature
        )
        
        return GenerationResult(
            answer=response.output_text,
            prompt_version="strict" if strict_mode else "standard",
            temperature=temperature
        )
```

---

## Component 3: Faithfulness Checker

**Purpose**: Verify that the generated answer is faithful to the context. This is the LLM-as-Judge from Note 2.

```python
@dataclass
class FaithfulnessResult:
    """Result of faithfulness check."""
    score: float  # 0.0–1.0
    is_faithful: bool
    issues: list[str]
    reasoning: str

class FaithfulnessChecker:
    """
    Check if an answer is faithful to the provided context.
    
    Uses LLM-as-Judge approach to evaluate grounding.
    """
    
    def __init__(
        self,
        model: str = "gpt-4.1",
        faithfulness_threshold: float = 0.75
    ):
        self.client = OpenAI()
        self.model = model
        self.threshold = faithfulness_threshold
    
    def check(
        self,
        query: str,
        context: str,
        answer: str
    ) -> FaithfulnessResult:
        """
        Check if answer is faithful to context.
        
        Args:
            query: Original question
            context: Retrieved context
            answer: Generated answer to verify
        
        Returns:
            FaithfulnessResult with score and issues
        """
        prompt = f"""You are a factual accuracy checker. Evaluate if the answer is fully supported by the context.

CONTEXT:
{context}

QUESTION: {query}

ANSWER: {answer}

EVALUATION CRITERIA:
1. Every claim in the answer must be supported by the context
2. The answer must not add information beyond what's in the context
3. The answer must not contradict the context
4. If the answer says "I don't know" when context lacks info, that's GOOD (score 1.0)
5. Partial information with appropriate caveats is acceptable

Respond in JSON:
{{
    "score": <0.0 to 1.0, where 1.0 = fully supported>,
    "issues": [<list of unsupported or contradicted claims, empty if none>],
    "reasoning": "<brief explanation of your evaluation>"
}}"""

        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0  # Deterministic evaluation
        )
        
        return self._parse_response(response.output_text)
    
    def _parse_response(self, text: str) -> FaithfulnessResult:
        """Parse LLM response into FaithfulnessResult."""
        try:
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
            # Conservative fallback: treat as unfaithful
            return FaithfulnessResult(
                score=0.0,
                is_faithful=False,
                issues=[f"Failed to parse faithfulness check: {str(e)}"],
                reasoning="Parse error"
            )
```

---

## Component 4: Abstention Handler

**Purpose**: Generate helpful abstention messages when we can't provide a reliable answer.

```python
@dataclass
class AbstentionMessage:
    """A helpful abstention response."""
    message: str
    reason: str
    what_we_found: str | None
    suggestions: list[str]

class AbstentionHandler:
    """
    Generate helpful abstention messages.
    
    Abstentions should be informative, not just "I don't know."
    """
    
    def __init__(self, model: str = "gpt-4.1"):
        self.client = OpenAI()
        self.model = model
    
    def create_abstention(
        self,
        query: str,
        reason: str,
        context_summary: str | None = None,
        failed_answer: str | None = None,
        issues: list[str] | None = None
    ) -> AbstentionMessage:
        """
        Create a helpful abstention message.
        
        Args:
            query: What the user asked
            reason: Why we're abstaining (no_relevant_context, low_faithfulness, etc.)
            context_summary: Brief summary of what we did find
            failed_answer: The answer that failed verification (for debugging)
            issues: Specific issues found during verification
        
        Returns:
            AbstentionMessage with helpful response
        """
        # Map reasons to user-friendly explanations
        reason_explanations = {
            "no_relevant_context": (
                "I couldn't find documents that address your question."
            ),
            "low_relevance": (
                "The available documents don't seem to contain information "
                "about this topic."
            ),
            "low_faithfulness": (
                "I found some related information, but I wasn't able to "
                "generate a fully accurate answer based on the documents."
            ),
            "max_retries_exceeded": (
                "After multiple attempts, I couldn't provide a reliable "
                "answer from the available documents."
            )
        }
        
        base_explanation = reason_explanations.get(
            reason,
            "I don't have enough information to answer accurately."
        )
        
        # Build the message
        message_parts = [base_explanation]
        
        # Add what we did find, if anything
        what_we_found = None
        if context_summary:
            what_we_found = context_summary
            message_parts.append(
                f"\nWhat I found: {context_summary}"
            )
        
        # Add suggestions
        suggestions = self._generate_suggestions(query, reason)
        if suggestions:
            message_parts.append(
                "\nSuggestions:\n" + 
                "\n".join(f"• {s}" for s in suggestions)
            )
        
        return AbstentionMessage(
            message="\n".join(message_parts),
            reason=reason,
            what_we_found=what_we_found,
            suggestions=suggestions
        )
    
    def _generate_suggestions(
        self,
        query: str,
        reason: str
    ) -> list[str]:
        """Generate helpful suggestions based on abstention reason."""
        suggestions = []
        
        if reason in ["no_relevant_context", "low_relevance"]:
            suggestions.extend([
                "Try rephrasing your question with different keywords",
                "Ask about a related topic that might be covered",
                "Check if the information exists in a different document set"
            ])
        elif reason in ["low_faithfulness", "max_retries_exceeded"]:
            suggestions.extend([
                "Ask a more specific question",
                "Break your question into smaller parts",
                "Request direct quotes from the documents instead"
            ])
        
        return suggestions[:3]  # Limit to 3 suggestions
```

---

## The Complete HallucinationGuard

Now we combine all components into a single orchestrating class.

```python
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HallucinationGuard")

@dataclass
class GuardConfig:
    """Configuration for HallucinationGuard."""
    # Thresholds
    relevance_threshold: float = 0.6
    faithfulness_threshold: float = 0.75
    min_relevant_chunks: int = 1
    
    # Retry settings
    max_retries: int = 2
    
    # Model settings
    model: str = "gpt-4.1"
    standard_temperature: float = 0.3
    strict_temperature: float = 0.1
    
    # Logging
    log_all_checks: bool = True

@dataclass
class GuardResult:
    """Complete result from HallucinationGuard."""
    # Final output
    answer: str
    status: str  # "success", "abstained"
    
    # Scores
    relevance_score: float
    faithfulness_score: float
    
    # Debug info
    attempts: int
    abstention_reason: Optional[str]
    issues_found: list[str]
    
    # Timing
    total_time_ms: float
    
    # Full trace for debugging
    trace: dict = field(default_factory=dict)

class HallucinationGuard:
    """
    Complete hallucination detection and mitigation pipeline.
    
    Orchestrates:
    1. Relevance checking (gate on retrieval quality)
    2. Grounded generation (constrained prompts)
    3. Faithfulness checking (verify answer)
    4. Retry logic (stricter prompts on failure)
    5. Abstention (graceful failure)
    
    Usage:
        guard = HallucinationGuard(config)
        result = guard.process(query, chunks)
        
        if result.status == "success":
            return result.answer
        else:
            return result.answer  # Abstention message
    """
    
    def __init__(self, config: GuardConfig | None = None):
        self.config = config or GuardConfig()
        
        # Initialize components
        self.relevance_checker = RelevanceChecker(
            model=self.config.model,
            relevance_threshold=self.config.relevance_threshold,
            min_relevant_chunks=self.config.min_relevant_chunks
        )
        
        self.generator = GroundedGenerator(
            model=self.config.model,
            standard_temperature=self.config.standard_temperature,
            strict_temperature=self.config.strict_temperature
        )
        
        self.faithfulness_checker = FaithfulnessChecker(
            model=self.config.model,
            faithfulness_threshold=self.config.faithfulness_threshold
        )
        
        self.abstention_handler = AbstentionHandler(
            model=self.config.model
        )
    
    def process(
        self,
        query: str,
        chunks: list[dict]
    ) -> GuardResult:
        """
        Process a query through the full pipeline.
        
        Args:
            query: User's question
            chunks: Retrieved chunks [{"text": str, "score": float, ...}]
        
        Returns:
            GuardResult with answer or abstention
        """
        start_time = datetime.now()
        trace = {"query": query, "chunk_count": len(chunks)}
        all_issues = []
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: Check Relevance
        # ═══════════════════════════════════════════════════════════
        self._log("Checking relevance...")
        relevance_result = self.relevance_checker.check(query, chunks)
        trace["relevance"] = {
            "score": relevance_result.relevance_score,
            "relevant_chunks": relevance_result.relevant_chunk_indices,
            "should_proceed": relevance_result.should_proceed
        }
        
        # Gate: Early abstention if retrieval failed
        if not relevance_result.should_proceed:
            self._log(f"Early abstention: relevance={relevance_result.relevance_score:.2f}")
            
            abstention = self.abstention_handler.create_abstention(
                query=query,
                reason="low_relevance",
                context_summary=relevance_result.reasoning
            )
            
            return GuardResult(
                answer=abstention.message,
                status="abstained",
                relevance_score=relevance_result.relevance_score,
                faithfulness_score=0.0,
                attempts=0,
                abstention_reason="low_relevance",
                issues_found=[],
                total_time_ms=self._elapsed_ms(start_time),
                trace=trace
            )
        
        # Filter to relevant chunks only
        relevant_chunks = [
            chunks[i] for i in relevance_result.relevant_chunk_indices
            if i < len(chunks)
        ]
        context = self._format_context(relevant_chunks)
        trace["filtered_chunk_count"] = len(relevant_chunks)
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2: Generate + Verify Loop
        # ═══════════════════════════════════════════════════════════
        last_faithfulness_score = 0.0
        trace["attempts"] = []
        
        for attempt in range(self.config.max_retries + 1):
            strict_mode = attempt > 0
            self._log(f"Attempt {attempt + 1}: strict_mode={strict_mode}")
            
            # Generate
            gen_result = self.generator.generate(
                query=query,
                context=context,
                strict_mode=strict_mode
            )
            
            # Check faithfulness
            faith_result = self.faithfulness_checker.check(
                query=query,
                context=context,
                answer=gen_result.answer
            )
            
            # Track attempt
            attempt_trace = {
                "attempt": attempt + 1,
                "strict_mode": strict_mode,
                "answer_preview": gen_result.answer[:200] + "...",
                "faithfulness_score": faith_result.score,
                "is_faithful": faith_result.is_faithful,
                "issues": faith_result.issues
            }
            trace["attempts"].append(attempt_trace)
            
            all_issues.extend(faith_result.issues)
            last_faithfulness_score = faith_result.score
            
            # Success: answer is faithful
            if faith_result.is_faithful:
                self._log(f"Success: faithfulness={faith_result.score:.2f}")
                
                return GuardResult(
                    answer=gen_result.answer,
                    status="success",
                    relevance_score=relevance_result.relevance_score,
                    faithfulness_score=faith_result.score,
                    attempts=attempt + 1,
                    abstention_reason=None,
                    issues_found=all_issues,
                    total_time_ms=self._elapsed_ms(start_time),
                    trace=trace
                )
            
            self._log(
                f"Attempt {attempt + 1} failed: "
                f"score={faith_result.score:.2f}, issues={faith_result.issues}"
            )
        
        # ═══════════════════════════════════════════════════════════
        # STEP 3: All Retries Failed — Abstain
        # ═══════════════════════════════════════════════════════════
        self._log(f"Max retries exceeded, abstaining")
        
        abstention = self.abstention_handler.create_abstention(
            query=query,
            reason="max_retries_exceeded",
            context_summary=f"Found {len(relevant_chunks)} relevant documents",
            issues=list(set(all_issues))  # Deduplicate
        )
        
        return GuardResult(
            answer=abstention.message,
            status="abstained",
            relevance_score=relevance_result.relevance_score,
            faithfulness_score=last_faithfulness_score,
            attempts=self.config.max_retries + 1,
            abstention_reason="max_retries_exceeded",
            issues_found=list(set(all_issues)),
            total_time_ms=self._elapsed_ms(start_time),
            trace=trace
        )
    
    def _format_context(self, chunks: list[dict]) -> str:
        """Format chunks into context string."""
        formatted = []
        for i, chunk in enumerate(chunks):
            metadata = chunk.get("metadata", {})
            source = metadata.get("source", f"Document {i+1}")
            text = chunk.get("text", "")
            formatted.append(f"[{source}]\n{text}")
        return "\n\n---\n\n".join(formatted)
    
    def _elapsed_ms(self, start_time: datetime) -> float:
        """Calculate elapsed milliseconds."""
        return (datetime.now() - start_time).total_seconds() * 1000
    
    def _log(self, message: str):
        """Log if logging is enabled."""
        if self.config.log_all_checks:
            logger.info(f"[HallucinationGuard] {message}")
```

---

## Usage Example

```python
# Initialize the guard
config = GuardConfig(
    relevance_threshold=0.6,
    faithfulness_threshold=0.75,
    max_retries=2,
    model="gpt-4.1"
)
guard = HallucinationGuard(config)

# Simulate retrieved chunks
chunks = [
    {
        "text": "Our refund policy allows returns within 30 days of purchase. Items must be in original packaging.",
        "score": 0.92,
        "metadata": {"source": "refund_policy.pdf"}
    },
    {
        "text": "Refunds are processed to the original payment method within 5-7 business days.",
        "score": 0.88,
        "metadata": {"source": "refund_policy.pdf"}
    }
]

# Process a query
query = "What's your refund policy?"
result = guard.process(query, chunks)

# Handle result
if result.status == "success":
    print(f"Answer: {result.answer}")
    print(f"Faithfulness: {result.faithfulness_score:.2f}")
else:
    print(f"Abstained: {result.answer}")
    print(f"Reason: {result.abstention_reason}")

# Debug info
print(f"Attempts: {result.attempts}")
print(f"Time: {result.total_time_ms:.0f}ms")
if result.issues_found:
    print(f"Issues: {result.issues_found}")
```

---

## Testing the Pipeline

Create test cases that verify each component and the full pipeline.

### Test Fixture Setup

```python
import pytest
from dataclasses import dataclass

@dataclass
class TestCase:
    """A test case for the hallucination guard."""
    name: str
    query: str
    chunks: list[dict]
    expected_status: str  # "success" or "abstained"
    expected_abstention_reason: str | None = None
    min_faithfulness: float | None = None

# Test cases
TEST_CASES = [
    # ───────────────────────────────────────────────────────────
    # CASE 1: Answerable query — should succeed
    # ───────────────────────────────────────────────────────────
    TestCase(
        name="answerable_query",
        query="What is the refund period?",
        chunks=[
            {
                "text": "Our refund policy allows returns within 30 days of purchase. Items must be in original condition.",
                "score": 0.95,
                "metadata": {"source": "policy.pdf"}
            }
        ],
        expected_status="success",
        min_faithfulness=0.75
    ),
    
    # ───────────────────────────────────────────────────────────
    # CASE 2: No relevant context — should abstain early
    # ───────────────────────────────────────────────────────────
    TestCase(
        name="no_relevant_context",
        query="What is the shipping policy?",
        chunks=[
            {
                "text": "Our company was founded in 1985 in San Francisco.",
                "score": 0.3,
                "metadata": {"source": "about.pdf"}
            }
        ],
        expected_status="abstained",
        expected_abstention_reason="low_relevance"
    ),
    
    # ───────────────────────────────────────────────────────────
    # CASE 3: Empty chunks — should abstain
    # ───────────────────────────────────────────────────────────
    TestCase(
        name="empty_chunks",
        query="What is the return policy?",
        chunks=[],
        expected_status="abstained",
        expected_abstention_reason="low_relevance"
    ),
    
    # ───────────────────────────────────────────────────────────
    # CASE 4: Partial information — should answer what's available
    # ───────────────────────────────────────────────────────────
    TestCase(
        name="partial_information",
        query="What is the refund period and processing time?",
        chunks=[
            {
                "text": "Refunds must be requested within 30 days.",
                "score": 0.9,
                "metadata": {"source": "policy.pdf"}
            }
            # Note: No info about processing time
        ],
        expected_status="success",  # Should answer what it can
        min_faithfulness=0.7
    ),
    
    # ───────────────────────────────────────────────────────────
    # CASE 5: Query clearly outside knowledge base
    # ───────────────────────────────────────────────────────────
    TestCase(
        name="out_of_scope_query",
        query="What is the CEO's favorite color?",
        chunks=[
            {
                "text": "The CEO, John Smith, has led the company since 2015.",
                "score": 0.4,
                "metadata": {"source": "leadership.pdf"}
            }
        ],
        expected_status="abstained",
        expected_abstention_reason="low_relevance"
    ),
]
```

### Test Implementation

```python
class TestHallucinationGuard:
    """Tests for the HallucinationGuard pipeline."""
    
    @pytest.fixture
    def guard(self):
        """Create a guard instance for testing."""
        config = GuardConfig(
            relevance_threshold=0.6,
            faithfulness_threshold=0.75,
            max_retries=1,  # Fewer retries for faster tests
            log_all_checks=False
        )
        return HallucinationGuard(config)
    
    @pytest.mark.parametrize("test_case", TEST_CASES, ids=lambda tc: tc.name)
    def test_pipeline(self, guard, test_case: TestCase):
        """Test the full pipeline with various cases."""
        result = guard.process(test_case.query, test_case.chunks)
        
        # Check status
        assert result.status == test_case.expected_status, (
            f"Expected status '{test_case.expected_status}', "
            f"got '{result.status}'"
        )
        
        # Check abstention reason if applicable
        if test_case.expected_abstention_reason:
            assert result.abstention_reason == test_case.expected_abstention_reason, (
                f"Expected reason '{test_case.expected_abstention_reason}', "
                f"got '{result.abstention_reason}'"
            )
        
        # Check faithfulness if applicable
        if test_case.min_faithfulness and result.status == "success":
            assert result.faithfulness_score >= test_case.min_faithfulness, (
                f"Expected faithfulness >= {test_case.min_faithfulness}, "
                f"got {result.faithfulness_score}"
            )
    
    def test_faithful_answer_passes(self, guard):
        """Verify that a faithful answer passes verification."""
        chunks = [
            {
                "text": "The API rate limit is 1000 requests per minute.",
                "score": 0.95,
                "metadata": {"source": "api_docs.md"}
            }
        ]
        
        result = guard.process("What is the API rate limit?", chunks)
        
        assert result.status == "success"
        assert result.faithfulness_score >= 0.75
        assert "1000" in result.answer or "1,000" in result.answer
    
    def test_abstention_message_is_helpful(self, guard):
        """Verify abstention messages are informative."""
        chunks = []  # No context
        
        result = guard.process("What is the pricing?", chunks)
        
        assert result.status == "abstained"
        # Should not just say "I don't know"
        assert len(result.answer) > 50
        # Should include suggestions
        assert "rephras" in result.answer.lower() or "suggest" in result.answer.lower()
    
    def test_retry_uses_stricter_prompt(self, guard):
        """Verify that retries use stricter prompts."""
        # This test would need mocking to verify prompt changes
        # For now, we verify the trace captures attempts
        chunks = [
            {
                "text": "We offer multiple plans.",
                "score": 0.8,
                "metadata": {"source": "pricing.pdf"}
            }
        ]
        
        result = guard.process("What are the exact prices?", chunks)
        
        # Check that trace captured attempts
        assert "attempts" in result.trace
        # At least one attempt should be made
        assert len(result.trace["attempts"]) >= 1
    
    def test_timing_is_tracked(self, guard):
        """Verify timing is tracked."""
        chunks = [
            {
                "text": "Basic plan costs $10/month.",
                "score": 0.9,
                "metadata": {"source": "pricing.pdf"}
            }
        ]
        
        result = guard.process("What does the basic plan cost?", chunks)
        
        assert result.total_time_ms > 0
        assert result.total_time_ms < 60000  # Should complete in < 60s
```

### Running Tests

```bash
# Run all tests
pytest test_hallucination_guard.py -v

# Run specific test
pytest test_hallucination_guard.py::TestHallucinationGuard::test_faithful_answer_passes -v

# Run with coverage
pytest test_hallucination_guard.py --cov=hallucination_guard --cov-report=html
```

---

## Logging and Debugging

The pipeline includes comprehensive tracing for debugging:

```python
def debug_result(result: GuardResult):
    """Print detailed debug information."""
    print("=" * 60)
    print(f"STATUS: {result.status}")
    print(f"ANSWER: {result.answer[:200]}...")
    print("-" * 60)
    print(f"Relevance Score: {result.relevance_score:.2f}")
    print(f"Faithfulness Score: {result.faithfulness_score:.2f}")
    print(f"Attempts: {result.attempts}")
    print(f"Time: {result.total_time_ms:.0f}ms")
    
    if result.abstention_reason:
        print(f"Abstention Reason: {result.abstention_reason}")
    
    if result.issues_found:
        print(f"Issues Found:")
        for issue in result.issues_found:
            print(f"  - {issue}")
    
    print("-" * 60)
    print("TRACE:")
    import json
    print(json.dumps(result.trace, indent=2, default=str))


# Usage
result = guard.process(query, chunks)
debug_result(result)
```

---

## Configuration Tuning

Different use cases require different configurations:

```python
# High-stakes (legal, medical)
high_stakes_config = GuardConfig(
    relevance_threshold=0.8,      # Higher bar for relevance
    faithfulness_threshold=0.9,   # Very strict faithfulness
    max_retries=3,                # More attempts
    standard_temperature=0.1,     # Very deterministic
    strict_temperature=0.0
)

# Balanced (customer support)
balanced_config = GuardConfig(
    relevance_threshold=0.6,
    faithfulness_threshold=0.75,
    max_retries=2,
    standard_temperature=0.3,
    strict_temperature=0.1
)

# Lenient (internal tools)
lenient_config = GuardConfig(
    relevance_threshold=0.5,
    faithfulness_threshold=0.65,
    max_retries=1,
    standard_temperature=0.4,
    strict_temperature=0.2
)
```

---

## Key Takeaways

1. **Pipeline structure matters**: Relevance check → Generate → Verify → Retry/Abstain creates clear decision points.
    
2. **Early abstention saves resources**: If retrieval failed, don't waste tokens on generation.
    
3. **Retry with escalation**: Stricter prompts + lower temperature on retry often fixes borderline cases.
    
4. **Abstentions should be helpful**: Include what was found, what's missing, and suggestions.
    
5. **Comprehensive tracing**: Log everything for debugging production issues.
    
6. **Test the failure modes**: Your test suite should cover answerable queries, unanswerable queries, edge cases, and abstention quality.
    

---

## What's Next

Note 5 covers production monitoring: how to track hallucination rates, alert on quality degradation, and continuously improve the pipeline based on real-world data.