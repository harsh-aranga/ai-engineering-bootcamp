# Week 2: Foundations — LLM Usage Patterns

> **Track:** Foundational (Sequential) **Time:** 2 hours/day **Goal:** Build reliable, production-grade patterns for using LLMs — handling failures, managing limits, and getting structured data out consistently.

---

## Overview

| Days | Topic                     | Output                    |
| ---- | ------------------------- | ------------------------- |
| 1-2  | LLM API Patterns          | Mini Challenge complete   |
| 3-4  | Context Window Management | Mini Challenge complete   |
| 5-6  | Structured Outputs        | Mini Challenge complete   |
| 7    | Mini Build                | Robust LLM Client Wrapper |

---

## Days 1-2: LLM API Patterns

### Why This Matters

In tutorials, you call the API and it works. In production:

- APIs fail (rate limits, timeouts, server errors)
- Users wait for responses (streaming improves perceived latency)
- Costs spike if you don't handle retries correctly (retry storms)
- Your app crashes at 2 AM because you didn't handle edge cases

Every RAG system and every Agent makes LLM calls. If your API layer is fragile, everything breaks.

### What to Learn

**Core Concepts:**

- Sync vs. async API calls
- Streaming responses (why, when, how)
- HTTP status codes you'll encounter (429 rate limit, 500 server error, 400 bad request)
- Retry strategies (exponential backoff, jitter)
- Timeout handling
- API response structure (choices, usage, finish_reason)

**Practical Skills:**

- Implement streaming that handles partial chunks
- Build retry logic that doesn't make things worse
- Handle rate limits gracefully (wait and retry vs. fail fast)
- Log API calls for debugging without logging sensitive data

### Resources

**Primary:**

- OpenAI API Reference: https://platform.openai.com/docs/api-reference/chat/create
- OpenAI Error Handling Guide: https://platform.openai.com/docs/guides/error-codes
- Anthropic API Errors: https://docs.anthropic.com/en/api/errors
- `tenacity` library (Python retries): https://tenacity.readthedocs.io/

**Secondary:**

- Search: "exponential backoff with jitter explained"
- Search: "python async openai streaming"

### Day 1 Tasks (1 hour learning, 1 hour experimenting)

**Hour 1 — Learn:**

1. Read OpenAI API reference for chat completions — focus on parameters and response structure (20 min)
2. Read OpenAI error codes page — understand each error type (15 min)
3. Read about `tenacity` library basics — retry decorators (15 min)
4. Understand `finish_reason` values: "stop", "length", "content_filter" — what each means (10 min)

**Hour 2 — Experiment:**

1. Make a basic API call, inspect the full response object (not just the content)
2. Print `usage` field — see prompt_tokens, completion_tokens, total_tokens
3. Implement basic streaming — print chunks as they arrive
4. Force an error: send invalid model name, exceed max_tokens, send empty messages — see what errors look like
5. Implement a simple retry with `tenacity` — test by simulating failures

### Day 2 Tasks (1 hour challenge, 1 hour reflection)

**Hour 1 — Mini Challenge:**

Build a function `robust_chat_completion()` that:

```python
def robust_chat_completion(
    messages: list,
    model: str = "gpt-4o-mini",
    stream: bool = False,
    max_retries: int = 3
) -> dict | Generator:
    """
    Makes a chat completion call with:
    - Automatic retries with exponential backoff for transient errors
    - Proper handling of rate limits (wait and retry)
    - Timeout handling
    - Streaming support
    - Returns structured response with content + usage stats
    """
    pass
```

**Success Criteria:**

- [ ] Retries on 429 (rate limit) with exponential backoff
- [ ] Retries on 500/502/503 (server errors) up to max_retries
- [ ] Does NOT retry on 400 (bad request) — that's your bug, not transient
- [ ] Streaming mode yields chunks as they arrive
- [ ] Non-streaming mode returns: `{"content": "...", "usage": {...}, "finish_reason": "..."}`
- [ ] Logs retries (print is fine) so you know when retries happen
- [ ] Has a timeout (30 seconds default) — doesn't hang forever
- [ ] Tested with at least 3 scenarios: success, simulated retry, simulated failure

**Hour 2 — Solidify + Ponder**

### 5 Things to Ponder

1. You implement retry with exponential backoff: wait 1s, 2s, 4s, 8s. But 100 users hit rate limit at the same time. They all retry at 1s, 2s, 4s... causing another spike. What's the fix? (Hint: jitter)
    
