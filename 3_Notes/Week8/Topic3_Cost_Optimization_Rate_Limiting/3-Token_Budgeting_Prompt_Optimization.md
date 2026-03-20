# Note 3: Token Budgeting and Prompt Optimization

## Introduction: Setting Limits Before Execution

Model routing (Note 2) determines _which_ model handles a task. Token budgeting determines _how much_ of that model you use. Together, they form your primary cost control surface.

Token budgeting operates at two levels:

1. **Output budgeting**: Hard cap on generated tokens (`max_output_tokens`)
2. **Input budgeting**: Controlling how much context you send

Both require thinking _before_ the request is made, not after you see the bill.

---

## Output Token Budgeting: The `max_output_tokens` Parameter

### How It Works

`max_output_tokens` (OpenAI Responses API) or `max_tokens` (Anthropic Messages API) sets a hard ceiling on generated output. The model stops generating when it hits this limit.

```python
from openai import OpenAI

client = OpenAI()

# Responses API pattern
# Source: OpenAI Python SDK docs (developers.openai.com/api/reference/python)
response = client.responses.create(
    model="gpt-4o-mini",
    input="Explain quantum computing in detail.",
    max_output_tokens=500,  # Hard cap: stop at 500 tokens
)

# Check if we hit the limit
if response.status == "incomplete":
    if response.incomplete_details.reason == "max_output_tokens":
        print("Response was truncated due to token limit")
```

For Anthropic:

```python
import anthropic

# Source: Anthropic Messages API docs (docs.claude.com/en/api/messages)
client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-6-20260101",
    max_tokens=500,  # Required parameter for Anthropic
    messages=[{"role": "user", "content": "Explain quantum computing in detail."}]
)

# Check stop reason
if response.stop_reason == "max_tokens":
    print("Response was truncated")
elif response.stop_reason == "end_turn":
    print("Response completed naturally")
```

### The Goldilocks Problem

```
Too low:
  max_output_tokens=50 for a summary request
  → Truncated mid-sentence
  → Unusable output
  → Wasted money (paid for input, got nothing useful)

Too high:
  max_output_tokens=4096 for a classification request
  → Model generates verbose explanation when you wanted "financial"
  → 10x the tokens you needed
  → 10x the cost

Just right:
  Task-appropriate limits based on expected output
```

### Task-Based Token Limits

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class TaskTokenConfig:
    """Token configuration for a specific task type."""
    max_output_tokens: int
    expected_output_tokens: int  # For cost estimation
    description: str


# Task-appropriate limits
TASK_TOKEN_CONFIGS = {
    # Minimal output tasks
    "classification": TaskTokenConfig(
        max_output_tokens=20,
        expected_output_tokens=5,
        description="Single word or short phrase"
    ),
    "yes_no": TaskTokenConfig(
        max_output_tokens=10,
        expected_output_tokens=3,
        description="Yes/no with brief reason"
    ),
    "entity_extraction": TaskTokenConfig(
        max_output_tokens=100,
        expected_output_tokens=30,
        description="List of extracted entities"
    ),
    
    # Moderate output tasks
    "query_reformulation": TaskTokenConfig(
        max_output_tokens=100,
        expected_output_tokens=40,
        description="Rewritten query"
    ),
    "summarization_short": TaskTokenConfig(
        max_output_tokens=200,
        expected_output_tokens=100,
        description="Brief summary"
    ),
    "rag_answer_concise": TaskTokenConfig(
        max_output_tokens=300,
        expected_output_tokens=150,
        description="Direct answer with key points"
    ),
    
    # Longer output tasks
    "rag_answer_detailed": TaskTokenConfig(
        max_output_tokens=800,
        expected_output_tokens=400,
        description="Comprehensive answer"
    ),
    "explanation": TaskTokenConfig(
        max_output_tokens=1000,
        expected_output_tokens=500,
        description="Detailed explanation"
    ),
    "code_generation": TaskTokenConfig(
        max_output_tokens=2000,
        expected_output_tokens=800,
        description="Code with comments"
    ),
    
    # Long output tasks
    "report_generation": TaskTokenConfig(
        max_output_tokens=4000,
        expected_output_tokens=2000,
        description="Full report or document"
    ),
    "creative_writing": TaskTokenConfig(
        max_output_tokens=4000,
        expected_output_tokens=2000,
        description="Story, essay, or creative content"
    ),
}


def get_task_config(task: str) -> TaskTokenConfig:
    """Get token config for a task, with sensible default."""
    return TASK_TOKEN_CONFIGS.get(
        task,
        TaskTokenConfig(
            max_output_tokens=500,
            expected_output_tokens=200,
            description="Default task"
        )
    )
