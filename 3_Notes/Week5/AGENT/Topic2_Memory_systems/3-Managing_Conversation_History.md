# Managing Conversation History: Windowing and Summarization

## The Problem: Context Windows Fill Up

Every LLM has a finite context window. As conversations grow, you face hard limits:

|Model|Context Window|At ~1000 tokens/turn|Fills Up After|
|---|---|---|---|
|GPT-4o|128K tokens|~128 turns|~1 hour of conversation|
|Claude Opus 4.6|200K (1M beta)|~200 turns|~2 hours|
|Claude Sonnet 4.6|200K (1M beta)|~200 turns|~2 hours|

When you exceed the limit, the API returns an error. But problems start earlier:

- **Cost scales linearly** with input tokens
- **Latency increases** with context size
- **Relevance decreases** as old messages dilute the signal

This note covers techniques to manage conversation history _within a session_—keeping context under control while preserving what matters.

> **Scope clarification:** This is about managing the _current conversation_ (short-term). Long-term memory extraction (saving facts/episodes to external stores) is covered in Notes 4–7.

---

## Strategy 1: Windowing (Keep Last N)

The simplest approach: keep only the most recent messages.

### Message-Count Windowing

```python
def keep_last_n_messages(messages: list, n: int = 10) -> list:
    """Keep only the last n messages."""
    return messages[-n:]
```

**Problem:** Message count doesn't correlate with token count. Ten messages might be 500 tokens or 50,000 tokens.

### Token-Count Windowing with LangChain

LangChain provides `trim_messages` for token-aware windowing:

```python
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)
from langchain.chat_models import init_chat_model

model = init_chat_model("claude-sonnet-4-6")

def call_model_with_trimming(messages: list) -> str:
    """Trim messages to fit token budget before calling model."""
    trimmed = trim_messages(
        messages,
        strategy="last",              # Keep most recent
        token_counter=count_tokens_approximately,
        max_tokens=8000,              # Budget for history
        start_on="human",             # Always start on user message
        end_on=("human", "tool"),     # Valid ending types
    )
    response = model.invoke(trimmed)
    return response.content
```

**Key parameters:**

- `strategy="last"`: Keep recent messages (vs `"first"` for oldest)
- `start_on="human"`: Ensures context starts with a user message (not orphaned assistant response)
- `end_on`: Ensures valid message sequence (no dangling tool calls)

### Where to Apply Windowing

Two patterns:

**1. Trim in state (destructive):**

```python
# Messages are deleted from graph state
from langchain_core.messages import RemoveMessage

def filter_messages(state):
    """Remove all but last 5 messages from state."""
    delete_messages = [
        RemoveMessage(id=m.id) 
        for m in state["messages"][:-5]
    ]
    return {"messages": delete_messages}
```

**2. Trim at invocation (non-destructive):**

```python
# Full history preserved in state, trimmed only for LLM call
def call_model(state):
    trimmed = trim_messages(state["messages"], ...)
    response = model.invoke(trimmed)
    return {"messages": [response]}
```

Pattern 2 is usually better—you keep the full audit trail while controlling what the LLM sees.

---

## Strategy 2: Summarization

Instead of discarding old messages, compress them into a summary.

### The Basic Pattern

```
Before:  [msg1, msg2, msg3, msg4, msg5, msg6, msg7, msg8]
                              ↓
After:   [summary_of_1-6, msg7, msg8]
```

### LangGraph Implementation

```python
from typing import TypedDict, Annotated
from langchain_core.messages import HumanMessage, RemoveMessage
from langgraph.graph import StateGraph, START, MessagesState

# Extend state to include summary
class State(TypedDict):
    messages: Annotated[list, add_messages]
    summary: str

def summarize_conversation(state: State) -> dict:
    """Generate or extend summary, then prune old messages."""
    
    # Get existing summary (if any)
    summary = state.get("summary", "")
    
    # Build summarization prompt
    if summary:
        summary_prompt = (
            f"This is the summary of the conversation so far: {summary}\n\n"
            "Extend the summary by incorporating the new messages above:"
        )
    else:
        summary_prompt = "Create a summary of the conversation above:"
    
    # Generate summary
    messages = state["messages"] + [HumanMessage(content=summary_prompt)]
    response = model.invoke(messages)
    
    # Delete all but the last 2 messages
    delete_messages = [
        RemoveMessage(id=m.id) 
        for m in state["messages"][:-2]
    ]
    
    return {
        "summary": response.content,
        "messages": delete_messages
    }
```