2. Your streaming response stops mid-sentence. `finish_reason` is "length". What happened, and how should your code handle this gracefully for the user?
    
3. You're building a chatbot. User sends a message, you call the API, it fails after 3 retries. What should the user see? "Error occurred" is lazy — what's the right UX?
    
4. Rate limit is 10,000 tokens per minute. Your app has 50 concurrent users. Each request averages 500 tokens. Will you hit the rate limit? How would you architect around this?
    
5. You log all API calls for debugging. But messages contain user data. How do you log enough to debug without violating privacy or creating security risks?
    

---

## Days 3-4: Context Window Management

### Why This Matters

Context window = max tokens for input + output combined. When you exceed it:

- API returns an error (best case)
- Response gets truncated (worse case)
- Important context gets lost (worst case — wrong answers)

Every long conversation, every RAG system stuffing documents, every agent with history — all hit context limits. Managing this is the difference between "works in demo" and "works in production."

### What to Learn

**Core Concepts:**

- Context window sizes by model (GPT-4o: 128K, Claude 3.5: 200K, GPT-4o-mini: 128K)
- Input vs. output token budgeting
- "Lost in the middle" problem — models pay less attention to middle content
- Truncation strategies (from start, from end, smart summarization)
- Sliding window approaches
- Message prioritization (system prompt > recent messages > old messages)

**Practical Skills:**

- Calculate remaining tokens before API call
- Implement truncation that preserves important context
- Build conversation buffers with automatic pruning
- Handle "context full" scenarios gracefully

### Resources

**Primary:**

- OpenAI Models page (context window sizes): https://platform.openai.com/docs/models
- Anthropic Model Comparison: https://docs.anthropic.com/en/docs/about-claude/models
- Your Week 1 tokenization code — you'll use it here

**Secondary:**

- Search: "lost in the middle LLM paper" — understand the attention problem
- Search: "conversation memory management LLM" — patterns others use

### Day 3 Tasks (1 hour learning, 1 hour experimenting)

**Hour 1 — Learn:**

1. Review context window sizes for major models — make a reference table (15 min)
2. Read about "lost in the middle" problem — understand why position matters (20 min)
3. Think through: System prompt (500 tokens) + User message (?) + Retrieved docs (?) + Response (?) = must fit in context. How do you budget? (15 min)
4. Research conversation memory patterns: buffer memory, summary memory, sliding window (10 min)

**Hour 2 — Experiment:**

1. Using your Week 1 tokenizer, create a function `count_messages_tokens(messages)` that counts total tokens in a conversation
2. Simulate a long conversation (20+ messages). Calculate total tokens. Does it fit in GPT-4o-mini's context?
3. Implement basic truncation: if over limit, remove oldest messages until under limit
4. Test: Start with messages that fit, keep adding until truncation kicks in
5. Edge case: What if a single message exceeds the limit? How should you handle it?

### Day 4 Tasks (1 hour challenge, 1 hour reflection)

**Hour 1 — Mini Challenge:**

Build a `ConversationManager` class:

```python
class ConversationManager:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        max_context_usage: float = 0.7,  # Reserve 30% for response
        system_prompt: str = None
    ):
        """
        Manages conversation history within context limits.
        """
        pass
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message, auto-truncate if needed."""
        pass
    
    def get_messages(self) -> list:
        """Return messages that fit in context budget."""
        pass
    
    def get_remaining_tokens(self) -> int:
        """Return tokens available for response."""
        pass
    
    def clear(self) -> None:
        """Clear conversation history (keep system prompt)."""
        pass
```

**Success Criteria:**

- [ ] Correctly tracks token count of all messages
- [ ] System prompt is never truncated (always preserved)
- [ ] When over budget, removes oldest non-system messages first
- [ ] Respects `max_context_usage` — leaves room for response
- [ ] `get_remaining_tokens()` returns accurate count
- [ ] Handles edge case: single user message too large (truncate message itself or error gracefully)
- [ ] Tested with conversation that grows from 0 to over-limit

**Hour 2 — Solidify + Ponder**

### 5 Things to Ponder

1. You truncate old messages to fit context. But the user references something from a truncated message: "As I mentioned earlier..." Now your AI has no idea what they mentioned. How could you handle this better than simple truncation?
    
2. Your system prompt is 2000 tokens (detailed instructions). Your context window is 4096 (small model). After system prompt, you have 2096 tokens. If you reserve 500 for response, only 1596 for conversation. That's maybe 5-6 exchanges. How would you redesign for longer conversations?
    