```

### Enforcing Output Limits in Prompts

`max_output_tokens` is a hard stop, but it can truncate mid-thought. Better to guide the model to be concise:

```python
# Prompt patterns for controlled output length

CONCISE_PROMPTS = {
    "classification": """Classify the following query into exactly one category.
Respond with ONLY the category name, nothing else.

Categories: financial, technical, general, support

Query: {query}

Category:""",

    "yes_no": """Answer the following question with Yes or No, followed by one sentence of explanation.

Question: {question}

Answer:""",

    "summary_short": """Summarize the following text in 2-3 sentences maximum.

Text: {text}

Summary:""",

    "rag_concise": """Based on the context below, answer the question directly.
Keep your response under 100 words.
If the context doesn't contain the answer, say "Not found in context."

Context:
{context}

Question: {question}

Answer:""",
}


def format_prompt(template_name: str, **kwargs) -> str:
    """Format a concise prompt template."""
    template = CONCISE_PROMPTS.get(template_name)
    if not template:
        raise ValueError(f"Unknown template: {template_name}")
    return template.format(**kwargs)
```

---

## Input Token Budgeting: Controlling Context

Input tokens are cheaper than output tokens, but they add up—especially in RAG systems where you're stuffing thousands of tokens of context into every request.

### The Input Token Budget Mental Model

```
Total input tokens = System prompt
                   + Retrieved chunks
                   + Conversation history (if any)
                   + User query
                   + Tool definitions (if any)
                   + Formatting overhead

Each component is a dial you can turn.
```

### Setting an Input Budget

```python
import tiktoken
from typing import List, Tuple

