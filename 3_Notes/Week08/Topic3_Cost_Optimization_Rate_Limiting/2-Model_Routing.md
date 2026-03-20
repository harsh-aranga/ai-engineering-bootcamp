# Note 2: Model Routing — Cheap Models for Cheap Tasks

## The Core Insight

Not every task needs your most capable model. A query classification that outputs one word doesn't need GPT-4o. Query reformulation that tweaks phrasing doesn't need Claude Opus. Simple extraction from structured text doesn't need your flagship model.

The insight is simple, but the savings are dramatic:

```
Task: Classify query as "financial" or "general"

GPT-4o:      $2.50/1M input, $10.00/1M output
GPT-4o-mini: $0.15/1M input, $0.60/1M output

Same result, 16x cost difference.
```

Model routing is the practice of directing different tasks to different models based on what each task actually requires. It's the highest-leverage cost optimization available.

---

## Task-to-Model Mapping

### The Mental Model

Think of your LLM operations in tiers:

```
┌─────────────────────────────────────────────────────────────────┐
│  TIER 1: Pattern Matching / Simple Classification               │
│  - Query classification (financial vs general vs support)       │
│  - Intent detection                                             │
│  - Simple extraction (dates, names, numbers)                    │
│  - Query reformulation                                          │
│  - Yes/no decisions                                             │
│                                                                 │
│  Model: gpt-4o-mini / claude-haiku-4-5                         │
│  Why: Output is constrained, reasoning is shallow               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  TIER 2: Moderate Reasoning / Standard Generation               │
│  - RAG answer synthesis (with good context)                     │
│  - Summarization                                                │
│  - Standard Q&A                                                 │
│  - Code explanation                                             │
│  - Translation                                                  │
│                                                                 │
│  Model: gpt-4o-mini / claude-sonnet-4-6                        │
│  Why: Reasoning required, but well-supported by context         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  TIER 3: Complex Reasoning / Creative Generation                │
│  - Multi-step analysis                                          │
│  - Complex code generation                                      │
│  - Synthesis across contradictory sources                       │
│  - Nuanced judgment calls                                       │
│  - Long-form creative content                                   │
│                                                                 │
│  Model: gpt-4o / claude-opus-4-6                               │
│  Why: Genuine reasoning required, stakes justify cost           │
└─────────────────────────────────────────────────────────────────┘
```

### Concrete Task Mapping

```python
# Task → Model mapping for a Research Assistant
MODEL_ROUTING = {
    # Tier 1: Cheap tasks → cheap model
    "query_classification": "gpt-4o-mini",
    "intent_detection": "gpt-4o-mini",
    "query_reformulation": "gpt-4o-mini",
    "entity_extraction": "gpt-4o-mini",
    "language_detection": "gpt-4o-mini",
    "yes_no_decision": "gpt-4o-mini",
    
    # Tier 2: Moderate tasks → capable but affordable
    "rag_synthesis": "gpt-4o-mini",  # Context does heavy lifting
    "summarization": "gpt-4o-mini",
    "simple_qa": "gpt-4o-mini",
    "code_explanation": "gpt-4o-mini",
    
    # Tier 3: Complex tasks → capable model (use sparingly)
    "multi_step_reasoning": "gpt-4o",
    "complex_code_generation": "gpt-4o",
    "contradictory_source_synthesis": "gpt-4o",
    "creative_writing": "gpt-4o",
    
    # Special: Embeddings → embedding model
    "embedding": "text-embedding-3-small",
}
```

---

## Implementing Model Routing

### Basic Config-Based Router