3. "Lost in the middle" — models pay more attention to start and end. You're stuffing 5 retrieved documents into the middle of your prompt. What are the implications? How might you structure the prompt to mitigate this?
    
4. You're building a customer support bot. Conversation history is important — customer shouldn't have to repeat themselves. But context is limited. When do you summarize old messages vs. truncate vs. store externally? What's your decision framework?
    
5. Two approaches: (A) Always use max context, stuff as much as possible. (B) Use minimum necessary context, be selective. What are the tradeoffs of each? Which would you default to and why?
    

---

## Days 5-6: Structured Outputs

### Why This Matters

LLMs output text. Your code needs data. The gap between "text that looks like JSON" and "valid parseable JSON" causes:

- Parser errors at runtime
- Try/catch hell with regex fallbacks
- Inconsistent field names ("name" vs "Name" vs "user_name")
- Missing fields that crash downstream code

Both RAG (extracting info from documents) and Agents (parsing tool responses) need reliable structured outputs. This is the bridge between "LLM magic" and "working software."

### What to Learn

**Core Concepts:**

- JSON mode (forces valid JSON, but not schema-validated)
- Response format parameter (OpenAI's structured outputs)
- Function calling / Tool use (schema-defined inputs and outputs)
- Pydantic for schema definition and validation
- When to use which approach

**Practical Skills:**

- Get valid JSON every time (not 95% of the time)
- Define schemas that the model follows
- Handle validation errors gracefully
- Use function calling for structured extraction

### Resources

**Primary:**

- OpenAI JSON Mode: https://platform.openai.com/docs/guides/json-mode
- OpenAI Structured Outputs: https://platform.openai.com/docs/guides/structured-outputs
- OpenAI Function Calling: https://platform.openai.com/docs/guides/function-calling
- Pydantic docs: https://docs.pydantic.dev/latest/

**Secondary:**

- Anthropic Tool Use: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
- Search: "pydantic openai structured outputs" — see integration patterns

### Day 5 Tasks (1 hour learning, 1 hour experimenting)

**Hour 1 — Learn:**

1. Read OpenAI JSON mode docs — understand how to enable and limitations (15 min)
2. Read OpenAI Structured Outputs docs — understand schema enforcement (20 min)
3. Read OpenAI Function Calling basics — understand the pattern (20 min)
4. Quick Pydantic refresher — model definition, validation (5 min)

**Hour 2 — Experiment:**

1. Make a call WITHOUT JSON mode, ask for JSON. See if it always works (spoiler: it won't always)
2. Same call WITH JSON mode. Compare reliability.
3. Define a simple Pydantic model (e.g., `Person` with name, age, city)
4. Use structured outputs with your Pydantic schema — see strict enforcement
5. Try function calling: define a dummy function schema, see how model outputs match the schema

### Day 6 Tasks (1 hour challenge, 1 hour reflection)

**Hour 1 — Mini Challenge:**

Build an `extract_structured_data()` function:

```python
from pydantic import BaseModel
from typing import Type, TypeVar

T = TypeVar('T', bound=BaseModel)

def extract_structured_data(
    text: str,
    schema: Type[T],
    model: str = "gpt-4o-mini"
) -> T:
    """
    Extracts structured data from unstructured text.
    
    Args:
        text: Unstructured text (e.g., job posting, email, article)
        schema: Pydantic model defining expected structure
        model: LLM to use
    
    Returns:
        Validated Pydantic model instance
    
    Raises:
        ValidationError: If extraction fails schema validation
    """
    pass
```

Test with this schema and sample texts:

```python
class JobPosting(BaseModel):
    title: str
    company: str
    location: str | None
    salary_min: int | None
    salary_max: int | None
    required_skills: list[str]
    experience_years: int | None
    remote: bool
```

**Success Criteria:**

- [ ] Returns valid Pydantic model instance (not dict)
- [ ] Handles missing optional fields correctly (None, not omitted)
- [ ] Works on 5 different job posting formats (find real ones, varied formats)
- [ ] Never returns invalid JSON (use JSON mode or structured outputs)
- [ ] Boolean fields (`remote`) correctly inferred even when not explicit ("work from home" → True)
- [ ] List fields (`required_skills`) correctly parsed from various formats (comma-separated, bullet points, etc.)
- [ ] Raises meaningful error if text is completely unrelated to schema

**Hour 2 — Solidify + Ponder**

### 5 Things to Ponder

1. JSON mode guarantees valid JSON but not valid schema. Structured Outputs guarantee schema compliance. Function calling also enforces schemas. When would you choose each? What are the tradeoffs?
    
2. Your schema requires `email: str`. The source text doesn't contain an email. What should happen? The model might hallucinate a plausible email. How do you design schemas and prompts to handle "field not present in source"?
    
3. You're extracting data from 10,000 documents. Each extraction costs tokens. Some documents don't contain the data you need (e.g., job posting schema on a recipe page). How would you optimize to not waste tokens on irrelevant documents?
    
4. Function calling was designed for agents to call tools. But you're using it for extraction. You're not actually calling a function — just using the schema. Is this a hack, or a legitimate pattern? What are the implications?
    
5. Your schema has `experience_years: int`. The job posting says "3-5 years experience." What should the model output? How would you redesign the schema to handle ranges properly?
    

---

## Day 7: Mini Build — Robust LLM Client Wrapper

### What to Build

A reusable Python module that combines everything from Week 2 into a production-ready LLM client. This becomes your foundation for Week 3+ work.

### Specifications

**File structure:**

```
llm_client/
├── __init__.py
├── client.py          # Main LLMClient class
├── conversation.py    # ConversationManager from Day 4
├── extraction.py      # Structured extraction from Day 6
└── utils.py           # Token counting, retry logic
```

**Main interface:**

```python
from llm_client import LLMClient

client = LLMClient(model="gpt-4o-mini")

# Simple completion
response = client.complete("What is 2+2?")

# Streaming
for chunk in client.complete("Tell me a story", stream=True):
    print(chunk, end="")

# With conversation management
client.set_system_prompt("You are a helpful assistant.")
client.add_user_message("Hi, my name is Harsh")
response = client.complete()  # Uses conversation history
client.add_user_message("What's my name?")
response = client.complete()  # Should remember "Harsh"

# Structured extraction
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int | None
    occupation: str | None

person = client.extract(
    "John is a 30 year old software engineer from Mumbai",
    schema=Person
)
print(person.name)  # "John"

# Get stats
print(client.get_usage())  # Total tokens used, cost estimate
```

### Success Criteria

- [ ] All Week 2 mini challenges integrated into one module
- [ ] Retry logic works (test by mocking failures)
- [ ] Streaming works
- [ ] Conversation management works (add messages, auto-truncate)
- [ ] Structured extraction works with Pydantic schemas
- [ ] Token counting and cost tracking across all calls
- [ ] Can be imported and used in new scripts (`from llm_client import LLMClient`)
- [ ] Basic error handling — doesn't crash on API failures
- [ ] At least 3 usage examples in a `examples.py` or README

### Things to Ponder (Post-Build)

1. You built this for OpenAI. A client wants to use Anthropic Claude instead. How much of your code needs to change? How would you design for multi-provider support?
    
2. Your `LLMClient` is stateful (tracks conversation). What happens if you use it in a web app with multiple concurrent users? How would you handle multi-tenant usage?
    
3. You track total tokens used. But different calls have different purposes (some are user-facing, some are background extraction). How would you extend tracking to categorize usage by purpose?
    
4. Your retry logic is in the client. But what if you want different retry behavior for different use cases (aggressive retries for batch processing, fail-fast for real-time)? How would you make this configurable?
    
5. You built a wrapper around OpenAI's API. LangChain also provides wrappers. What's the value of your custom wrapper vs. using LangChain? When would you use each?
    

---

## Week 2 Checklist

### Completion Criteria

- [ ] **API Patterns:** Can implement streaming, handle errors, build retry logic with backoff
- [ ] **Context Management:** Can calculate token budget, truncate intelligently, manage conversation history
- [ ] **Structured Outputs:** Can get reliable JSON/schema-compliant outputs, use function calling for extraction
- [ ] **Mini Build:** Working `llm_client` module on your GitHub that you'll actually use
- [ ] **Pondering:** Notes on all "Things to Ponder" — your thinking, not just answers

### What's Next

Week 3 begins **parallel tracks**:

- **RAG Track (1 hour):** Document loading, chunking strategies
- **Agent Track (1 hour):** Function calling deep dive, tool design

Your `LLMClient` from this week becomes the foundation both tracks build on.

---

## Notes Section

### Day 1-2 Notes (API Patterns)

### Day 3-4 Notes (Context Management)

### Day 5-6 Notes (Structured Outputs)

### Day 7 Notes (Mini Build)