class InputBudgetManager:
    """Manage input token budgets for requests."""
    
    def __init__(self, model: str = "gpt-4o"):
        self.encoding = tiktoken.encoding_for_model(model)
        
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))
    
    def allocate_budget(
        self,
        total_budget: int,
        system_prompt: str,
        user_query: str,
        tool_overhead: int = 0,
        reserved_for_output: int = 500,
    ) -> int:
        """
        Allocate budget and return tokens available for context.
        
        Args:
            total_budget: Total input token budget
            system_prompt: System prompt text
            user_query: User's query
            tool_overhead: Estimated tokens for tool definitions
            reserved_for_output: Buffer for model's reasoning
            
        Returns:
            Tokens available for RAG context
        """
        system_tokens = self.count_tokens(system_prompt)
        query_tokens = self.count_tokens(user_query)
        
        used = system_tokens + query_tokens + tool_overhead
        available = total_budget - used - reserved_for_output
        
        return max(0, available)
    
    def fit_chunks_to_budget(
        self,
        chunks: List[str],
        budget: int,
        min_chunks: int = 1,
    ) -> Tuple[List[str], int]:
        """
        Select chunks that fit within token budget.
        
        Returns:
            Tuple of (selected_chunks, total_tokens_used)
        """
        selected = []
        total_tokens = 0
        
        for chunk in chunks:
            chunk_tokens = self.count_tokens(chunk)
            
            if total_tokens + chunk_tokens <= budget:
                selected.append(chunk)
                total_tokens += chunk_tokens
            elif len(selected) >= min_chunks:
                # We have enough chunks, stop
                break
            else:
                # Need minimum chunks, truncate this one
                # (In production, you'd want smarter truncation)
                remaining = budget - total_tokens
                if remaining > 50:  # Worth including partial
                    truncated = self._truncate_to_tokens(chunk, remaining)
                    selected.append(truncated)
                    total_tokens += self.count_tokens(truncated)
                break
        
        return selected, total_tokens
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit."""
        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        truncated_tokens = tokens[:max_tokens - 3]  # Leave room for "..."
        return self.encoding.decode(truncated_tokens) + "..."


# Usage example
budget_manager = InputBudgetManager("gpt-4o-mini")

# Calculate available budget for RAG chunks
system_prompt = "You are a helpful assistant that answers questions based on provided context."
user_query = "What were Apple's revenue drivers in Q3 2024?"

available_for_context = budget_manager.allocate_budget(
    total_budget=4000,  # Total input budget
    system_prompt=system_prompt,
    user_query=user_query,
    tool_overhead=0,
    reserved_for_output=500,
)

print(f"Available for context: {available_for_context} tokens")

# Fit chunks to budget
retrieved_chunks = [
    "Apple reported Q3 2024 revenue of $85.8 billion...",  # ~100 tokens
    "iPhone sales remained the largest contributor...",    # ~80 tokens
    "Services revenue grew 14% year-over-year...",         # ~70 tokens
    "Mac sales declined 7% due to...",                     # ~60 tokens
    "Greater China revenue decreased 6.5%...",             # ~50 tokens
]

selected, tokens_used = budget_manager.fit_chunks_to_budget(
    chunks=retrieved_chunks,
    budget=available_for_context,
    min_chunks=2,
)

print(f"Selected {len(selected)} chunks using {tokens_used} tokens")
```

---

## Pre-Request Cost Estimation

Before making a request, estimate its cost and reject or warn if it exceeds budget.

### The Complete Cost Estimator

```python
import tiktoken
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class BudgetAction(Enum):
    PROCEED = "proceed"
    WARN = "warn"
    REJECT = "reject"


@dataclass
class CostEstimate:
    """Pre-request cost estimate."""
    input_tokens: int
    estimated_output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    model: str
    action: BudgetAction
    message: Optional[str] = None


class PreRequestBudgetChecker:
    """
    Check costs before making API requests.
    
    Implements budget enforcement at multiple levels:
    - Per-request budget (reject expensive individual requests)
    - Per-user budget (track cumulative spend)
    - Warning thresholds (alert before limits hit)
    """
    
    # Prices per 1M tokens (update as needed)
    PRICES = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
        "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    }
    
    def __init__(
        self,
        max_cost_per_request: float = 0.10,  # $0.10 max per request
        warn_threshold: float = 0.05,         # Warn above $0.05
        default_model: str = "gpt-4o-mini",
    ):
        self.max_cost_per_request = max_cost_per_request
        self.warn_threshold = warn_threshold
        self.default_model = default_model
        self._encodings = {}
    
    def _get_encoding(self, model: str):
        """Get or create encoding for model."""
        if model not in self._encodings:
            try:
                self._encodings[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback for unknown models
                self._encodings[model] = tiktoken.get_encoding("cl100k_base")
        return self._encodings[model]
    
    def estimate_request_cost(
        self,
        input_text: str,
        model: str,
        expected_output_tokens: int,
    ) -> CostEstimate:
        """
        Estimate cost for a request and determine action.
        
        Args:
            input_text: Full prompt (system + context + query)
            model: Model identifier
            expected_output_tokens: Expected output length
            
        Returns:
            CostEstimate with action (proceed/warn/reject)
        """
        # Count input tokens
        encoding = self._get_encoding(model)
        input_tokens = len(encoding.encode(input_text))
        
        # Get pricing
        prices = self.PRICES.get(model, self.PRICES[self.default_model])
        
        # Calculate costs
        input_cost = (input_tokens / 1_000_000) * prices["input"]
        output_cost = (expected_output_tokens / 1_000_000) * prices["output"]
        total_cost = input_cost + output_cost
        
        # Determine action
        if total_cost > self.max_cost_per_request:
            action = BudgetAction.REJECT
            message = f"Estimated cost ${total_cost:.4f} exceeds limit ${self.max_cost_per_request:.4f}"
        elif total_cost > self.warn_threshold:
            action = BudgetAction.WARN
            message = f"Request cost ${total_cost:.4f} is above warning threshold"
        else:
            action = BudgetAction.PROCEED
            message = None
        
        return CostEstimate(
            input_tokens=input_tokens,
            estimated_output_tokens=expected_output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            model=model,
            action=action,
            message=message,
        )
    
    def check_and_execute(
        self,
        client,  # OpenAI client
        input_text: str,
        model: str,
        expected_output_tokens: int,
        max_output_tokens: int,
        force_execute: bool = False,
    ) -> dict:
        """
        Estimate cost, check budget, then execute if allowed.
        
        Args:
            client: OpenAI client
            input_text: Full prompt
            model: Model to use
            expected_output_tokens: Expected output (for estimation)
            max_output_tokens: Hard limit for actual request
            force_execute: Execute even if over budget (for admin override)
            
        Returns:
            Dict with response or error
        """
        # Estimate cost
        estimate = self.estimate_request_cost(
            input_text=input_text,
            model=model,
            expected_output_tokens=expected_output_tokens,
        )
        
        # Check action
        if estimate.action == BudgetAction.REJECT and not force_execute:
            return {
                "success": False,
                "error": "budget_exceeded",
                "message": estimate.message,
                "estimate": estimate,
            }
        
        if estimate.action == BudgetAction.WARN:
            # Log warning but proceed
            print(f"WARNING: {estimate.message}")
        
        # Execute request
        response = client.responses.create(
            model=model,
            input=input_text,
            max_output_tokens=max_output_tokens,
        )
        
        # Calculate actual cost
        actual_input = response.usage.input_tokens
        actual_output = response.usage.output_tokens
        prices = self.PRICES.get(model, self.PRICES[self.default_model])
        actual_cost = (
            (actual_input / 1_000_000) * prices["input"] +
            (actual_output / 1_000_000) * prices["output"]
        )
        
        return {
            "success": True,
            "response": response.output_text,
            "estimate": estimate,
            "actual": {
                "input_tokens": actual_input,
                "output_tokens": actual_output,
                "cost": actual_cost,
            },
        }


# Usage
checker = PreRequestBudgetChecker(
    max_cost_per_request=0.05,  # $0.05 max
    warn_threshold=0.02,        # Warn above $0.02
)

# Example: Check before executing
system_prompt = "You are a financial analyst assistant."
context = "Apple reported Q3 revenue of $85.8 billion..." * 10  # Simulate large context
query = "What were the revenue drivers?"

full_prompt = f"{system_prompt}\n\nContext:\n{context}\n\nQuery: {query}"

estimate = checker.estimate_request_cost(
    input_text=full_prompt,
    model="gpt-4o-mini",
    expected_output_tokens=300,
)

print(f"Estimated cost: ${estimate.total_cost:.4f}")
print(f"Action: {estimate.action.value}")
if estimate.message:
    print(f"Message: {estimate.message}")
```

### User Budget Management

```python
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict

class UserBudgetManager:
    """Track and enforce per-user budgets."""
    
    def __init__(
        self,
        daily_budget_per_user: float = 1.00,  # $1/day per user
        monthly_budget_per_user: float = 20.00,  # $20/month per user
    ):
        self.daily_budget = daily_budget_per_user
        self.monthly_budget = monthly_budget_per_user
        
        # In production, use Redis or a database
        self.daily_spend: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.monthly_spend: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    
    def _get_day_key(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")
    
    def _get_month_key(self) -> str:
        return datetime.now().strftime("%Y-%m")
    
    def get_remaining_budget(self, user_id: str) -> dict:
        """Get user's remaining budget."""
        day_key = self._get_day_key()
        month_key = self._get_month_key()
        
        daily_spent = self.daily_spend[user_id][day_key]
        monthly_spent = self.monthly_spend[user_id][month_key]
        
        return {
            "daily_remaining": max(0, self.daily_budget - daily_spent),
            "monthly_remaining": max(0, self.monthly_budget - monthly_spent),
            "daily_spent": daily_spent,
            "monthly_spent": monthly_spent,
        }
    
    def can_afford(self, user_id: str, estimated_cost: float) -> tuple[bool, str]:
        """Check if user can afford a request."""
        remaining = self.get_remaining_budget(user_id)
        
        if estimated_cost > remaining["daily_remaining"]:
            return False, f"Daily budget exceeded. Remaining: ${remaining['daily_remaining']:.4f}"
        
        if estimated_cost > remaining["monthly_remaining"]:
            return False, f"Monthly budget exceeded. Remaining: ${remaining['monthly_remaining']:.4f}"
        
        return True, "OK"
    
    def record_spend(self, user_id: str, cost: float) -> None:
        """Record actual spend for a user."""
        day_key = self._get_day_key()
        month_key = self._get_month_key()
        
        self.daily_spend[user_id][day_key] += cost
        self.monthly_spend[user_id][month_key] += cost
    
    def get_user_status(self, user_id: str) -> dict:
        """Get detailed status for a user."""
        remaining = self.get_remaining_budget(user_id)
        
        return {
            "user_id": user_id,
            "daily": {
                "budget": self.daily_budget,
                "spent": remaining["daily_spent"],
                "remaining": remaining["daily_remaining"],
                "percent_used": (remaining["daily_spent"] / self.daily_budget) * 100,
            },
            "monthly": {
                "budget": self.monthly_budget,
                "spent": remaining["monthly_spent"],
                "remaining": remaining["monthly_remaining"],
                "percent_used": (remaining["monthly_spent"] / self.monthly_budget) * 100,
            },
        }