### Injecting Summary into Context

The summary needs to reach the model:

```python
def call_model(state: State) -> dict:
    """Call model with summary context."""
    summary = state.get("summary", "")
    
    if summary:
        # Inject summary as system message
        system_message = f"Summary of earlier conversation: {summary}"
        messages = [SystemMessage(content=system_message)] + state["messages"]
    else:
        messages = state["messages"]
    
    response = model.invoke(messages)
    return {"messages": [response]}
```

### When to Trigger Summarization

```python
def should_summarize(state: State) -> str:
    """Route to summarization if message count exceeds threshold."""
    if len(state["messages"]) > 10:
        return "summarize"
    return "continue"

# In graph construction
builder.add_conditional_edges(
    "assistant",
    should_summarize,
    {"summarize": "summarize_node", "continue": END}
)
```

---

## Strategy 3: Hybrid (Summary + Recent Window)

The production pattern: keep a rolling summary _plus_ recent messages.

```
┌─────────────────────────────────────────────────────┐
│                    CONTEXT                          │
│  ┌─────────────────────────────────────────────┐   │
│  │ System: Summary of conversation so far:     │   │
│  │ - User is building a RAG system            │   │
│  │ - Discussed chunking strategies            │   │
│  │ - Decided on 512-token chunks with overlap │   │
│  └─────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────┐   │
│  │ Recent messages (last 4-6 turns):          │   │
│  │ - User: "Now let's talk about retrieval"   │   │
│  │ - Assistant: "For retrieval, you have..."  │   │
│  │ - User: "What about hybrid search?"        │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

**Why hybrid?**

- Summary preserves high-level context (decisions, facts, progress)
- Recent window preserves immediate context (current topic, exact wording)
- Together, they balance breadth and recency

---

## Provider-Specific: OpenAI Responses API Compaction

OpenAI's Responses API (March 2025+) includes native compaction via `/responses/compact`:

```python
from openai import OpenAI

client = OpenAI()

# Option 1: Manual compaction endpoint
response = client.responses.compact(
    model="gpt-5.3-codex",
    input=conversation_history,  # Full history
)
# Returns compacted window with encrypted compaction item

# Option 2: Server-side automatic compaction
response = client.responses.create(
    model="gpt-5.3-codex",
    input=conversation_history,
    store=False,
    context_management=[{
        "type": "compaction",
        "compact_threshold": 200000  # Trigger at 200K tokens
    }]
)
```

**Key characteristics:**

- **Encrypted compaction item:** The compacted state is opaque—you can't read it, but it carries forward reasoning and context
- **Server-side triggers:** Set a threshold, and compaction happens automatically when exceeded
- **ZDR-compatible:** Works with Zero Data Retention when `store=False`

**Usage pattern:**

```python
conversation = [{"type": "message", "role": "user", "content": "Let's begin..."}]

while keep_going:
    response = client.responses.create(
        model="gpt-5.3-codex",
        input=conversation,
        store=False,
        context_management=[{"type": "compaction", "compact_threshold": 200000}]
    )
    
    # Extend conversation with response output
    conversation.extend(response.output)
    
    # Add next user input
    conversation.append({
        "type": "message",
        "role": "user", 
        "content": get_next_user_input()
    })
```

After compaction fires, the conversation array includes the compaction item. You don't need to do anything special—just keep passing the full array, and the API handles it.

---

## Provider-Specific: Anthropic Context Management

Anthropic offers multiple approaches (all in beta as of early 2026):

### 1. Context Editing: Clear Old Tool Results

For agentic workflows with heavy tool use, old tool results (file contents, search results) can be cleared:

```python
import anthropic

client = anthropic.Anthropic()