```python
from dataclasses import dataclass
from typing import Optional
from openai import OpenAI

@dataclass
class ModelConfig:
    """Configuration for a model including pricing."""
    model_id: str
    input_price_per_1m: float  # USD per 1M tokens
    output_price_per_1m: float
    max_output_tokens: int = 4096
    
    @property
    def tier(self) -> str:
        """Classify model by cost tier."""
        if self.output_price_per_1m < 1.0:
            return "budget"
        elif self.output_price_per_1m < 10.0:
            return "standard"
        else:
            return "premium"


class ModelRouter:
    """Route tasks to appropriate models based on complexity."""
    
    # Model configurations (prices as of early 2026)
    # Source: OpenAI Pricing page, Anthropic Pricing docs
    MODELS = {
        "gpt-4o-mini": ModelConfig(
            model_id="gpt-4o-mini",
            input_price_per_1m=0.15,
            output_price_per_1m=0.60,
        ),
        "gpt-4o": ModelConfig(
            model_id="gpt-4o",
            input_price_per_1m=2.50,
            output_price_per_1m=10.00,
        ),
        "text-embedding-3-small": ModelConfig(
            model_id="text-embedding-3-small",
            input_price_per_1m=0.02,
            output_price_per_1m=0.0,
        ),
    }
    
    # Task → Model mapping
    TASK_ROUTING = {
        # Cheap tasks
        "classification": "gpt-4o-mini",
        "reformulation": "gpt-4o-mini",
        "extraction": "gpt-4o-mini",
        "summarization": "gpt-4o-mini",
        "rag_synthesis": "gpt-4o-mini",
        
        # Expensive tasks
        "complex_reasoning": "gpt-4o",
        "code_generation": "gpt-4o",
        "creative": "gpt-4o",
        
        # Embeddings
        "embedding": "text-embedding-3-small",
    }
    
    def __init__(self, client: OpenAI):
        self.client = client
        self._override_model: Optional[str] = None
    
    def select_model(
        self,
        task: str,
        complexity: str = "normal",
        force_model: Optional[str] = None
    ) -> str:
        """
        Select appropriate model for a task.
        
        Args:
            task: Task identifier (e.g., "classification", "rag_synthesis")
            complexity: "low", "normal", or "high"
            force_model: Override to force a specific model
            
        Returns:
            Model identifier string
        """
        # Explicit override takes precedence
        if force_model:
            return force_model
        
        # Global override (e.g., during testing)
        if self._override_model:
            return self._override_model
        
        # Look up task routing
        base_model = self.TASK_ROUTING.get(task, "gpt-4o-mini")
        
        # Upgrade for high complexity
        if complexity == "high" and base_model == "gpt-4o-mini":
            return "gpt-4o"
        
        # Downgrade for low complexity (even cheaper)
        if complexity == "low" and base_model == "gpt-4o":
            return "gpt-4o-mini"
        
        return base_model
    
    def get_model_config(self, model: str) -> ModelConfig:
        """Get configuration for a model."""
        return self.MODELS.get(model, self.MODELS["gpt-4o-mini"])
    
    def set_global_override(self, model: Optional[str]) -> None:
        """Set a global model override (useful for testing/debugging)."""
        self._override_model = model
    
    def generate(
        self,
        task: str,
        prompt: str,
        complexity: str = "normal",
        **kwargs
    ) -> dict:
        """
        Generate response using appropriate model for task.
        
        Returns dict with response and metadata.
        """
        model = self.select_model(task, complexity)
        config = self.get_model_config(model)
        
        # Use Responses API
        # Source: OpenAI Python SDK docs (developers.openai.com/api/reference/python)
        response = self.client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=kwargs.get("max_output_tokens", config.max_output_tokens),
        )
        
        # Calculate cost
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = (
            (input_tokens / 1_000_000) * config.input_price_per_1m +
            (output_tokens / 1_000_000) * config.output_price_per_1m
        )
        
        return {
            "text": response.output_text,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "task": task,
            "complexity": complexity,
        }


# Usage example
client = OpenAI()
router = ModelRouter(client)

# Classification task → automatically uses gpt-4o-mini
result = router.generate(
    task="classification",
    prompt="Classify this query: 'What were Apple's Q3 earnings?' → financial or general?"
)
print(f"Model: {result['model']}, Cost: ${result['cost_usd']:.6f}")

# Complex reasoning → automatically uses gpt-4o
result = router.generate(
    task="complex_reasoning",
    prompt="Analyze the implications of these contradictory analyst reports..."
)
print(f"Model: {result['model']}, Cost: ${result['cost_usd']:.6f}")
```

### Using with Anthropic