# Usage
budget_mgr = UserBudgetManager(
    daily_budget_per_user=1.00,
    monthly_budget_per_user=20.00,
)

user_id = "user_123"

# Check before request
estimated_cost = 0.05
can_afford, message = budget_mgr.can_afford(user_id, estimated_cost)

if can_afford:
    # Make request...
    actual_cost = 0.048
    budget_mgr.record_spend(user_id, actual_cost)
else:
    print(f"Request blocked: {message}")

# Check status
status = budget_mgr.get_user_status(user_id)
print(f"Daily budget: {status['daily']['percent_used']:.1f}% used")
```

---

## Prompt Optimization Techniques

Every token in your prompt costs money. Shorter prompts = lower cost.

### System Prompt Optimization

```python
# BEFORE: Verbose system prompt (187 tokens)
VERBOSE_SYSTEM_PROMPT = """
You are a highly skilled and knowledgeable financial analyst assistant. Your role is 
to help users understand complex financial information by providing clear, accurate, 
and insightful analysis. When answering questions, you should:

1. Always base your answers on the provided context
2. Be precise and avoid speculation
3. If information is not available in the context, clearly state that
4. Use professional but accessible language
5. Provide specific numbers and data when available
6. Structure your responses clearly with appropriate formatting
7. Consider multiple perspectives when analyzing financial data

Remember that your responses should be helpful, accurate, and professional at all times.
"""