response = client.beta.messages.create(
    model="claude-opus-4-6",
    max_tokens=4096,
    betas=["context-management-2025-06-27"],
    messages=messages,
    context_management={
        "edits": [{
            "type": "clear_tool_uses_20250919",
            "trigger": {"type": "input_tokens", "value": 30000},
            "keep": {"type": "tool_uses", "value": 3},  # Keep last 3
            "exclude_tools": ["web_search"]  # Don't clear search results
        }]
    }
)
```

### 2. Compaction: Summarize Conversation

Server-side summarization (beta `compact-2026-01-12`):

```python
response = client.beta.messages.create(
    model="claude-opus-4-6",
    max_tokens=4096,
    betas=["compact-2026-01-12"],
    messages=messages,
    context_management={
        "edits": [{
            "type": "compact_20260112",
            "trigger": {"type": "input_tokens", "value": 100000}
        }]
    }
)
```

When triggered:

1. Claude summarizes the conversation
2. A `compaction` block is returned in the response
3. On subsequent requests, the API automatically drops messages before the compaction block

**Customizing the summarization prompt:**

```python
context_management={
    "edits": [{
        "type": "compact_20260112",
        "trigger": {"type": "input_tokens", "value": 100000},
        "summary_prompt": "Summarize the technical decisions made so far, "
                         "including any code snippets that were agreed upon."
    }]
}
```

### 3. Combining Memory Tool with Compaction

When compaction approaches, Claude can save important info to persistent memory first:

```python
# Memory tool + compaction work together
# Claude receives warning before compaction triggers
# Uses memory tool to save critical facts
# Then compaction summarizes the rest
```

---

## Trade-offs Summary

|Technique|Preserves|Loses|Best For|
|---|---|---|---|
|**Windowing (last N)**|Recent context|All older context|Simple chatbots, support tickets|
|**Summarization**|High-level decisions|Exact wording, nuance|Long-running projects|
|**Hybrid**|Both breadth and recency|Some older detail|Production assistants|
|**Provider compaction**|Server-managed state|Transparency (encrypted)|Long agentic workflows|

---

## Implementation Checklist

When implementing conversation history management:

1. **Choose your strategy** based on use case:
    
    - Short sessions (< 20 turns)? Windowing is fine
    - Long sessions with context dependency? Hybrid or compaction
2. **Decide where to apply**:
    
    - Trim in state (destructive) vs trim at invocation (preserve full history)
3. **Handle edge cases**:
    
    - Tool call/result pairs must stay together
    - Don't orphan assistant messages without preceding user messages
    - Consider `start_on` and `end_on` parameters
4. **Token budget allocation**:
    
    - System prompt: fixed
    - Summary: ~500-1000 tokens
    - Recent window: ~4000-8000 tokens
    - Response generation: reserved (don't cut into this)
5. **Test degradation**:
    
    - What happens when summary gets too compressed?
    - Can the agent still reference earlier decisions?

---

## Key Takeaways

1. **Context windows are finite.** Cost, latency, and relevance all degrade as context grows—management is not optional.
    
2. **Windowing is simple but lossy.** Good for independent turns; bad when earlier context matters.
    
3. **Summarization preserves meaning but costs tokens.** An LLM call to summarize adds latency and cost.
    
4. **Hybrid (summary + window) is the production standard.** Captures both breadth and recency.
    
5. **Provider-native compaction is emerging.** OpenAI's `/compact` and Anthropic's `compact_20260112` handle this server-side with encrypted state.
    
6. **Preserve audit trails separately.** Even if you trim for the LLM, keep full history in your database for debugging and compliance.
    

---

## References

- LangGraph Memory Documentation: https://docs.langchain.com/oss/python/langgraph/add-memory
- LangChain `trim_messages`: https://python.langchain.com/docs/how_to/trim_messages/
- OpenAI Compaction Guide: https://developers.openai.com/api/docs/guides/compaction/
- Anthropic Context Editing: https://platform.claude.com/docs/en/build-with-claude/context-editing
- Anthropic Compaction (beta): https://platform.claude.com/docs/en/build-with-claude/compaction