```python
import anthropic
from dataclasses import dataclass
from typing import Optional

@dataclass
class AnthropicModelConfig:
    model_id: str
    input_price_per_1m: float
    output_price_per_1m: float
    max_tokens: int = 4096


class AnthropicModelRouter:
    """Route tasks to appropriate Claude models."""
    
    # Source: Anthropic Pricing docs (platform.claude.com/docs/en/about-claude/pricing)
    MODELS = {
        "claude-haiku-4-5": AnthropicModelConfig(
            model_id="claude-haiku-4-5-20251001",
            input_price_per_1m=1.00,
            output_price_per_1m=5.00,
        ),
        "claude-sonnet-4-6": AnthropicModelConfig(
            model_id="claude-sonnet-4-6-20260101",
            input_price_per_1m=3.00,
            output_price_per_1m=15.00,
        ),
        "claude-opus-4-6": AnthropicModelConfig(
            model_id="claude-opus-4-6-20260101",
            input_price_per_1m=5.00,
            output_price_per_1m=25.00,
        ),
    }
    
    TASK_ROUTING = {
        # Cheap tasks → Haiku
        "classification": "claude-haiku-4-5",
        "extraction": "claude-haiku-4-5",
        "reformulation": "claude-haiku-4-5",
        
        # Moderate tasks → Sonnet
        "rag_synthesis": "claude-sonnet-4-6",
        "summarization": "claude-sonnet-4-6",
        "code_explanation": "claude-sonnet-4-6",
        
        # Complex tasks → Opus
        "complex_reasoning": "claude-opus-4-6",
        "code_generation": "claude-opus-4-6",
    }
    
    def __init__(self):
        self.client = anthropic.Anthropic()
    
    def select_model(self, task: str, complexity: str = "normal") -> str:
        base_model = self.TASK_ROUTING.get(task, "claude-sonnet-4-6")
        
        if complexity == "high":
            # Upgrade path: haiku → sonnet → opus
            if base_model == "claude-haiku-4-5":
                return "claude-sonnet-4-6"
            elif base_model == "claude-sonnet-4-6":
                return "claude-opus-4-6"
        
        if complexity == "low":
            # Downgrade path
            if base_model == "claude-opus-4-6":
                return "claude-sonnet-4-6"
            elif base_model == "claude-sonnet-4-6":
                return "claude-haiku-4-5"
        
        return base_model
    
    def generate(self, task: str, prompt: str, complexity: str = "normal") -> dict:
        model_key = self.select_model(task, complexity)
        config = self.MODELS[model_key]
        
        response = self.client.messages.create(
            model=config.model_id,
            max_tokens=config.max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = (
            (input_tokens / 1_000_000) * config.input_price_per_1m +
            (output_tokens / 1_000_000) * config.output_price_per_1m
        )
        
        return {
            "text": response.content[0].text,
            "model": model_key,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
        }
```

---

## Dynamic Complexity Assessment

Sometimes you don't know the complexity upfront. A short query might require deep reasoning. A long query might be straightforward.

### Approach 1: Heuristic-Based Assessment

```python
import re
from typing import Tuple

class ComplexityAssessor:
    """Assess query complexity using heuristics."""
    
    # Indicators of complexity
    COMPLEX_PATTERNS = [
        r'\b(compare|contrast|analyze|synthesize)\b',
        r'\b(implications|consequences|impact)\b',
        r'\b(why|how come|explain why)\b',
        r'\b(pros and cons|trade-?offs|advantages and disadvantages)\b',
        r'\b(step.by.step|in detail|thoroughly)\b',
        r'\b(multiple|several|various)\b.*\b(factors|aspects|considerations)\b',
    ]
    
    SIMPLE_PATTERNS = [
        r'^(what is|who is|when did|where is)\b',
        r'^(define|list|name)\b',
        r'\b(yes or no|true or false)\b',
        r'^(is|are|does|do|can|will)\b.*\?$',  # Yes/no questions
    ]
    
    def assess(self, query: str) -> Tuple[str, float]:
        """
        Assess query complexity.
        
        Returns:
            Tuple of (complexity_level, confidence)
            complexity_level: "low", "normal", or "high"
            confidence: 0.0 to 1.0
        """
        query_lower = query.lower().strip()
        
        # Check for simple patterns
        simple_score = sum(
            1 for pattern in self.SIMPLE_PATTERNS 
            if re.search(pattern, query_lower)
        )
        
        # Check for complex patterns
        complex_score = sum(
            1 for pattern in self.COMPLEX_PATTERNS 
            if re.search(pattern, query_lower)
        )
        
        # Length as a factor (very long queries often need more reasoning)
        word_count = len(query.split())
        length_factor = min(word_count / 50, 1.0)  # Normalize
        
        # Multiple questions indicator
        question_marks = query.count('?')
        multi_question_factor = min(question_marks / 3, 1.0)
        
        # Calculate composite score
        # Negative = simple, Positive = complex
        composite = (
            complex_score * 2 
            - simple_score * 2 
            + length_factor 
            + multi_question_factor
        )
        
        # Determine level
        if composite <= -1:
            return ("low", min(abs(composite) / 3, 1.0))
        elif composite >= 2:
            return ("high", min(composite / 5, 1.0))
        else:
            return ("normal", 0.5)


# Usage
assessor = ComplexityAssessor()

queries = [
    "What is Apple's stock ticker?",  # Simple
    "Compare Apple and Microsoft's AI strategies, analyzing the implications for their market positions over the next 5 years.",  # Complex
    "Summarize the Q3 earnings report.",  # Normal
]

for query in queries:
    level, confidence = assessor.assess(query)
    print(f"Query: {query[:50]}...")
    print(f"  Complexity: {level} (confidence: {confidence:.2f})")
```