# AFTER: Concise system prompt (47 tokens)
CONCISE_SYSTEM_PROMPT = """You are a financial analyst. Answer based on provided context only. 
Be precise, cite numbers, state when information is unavailable."""

# Token savings: 187 - 47 = 140 tokens per request
# At GPT-4o rates ($2.50/1M): 140 tokens × 10,000 requests = $3.50 saved
# At GPT-4o-mini rates ($0.15/1M): 140 tokens × 10,000 requests = $0.21 saved
```

### Instruction Optimization

```python
# Verbose vs concise instruction patterns

INSTRUCTIONS = {
    # Classification
    "verbose": """
    Please analyze the following query and determine which category it belongs to.
    The available categories are: financial, technical, general, and support.
    After careful consideration, please respond with just the category name.
    """,
    "concise": "Classify as: financial, technical, general, or support. Reply with category only.",
    
    # RAG synthesis
    "verbose": """
    Based on the context information provided below, please answer the user's question.
    Make sure to only use information from the context and do not make up any facts.
    If the context does not contain relevant information, please indicate that.
    Your response should be comprehensive but focused on what the user asked.
    """,
    "concise": "Answer from context only. Say 'not found' if context lacks the answer.",
    
    # Summarization
    "verbose": """
    Please provide a summary of the following text. The summary should capture the
    main points and key information while being significantly shorter than the original.
    Aim for a summary that is about 20% of the original length.
    """,
    "concise": "Summarize in 2-3 sentences.",
}
```

### Few-Shot Example Optimization

```python
# Few-shot examples consume tokens. Optimize them.

# BEFORE: Verbose examples (estimated 400 tokens)
VERBOSE_FEW_SHOT = """
Example 1:
Query: "What was Microsoft's revenue in the last quarter?"
Classification: financial
Reasoning: This query is asking about financial metrics (revenue) for a company,
which makes it a financial query.

Example 2:
Query: "How do I connect to the VPN?"
Classification: technical
Reasoning: This query is asking about technical procedures related to IT 
infrastructure, making it a technical support question.

Example 3:
Query: "What's the weather like today?"
Classification: general
Reasoning: This is a general knowledge question not related to our specific
domain, so it falls into the general category.
"""

# AFTER: Minimal examples (estimated 60 tokens)
CONCISE_FEW_SHOT = """Examples:
"Microsoft revenue last quarter?" → financial
"How to connect to VPN?" → technical
"Weather today?" → general"""

# Token savings: ~340 tokens per request
```

### Formatting Optimization

```python
# Format matters for token efficiency

# BEFORE: XML-style formatting (more tokens)
XML_FORMAT = """
<context>
<chunk id="1">
<content>Apple reported Q3 2024 revenue of $85.8 billion.</content>
<source>earnings_report_q3_2024.pdf</source>
</chunk>
<chunk id="2">
<content>iPhone sales contributed 46% of total revenue.</content>
<source>earnings_report_q3_2024.pdf</source>
</chunk>
</context>
"""

# AFTER: Minimal formatting (fewer tokens)
MINIMAL_FORMAT = """Context:
[1] Apple reported Q3 2024 revenue of $85.8 billion. (earnings_report_q3_2024.pdf)
[2] iPhone sales contributed 46% of total revenue. (earnings_report_q3_2024.pdf)"""

# Use XML when you need structured extraction
# Use minimal formatting for simple context injection
```

---

## Context Optimization: The RAG Cost Dial

RAG systems stuff retrieved chunks into the prompt. This is often your largest input cost driver.

### Strategy 1: Fewer Chunks

```python
# Instead of retrieving 10 chunks, retrieve 5
# Quality impact: Moderate (if top chunks are most relevant)
# Cost reduction: 50%

def retrieve_with_budget(
    query: str,
    retriever,
    max_chunks: int = 5,  # Reduced from 10
    min_relevance_score: float = 0.7,  # Only include relevant chunks
) -> list:
    """Retrieve chunks with budget awareness."""
    
    # Get more candidates than needed
    candidates = retriever.retrieve(query, top_k=max_chunks * 2)
    
    # Filter by relevance
    relevant = [c for c in candidates if c.score >= min_relevance_score]
    
    # Take top N
    return relevant[:max_chunks]
```

### Strategy 2: Shorter Chunks

```python
# Smaller chunk size during indexing = smaller chunks at query time

# Standard: 500 tokens per chunk
# Budget-conscious: 200-300 tokens per chunk

# Trade-off:
# - Smaller chunks: Less context per chunk, might miss surrounding info
# - Larger chunks: More complete context, but higher cost

CHUNK_SIZE_CONFIGS = {
    "budget": {
        "chunk_size": 200,
        "chunk_overlap": 30,
        "description": "Minimal chunks, lowest cost"
    },
    "balanced": {
        "chunk_size": 400,
        "chunk_overlap": 50,
        "description": "Good balance of context and cost"
    },
    "quality": {
        "chunk_size": 600,
        "chunk_overlap": 100,
        "description": "More context, higher cost"
    },
}
```

### Strategy 3: Context Summarization

```python
def summarize_context_for_budget(
    chunks: list[str],
    token_budget: int,
    summarizer_client,
) -> str:
    """
    When chunks exceed budget, summarize them instead.
    
    Trade-off:
    - Pro: Fits within budget, preserves key information
    - Con: Additional API call for summarization, some detail loss
    """
    import tiktoken
    
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    full_context = "\n\n".join(chunks)
    context_tokens = len(encoding.encode(full_context))
    
    if context_tokens <= token_budget:
        return full_context
    
    # Summarize to fit budget
    summary_prompt = f"""Summarize the following context into key facts and figures.
Keep the summary under {token_budget // 2} tokens.
Preserve specific numbers, dates, and names.

Context:
{full_context}

Summary:"""
    
    response = summarizer_client.responses.create(
        model="gpt-4o-mini",  # Use cheap model for summarization
        input=summary_prompt,
        max_output_tokens=token_budget // 2,
    )
    
    return response.output_text


# Cost analysis of summarization approach:
# 
# Direct context (5 chunks × 400 tokens = 2000 tokens):
#   - Input cost: $2.50 × 2000 / 1M = $0.005 (with GPT-4o)
#
# Summarized context:
#   - Summarization call (cheap model): ~$0.0003
#   - Final call with 500 token summary: $2.50 × 500 / 1M = $0.00125
#   - Total: ~$0.0016
#
# Savings: $0.005 - $0.0016 = $0.0034 per request (68% reduction)
# 
# But: Added latency from summarization call
# Best for: Large contexts where direct inclusion is expensive
```

### Strategy 4: Intelligent Truncation

```python
def truncate_chunk_intelligently(
    chunk: str,
    max_tokens: int,
    encoding,
) -> str:
    """
    Truncate a chunk while preserving meaning.
    
    Strategies:
    1. Keep first and last portions (intro + conclusion)
    2. Keep sentences, don't cut mid-sentence
    3. Preserve key patterns (numbers, names, dates)
    """
    tokens = encoding.encode(chunk)
    
    if len(tokens) <= max_tokens:
        return chunk
    
    # Strategy: Keep first 70% and last 20% of budget
    first_portion = int(max_tokens * 0.7)
    last_portion = int(max_tokens * 0.2)
    middle_marker = 5  # Tokens for "..."
    
    first_tokens = tokens[:first_portion]
    last_tokens = tokens[-last_portion:]
    
    # Decode and combine
    first_text = encoding.decode(first_tokens)
    last_text = encoding.decode(last_tokens)
    
    # Try to end first part at sentence boundary
    sentence_endings = ['. ', '.\n', '! ', '? ']
    for ending in sentence_endings:
        idx = first_text.rfind(ending)
        if idx > len(first_text) * 0.5:  # At least halfway through
            first_text = first_text[:idx + 1]
            break
    
    # Try to start last part at sentence boundary
    for ending in sentence_endings:
        idx = last_text.find(ending)
        if idx != -1 and idx < len(last_text) * 0.5:
            last_text = last_text[idx + 2:]
            break
    
    return f"{first_text}\n[...]\n{last_text}"
```

---

## The Context-Quality Trade-off

More context generally means better answers, but at higher cost. Finding the minimum viable context is key.

### Measuring the Trade-off

```python
from dataclasses import dataclass
from typing import List