### Approach 2: LLM-Based Assessment (Meta-Routing)

Use a cheap model to assess complexity, then route to the appropriate model:

```python
class LLMComplexityAssessor:
    """Use a cheap LLM to assess query complexity."""
    
    ASSESSMENT_PROMPT = """Assess the complexity of this query. Consider:
- Does it require multi-step reasoning?
- Does it need synthesis across multiple topics?
- Is the answer straightforward or nuanced?

Query: {query}

Respond with ONLY one word: SIMPLE, MODERATE, or COMPLEX"""
    
    def __init__(self, client: OpenAI):
        self.client = client
    
    def assess(self, query: str) -> str:
        """
        Assess query complexity using a cheap model.
        
        Cost: ~$0.00001 per assessment (negligible)
        """
        response = self.client.responses.create(
            model="gpt-4o-mini",  # Use cheapest model for assessment
            input=self.ASSESSMENT_PROMPT.format(query=query),
            max_output_tokens=10,  # We only need one word
        )
        
        result = response.output_text.strip().upper()
        
        # Map to complexity levels
        if "SIMPLE" in result:
            return "low"
        elif "COMPLEX" in result:
            return "high"
        else:
            return "normal"


class SmartRouter:
    """Router that uses LLM to assess complexity before routing."""
    
    def __init__(self, client: OpenAI):
        self.client = client
        self.assessor = LLMComplexityAssessor(client)
        self.router = ModelRouter(client)
    
    def generate(self, task: str, query: str, **kwargs) -> dict:
        # First, assess complexity (cheap)
        complexity = self.assessor.assess(query)
        
        # Then route based on complexity
        return self.router.generate(task, query, complexity=complexity, **kwargs)


# Cost analysis of meta-routing:
# Assessment call: ~100 tokens in, ~5 tokens out
# Cost: ($0.15 * 100 + $0.60 * 5) / 1M = $0.000018
# 
# If 20% of queries are downgraded from gpt-4o to gpt-4o-mini:
# Savings per query: ~$0.01 (typical)
# Net savings: $0.01 * 0.20 - $0.000018 = $0.002 per query
#
# Meta-routing pays for itself if >0.2% of queries change routing.
```

---

## Cost Comparison: Concrete Numbers

Let's make the savings tangible with a Research Assistant example:

### Scenario: 10,000 queries/day

**Without model routing (all GPT-4o):**

```
Per query (average):
- Input: 2,500 tokens (context + query)
- Output: 400 tokens

Cost per query:
- Input: $2.50 × 2500 / 1M = $0.00625
- Output: $10.00 × 400 / 1M = $0.00400
- Total: $0.01025

Daily cost: 10,000 × $0.01025 = $102.50
Monthly cost: $3,075
```

**With intelligent routing:**

```
Query distribution (estimated):
- 60% simple (classification, reformulation, simple RAG): gpt-4o-mini
- 30% moderate (standard RAG synthesis): gpt-4o-mini
- 10% complex (multi-step reasoning): gpt-4o

Simple queries (6,000/day, gpt-4o-mini):
- Cost: ($0.15 × 2500 + $0.60 × 400) / 1M = $0.000615
- Daily: 6,000 × $0.000615 = $3.69

Moderate queries (3,000/day, gpt-4o-mini):
- Cost: $0.000615 per query
- Daily: 3,000 × $0.000615 = $1.85

Complex queries (1,000/day, gpt-4o):
- Cost: $0.01025 per query
- Daily: 1,000 × $0.01025 = $10.25

Total daily cost: $3.69 + $1.85 + $10.25 = $15.79
Monthly cost: $474

SAVINGS: $3,075 - $474 = $2,601/month (85% reduction)
```

### The Key Question: Does Quality Suffer?

The savings mean nothing if quality drops. Here's how to validate:

```python
from dataclasses import dataclass
from typing import List
import json

@dataclass
class QualityTestCase:
    query: str
    expected_contains: List[str]  # Key phrases that should appear
    task_type: str
    

class ModelQualityTester:
    """Test quality across models for routing decisions."""
    
    def __init__(self, client: OpenAI):
        self.client = client
    
    def test_model(
        self,
        model: str,
        test_cases: List[QualityTestCase],
        system_prompt: str
    ) -> dict:
        """
        Run test cases against a model and measure quality.
        """
        results = []
        
        for case in test_cases:
            response = self.client.responses.create(
                model=model,
                input=f"{system_prompt}\n\nQuery: {case.query}",
            )
            
            output = response.output_text.lower()
            
            # Check for expected content
            matches = sum(
                1 for phrase in case.expected_contains 
                if phrase.lower() in output
            )
            score = matches / len(case.expected_contains) if case.expected_contains else 1.0
            
            results.append({
                "query": case.query,
                "task_type": case.task_type,
                "score": score,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            })
        
        # Aggregate results
        avg_score = sum(r["score"] for r in results) / len(results)
        total_input = sum(r["input_tokens"] for r in results)
        total_output = sum(r["output_tokens"] for r in results)
        
        return {
            "model": model,
            "average_score": avg_score,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "results": results,
        }
    
    def compare_models(
        self,
        models: List[str],
        test_cases: List[QualityTestCase],
        system_prompt: str
    ) -> None:
        """Compare quality and cost across models."""
        
        prices = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
        }
        
        print("Model Comparison Results")
        print("=" * 60)
        
        for model in models:
            result = self.test_model(model, test_cases, system_prompt)
            
            price = prices.get(model, {"input": 0, "output": 0})
            cost = (
                (result["total_input_tokens"] / 1_000_000) * price["input"] +
                (result["total_output_tokens"] / 1_000_000) * price["output"]
            )
            
            print(f"\n{model}:")
            print(f"  Quality Score: {result['average_score']:.2%}")
            print(f"  Total Cost: ${cost:.6f}")
            print(f"  Cost per test: ${cost / len(test_cases):.6f}")
            
            # Show per-task breakdown
            by_task = {}
            for r in result["results"]:
                task = r["task_type"]
                if task not in by_task:
                    by_task[task] = []
                by_task[task].append(r["score"])
            
            print(f"  By task type:")
            for task, scores in by_task.items():
                avg = sum(scores) / len(scores)
                print(f"    {task}: {avg:.2%}")


# Example test suite for classification
test_cases = [
    QualityTestCase(
        query="What were Apple's earnings last quarter?",
        expected_contains=["financial"],
        task_type="classification"
    ),
    QualityTestCase(
        query="How do I reset my password?",
        expected_contains=["support", "technical"],
        task_type="classification"
    ),
    QualityTestCase(
        query="Tell me a joke",
        expected_contains=["general", "casual"],
        task_type="classification"
    ),
]

# Run comparison
# client = OpenAI()
# tester = ModelQualityTester(client)
# tester.compare_models(
#     models=["gpt-4o-mini", "gpt-4o"],
#     test_cases=test_cases,
#     system_prompt="Classify the query into one category: financial, support, or general. Respond with just the category."
# )
```

### What You'll Typically Find

For classification and simple extraction tasks:

- **gpt-4o-mini often matches gpt-4o at 95%+ quality**
- The 5% difference rarely matters for routing decisions
- Cost savings: 16x

For RAG synthesis with good context:

- **gpt-4o-mini performs within 5-10% of gpt-4o**
- Context does the heavy lifting; the model just synthesizes
- Cost savings: 16x

For complex multi-step reasoning:

- **gpt-4o shows measurable improvement**
- Worth the cost for queries that genuinely need it
- Reserve for the 10-20% of queries that require it

---

## Cascading Strategy: Try Cheap First

For maximum savings with quality guarantees, use cascading:

```python
from typing import Callable, Optional

class CascadingRouter:
    """
    Try cheap model first; escalate if quality check fails.
    
    This approach:
    - Saves money on easy queries (most queries)
    - Maintains quality on hard queries
    - Costs slightly more than pure routing due to retries
    """
    
    def __init__(self, client: OpenAI):
        self.client = client
    
    def generate_with_cascade(
        self,
        prompt: str,
        quality_check: Callable[[str], bool],
        cheap_model: str = "gpt-4o-mini",
        capable_model: str = "gpt-4o",
        max_output_tokens: int = 1000,
    ) -> dict:
        """
        Generate response, escalating if quality check fails.
        
        Args:
            prompt: The input prompt
            quality_check: Function that returns True if response is acceptable
            cheap_model: First model to try
            capable_model: Fallback model if quality check fails
            
        Returns:
            Dict with response, model used, and metadata
        """
        # Try cheap model first
        response = self.client.responses.create(
            model=cheap_model,
            input=prompt,
            max_output_tokens=max_output_tokens,
        )
        
        output = response.output_text
        
        # Check quality
        if quality_check(output):
            return {
                "text": output,
                "model": cheap_model,
                "escalated": False,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        
        # Quality check failed → escalate to capable model
        response = self.client.responses.create(
            model=capable_model,
            input=prompt,
            max_output_tokens=max_output_tokens,
        )
        
        return {
            "text": response.output_text,
            "model": capable_model,
            "escalated": True,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cheap_model_failed": True,
        }


# Example quality checks

def check_not_empty(response: str) -> bool:
    """Basic check: response isn't empty or just whitespace."""
    return len(response.strip()) > 10

def check_contains_structure(response: str) -> bool:
    """Check that response has expected structure (e.g., for JSON)."""
    try:
        import json
        json.loads(response)
        return True
    except:
        return False

def check_confidence_keywords(response: str) -> bool:
    """Check that response doesn't express uncertainty."""
    uncertainty_markers = [
        "i'm not sure",
        "i don't know",
        "unclear",
        "cannot determine",
        "insufficient information",
    ]
    response_lower = response.lower()
    return not any(marker in response_lower for marker in uncertainty_markers)

def check_minimum_detail(response: str, min_words: int = 50) -> bool:
    """Check that response has minimum detail level."""
    return len(response.split()) >= min_words


# Composite quality check
def create_quality_checker(
    min_length: int = 10,
    require_confidence: bool = True,
    require_json: bool = False,
    min_words: Optional[int] = None,
) -> Callable[[str], bool]:
    """Create a composite quality checker."""
    
    def check(response: str) -> bool:
        if len(response.strip()) < min_length:
            return False
        
        if require_confidence and not check_confidence_keywords(response):
            return False
        
        if require_json and not check_contains_structure(response):
            return False
        
        if min_words and not check_minimum_detail(response, min_words):
            return False
        
        return True
    
    return check


# Usage
# router = CascadingRouter(client)
# 
# result = router.generate_with_cascade(
#     prompt="Analyze the key factors behind Apple's Q3 performance...",
#     quality_check=create_quality_checker(
#         min_length=100,
#         require_confidence=True,
#         min_words=50
#     ),
# )
# 
# if result["escalated"]:
#     print("Query required capable model")
# else:
#     print("Cheap model was sufficient")
```

### Cascading Cost Analysis

```
Assumptions:
- 80% of queries pass quality check with cheap model
- 20% require escalation to capable model
- Average query: 2000 input tokens, 400 output tokens

Without cascading (all gpt-4o):
- Cost: $0.01025 per query

With cascading:
- 80% cheap: $0.000615 per query
- 20% escalated: $0.000615 (failed attempt) + $0.01025 (retry) = $0.01086

Weighted average: 0.8 × $0.000615 + 0.2 × $0.01086 = $0.00266

Savings: $0.01025 - $0.00266 = $0.00759 per query (74% reduction)
```

The cascading approach is slightly less efficient than perfect routing (due to wasted calls), but it provides a quality guarantee you don't get with pure routing.

---

## Key Takeaways

1. **Model selection is your biggest cost lever** — 16x difference between tiers
    
2. **Most tasks don't need your flagship model**:
    
    - Classification: cheap model
    - Reformulation: cheap model
    - RAG synthesis: cheap model (context does the work)
    - Complex reasoning: capable model
3. **Test before assuming** — Run quality comparisons on your actual tasks
    
4. **Cascading provides quality guarantees** — Try cheap first, escalate if needed
    
5. **Dynamic assessment pays for itself** — A $0.00002 assessment call can save $0.01
    
6. **Track actual routing decisions** — Know what percentage of queries use each model
    

---

## What's Next

With model routing in place, the next notes cover:

- **Note 3**: Token budgeting and context management
- **Note 4**: Rate limiting implementation
- **Note 5**: Graceful degradation when limits hit

---

## References

- OpenAI Pricing: https://platform.openai.com/docs/pricing
- OpenAI Python SDK: https://github.com/openai/openai-python
- OpenAI Responses API: https://developers.openai.com/api/docs/quickstart
- Anthropic Pricing: https://platform.claude.com/docs/en/about-claude/pricing