@dataclass
class QualityCostPoint:
    """Single measurement of quality vs cost."""
    num_chunks: int
    context_tokens: int
    cost_per_request: float
    quality_score: float  # 0-1, from evaluation
    

def find_optimal_context_level(
    test_queries: List[dict],  # {"query": str, "expected_answer": str}
    retriever,
    generator_client,
    evaluator,
    chunk_levels: List[int] = [1, 3, 5, 7, 10],
) -> QualityCostPoint:
    """
    Empirically find the optimal number of chunks.
    
    Returns the configuration with best quality-per-dollar.
    """
    results = []
    
    for num_chunks in chunk_levels:
        quality_scores = []
        costs = []
        
        for test in test_queries:
            # Retrieve chunks
            chunks = retriever.retrieve(test["query"], top_k=num_chunks)
            
            # Generate answer
            context = "\n\n".join([c.text for c in chunks])
            # ... generate and calculate cost ...
            
            # Evaluate quality
            score = evaluator.score(
                generated_answer=generated,
                expected_answer=test["expected_answer"],
            )
            quality_scores.append(score)
            costs.append(request_cost)
        
        avg_quality = sum(quality_scores) / len(quality_scores)
        avg_cost = sum(costs) / len(costs)
        
        results.append(QualityCostPoint(
            num_chunks=num_chunks,
            context_tokens=sum(len(c.text.split()) for c in chunks) * 1.3,  # Rough
            cost_per_request=avg_cost,
            quality_score=avg_quality,
        ))
    
    # Find best quality-per-dollar
    # (You might weight this differently based on priorities)
    for r in results:
        r.efficiency = r.quality_score / r.cost_per_request
    
    best = max(results, key=lambda r: r.efficiency)
    
    # Print analysis
    print("Context Level Analysis:")
    print("-" * 60)
    for r in results:
        print(f"Chunks: {r.num_chunks:2d} | Quality: {r.quality_score:.2f} | "
              f"Cost: ${r.cost_per_request:.4f} | Efficiency: {r.efficiency:.1f}")
    print(f"\nOptimal: {best.num_chunks} chunks")
    
    return best
```

### Typical Findings

```
Context Level Analysis:
------------------------------------------------------------
Chunks:  1 | Quality: 0.65 | Cost: $0.0008 | Efficiency: 812.5
Chunks:  3 | Quality: 0.82 | Cost: $0.0015 | Efficiency: 546.7
Chunks:  5 | Quality: 0.89 | Cost: $0.0022 | Efficiency: 404.5
Chunks:  7 | Quality: 0.91 | Cost: $0.0029 | Efficiency: 313.8
Chunks: 10 | Quality: 0.92 | Cost: $0.0038 | Efficiency: 242.1

Optimal: 3 chunks

Insight: Going from 5 to 10 chunks increases cost by 73% 
         but only improves quality by 3%.
```

---

## Putting It All Together: Budget-Aware Request

```python
from openai import OpenAI
import tiktoken

class BudgetAwareRequester:
    """
    Complete budget-aware request handling.
    
    Combines:
    - Input budget allocation
    - Pre-request cost estimation
    - Output token limits
    - User budget tracking
    """
    
    def __init__(
        self,
        client: OpenAI,
        max_cost_per_request: float = 0.10,
        default_model: str = "gpt-4o-mini",
    ):
        self.client = client
        self.max_cost = max_cost_per_request
        self.default_model = default_model
        self.encoding = tiktoken.encoding_for_model(default_model)
        
        self.prices = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
        }
    
    def execute_with_budget(
        self,
        system_prompt: str,
        user_query: str,
        context_chunks: list[str],
        task_type: str,
        model: str = None,
        user_budget_remaining: float = None,
    ) -> dict:
        """
        Execute a request with full budget awareness.
        
        1. Estimate cost
        2. Fit context to budget if needed
        3. Check user budget
        4. Execute with appropriate max_tokens
        5. Return result with cost tracking
        """
        model = model or self.default_model
        task_config = get_task_config(task_type)
        
        # Step 1: Build initial prompt
        context = "\n\n".join(context_chunks)
        full_prompt = f"{system_prompt}\n\nContext:\n{context}\n\nQuery: {user_query}"
        
        # Step 2: Estimate cost
        input_tokens = len(self.encoding.encode(full_prompt))
        output_tokens = task_config.expected_output_tokens
        
        prices = self.prices.get(model, self.prices[self.default_model])
        estimated_cost = (
            (input_tokens / 1_000_000) * prices["input"] +
            (output_tokens / 1_000_000) * prices["output"]
        )
        
        # Step 3: Check against limits
        if estimated_cost > self.max_cost:
            # Try to reduce context
            reduced_chunks = self._reduce_context_to_budget(
                context_chunks=context_chunks,
                system_prompt=system_prompt,
                user_query=user_query,
                target_cost=self.max_cost * 0.8,  # Leave some buffer
                model=model,
                expected_output=output_tokens,
            )
            
            if reduced_chunks is None:
                return {
                    "success": False,
                    "error": "budget_exceeded",
                    "message": f"Cannot fit request within ${self.max_cost:.4f} budget",
                    "estimated_cost": estimated_cost,
                }
            
            context_chunks = reduced_chunks
            context = "\n\n".join(context_chunks)
            full_prompt = f"{system_prompt}\n\nContext:\n{context}\n\nQuery: {user_query}"
            input_tokens = len(self.encoding.encode(full_prompt))
            estimated_cost = (
                (input_tokens / 1_000_000) * prices["input"] +
                (output_tokens / 1_000_000) * prices["output"]
            )
        
        # Step 4: Check user budget
        if user_budget_remaining is not None and estimated_cost > user_budget_remaining:
            return {
                "success": False,
                "error": "user_budget_exceeded",
                "message": f"Estimated cost ${estimated_cost:.4f} exceeds your remaining budget ${user_budget_remaining:.4f}",
                "estimated_cost": estimated_cost,
            }
        
        # Step 5: Execute
        response = self.client.responses.create(
            model=model,
            input=full_prompt,
            max_output_tokens=task_config.max_output_tokens,
        )
        
        # Step 6: Calculate actual cost
        actual_input = response.usage.input_tokens
        actual_output = response.usage.output_tokens
        actual_cost = (
            (actual_input / 1_000_000) * prices["input"] +
            (actual_output / 1_000_000) * prices["output"]
        )
        
        return {
            "success": True,
            "response": response.output_text,
            "truncated": response.status == "incomplete",
            "usage": {
                "input_tokens": actual_input,
                "output_tokens": actual_output,
                "estimated_cost": estimated_cost,
                "actual_cost": actual_cost,
            },
            "context_chunks_used": len(context_chunks),
        }
    
    def _reduce_context_to_budget(
        self,
        context_chunks: list[str],
        system_prompt: str,
        user_query: str,
        target_cost: float,
        model: str,
        expected_output: int,
    ) -> list[str] | None:
        """Reduce context until it fits budget."""
        prices = self.prices.get(model, self.prices[self.default_model])
        
        # Calculate max input tokens for target cost
        output_cost = (expected_output / 1_000_000) * prices["output"]
        max_input_cost = target_cost - output_cost
        max_input_tokens = int(max_input_cost / prices["input"] * 1_000_000)
        
        # Calculate overhead
        overhead = system_prompt + "\n\nContext:\n\n\nQuery: " + user_query
        overhead_tokens = len(self.encoding.encode(overhead))
        available_for_context = max_input_tokens - overhead_tokens
        
        if available_for_context < 100:
            return None
        
        # Fit chunks to available budget
        selected = []
        used_tokens = 0
        
        for chunk in context_chunks:
            chunk_tokens = len(self.encoding.encode(chunk))
            if used_tokens + chunk_tokens <= available_for_context:
                selected.append(chunk)
                used_tokens += chunk_tokens
            else:
                break
        
        if not selected:
            return None
        
        return selected
```

---

## Key Takeaways

1. **Set `max_output_tokens` based on task**, not model default:
    
    - Classification: 10-20 tokens
    - Summary: 100-300 tokens
    - Detailed answer: 500-1000 tokens
2. **Estimate cost before executing** — reject or warn if over budget
    
3. **Optimize prompts ruthlessly**:
    
    - Shorter system prompts (every token counts)
    - Minimal few-shot examples
    - Efficient formatting
4. **Context is your biggest input cost dial**:
    
    - Fewer chunks (5 vs 10)
    - Shorter chunks (300 vs 500 tokens)
    - Summarize instead of including verbatim
5. **Measure the context-quality trade-off** — find minimum viable context
    
6. **Track user budgets** — enforce limits before hitting surprise bills
    

---

## What's Next

With token budgeting in place, the next notes cover:

- **Note 4**: Rate limiting implementation
- **Note 5**: Graceful degradation when limits hit

---

## References

- OpenAI Responses API: https://developers.openai.com/api/docs/quickstart
- OpenAI Reasoning Models: https://platform.openai.com/docs/guides/reasoning
- Anthropic Messages API: https://docs.claude.com/en/api/messages
- tiktoken Library: https://github.com/openai/tiktoken