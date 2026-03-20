# When to Use Agents vs. Simpler Solutions

> **Doc References:** Anthropic "Building Effective Agents" (2024), OpenAI "A Practical Guide to Building Agents" (2025), LangChain "How to think about agent frameworks" (2025), LangChain "State of Agent Engineering" Survey (2025)

---

## The Golden Rule

> "When building applications with LLMs, we recommend finding the simplest solution possible, and only increasing complexity when needed. This might mean not building agentic systems at all." — Anthropic, "Building Effective Agents"

Most AI features don't need agents. Start simple. Add complexity only when simpler solutions fail.

---

## The Complexity Ladder

```
┌─────────────────────────────────────────────────────────────┐
│                    COMPLEXITY LADDER                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Level 4: AUTONOMOUS AGENTS                                 │
│           LLM decides what to do, when to stop, how to      │
│           recover. Open-ended. Multiple tools. Self-correct.│
│           ↑                                                 │
│  Level 3: WORKFLOWS WITH TOOL USE                           │
│           Fixed steps, but LLM calls tools as needed.       │
│           You control flow; model controls tool params.     │
│           ↑                                                 │
│  Level 2: CHAINED PROMPTS (WORKFLOWS)                       │
│           Multiple LLM calls in fixed sequence.             │
│           Output of one → input of next. Deterministic.     │
│           ↑                                                 │
│  Level 1: SINGLE LLM CALL + RAG                             │
│           One prompt, maybe with retrieved context.         │
│           No loops, no tools, no branching.                 │
│           ↑                                                 │
│  Level 0: SINGLE LLM CALL                                   │
│           Just prompt → response. Done.                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘

        Start at Level 0. Only climb when you must.
```

---

## The Decision Framework

### Question 1: Does the AI need to DECIDE what to do?

```
User: "Summarize this document"
→ NO decision needed. Fixed task. Single LLM call.

User: "Research competitor pricing and update our database"  
→ YES. Which competitors? What sources? When is enough?
```

**If NO → You need a workflow, not an agent.**

### Question 2: Can you define the steps in advance?

```
Task: "Generate blog post from outline"
→ YES: Expand outline → Write intro → Write sections → Add conclusion
→ Use a WORKFLOW (chained prompts)

Task: "Debug this failing test"
→ NO: Unknown which files, which errors, which fixes will work
→ May need an AGENT
```

**If YES → Use a workflow. If NO → Consider an agent.**

### Question 3: Is the problem open-ended?

```
Open-ended: "Research this topic until you have enough for a report"
Closed: "Extract these 5 fields from this document"
```

**Open-ended problems with unclear stopping conditions → Agent territory.**

---

## When Each Solution Fits

### Level 0: Single LLM Call

**Use when:**

- Task is self-contained in one prompt
- No external data needed (or already in prompt)
- Classification, generation, transformation, Q&A

**Examples:**

- Sentiment analysis
- Text summarization
- Translation
- Code explanation
- Email drafting

```python
response = client.responses.create(
    model="gpt-4o",
    input="Summarize this article in 3 bullets: {article}"
)
```

**Cost:** 1 API call  
**Latency:** ~1-3 seconds  
**Reliability:** Highest (single point of failure)

---

### Level 1: Single LLM Call + RAG

**Use when:**

- Need external/private knowledge
- Task is still single-step after retrieval
- Fixed retrieval strategy works

**Examples:**

- Q&A over documents
- Customer support with knowledge base
- Product recommendations

```python
# Retrieve relevant docs
docs = vector_store.search(query, top_k=5)

# Single LLM call with context
response = client.responses.create(
    model="gpt-4o",
    input=f"Context: {docs}\n\nQuestion: {query}"
)
```

**Cost:** 1 API call + retrieval  
**Latency:** ~2-5 seconds  
**Reliability:** High (retrieval quality is main variable)

---

### Level 2: Workflows (Chained Prompts)

**Use when:**

- Task has multiple distinct steps
- Steps are FIXED and PREDICTABLE
- Each step's output feeds the next

**Examples:**

- Document processing: extract → validate → transform → store
- Content pipeline: outline → draft → edit → format
- Data analysis: query → summarize → visualize

```python
# Step 1: Extract key points
key_points = llm_call("Extract key points from: {doc}")

# Step 2: Organize into structure
outline = llm_call(f"Organize these into an outline: {key_points}")

# Step 3: Write full content
content = llm_call(f"Write article from outline: {outline}")

# Deterministic flow - no decisions, no branching
```

**Cost:** N API calls (where N = steps)  
**Latency:** Sum of all steps  
**Reliability:** High if each step is robust

---

### Level 3: Workflows with Tool Use

**Use when:**

- Need external actions (search, calculate, API calls)
- But flow is still deterministic
- You know WHEN tools will be needed

**Examples:**

- Calculator for math problems
- Web search for current info
- Database queries for lookups

```python
# Fixed flow with tool use
response = llm_call_with_tools(
    input="What's the weather in Tokyo and convert to Fahrenheit?",
    tools=[weather_tool, calculator_tool]
)
# You know it will: search weather → calculate conversion
```

**Key distinction from agents:** You still control the workflow. The LLM just decides tool parameters, not whether/when to use them.

---

### Level 4: Autonomous Agents

**Use when:**

- Number of steps is UNKNOWN in advance
- LLM must DECIDE what to do next
- Problem is OPEN-ENDED
- Need SELF-CORRECTION on failure
- Require ADAPTIVE planning

**Examples:**

- Code debugging (unknown files, unknown fixes)
- Research tasks (follow leads, evaluate sources)
- Computer use (navigate, click, type, verify)
- Multi-step booking/purchasing

```python
# Agent loop - LLM controls flow
while not done:
    thought = llm_think("What should I do next?")
    action = llm_decide_action(tools)
    result = execute(action)
    done = llm_evaluate("Is task complete?")
```

**Cost:** 5-20x more LLM calls than workflows  
**Latency:** Minutes (not seconds)  
**Reliability:** Lower (errors compound across steps)

---

## The Trade-offs

|Aspect|Simpler (Single/Workflow)|Agents|
|---|---|---|
|**Cost**|Low, predictable|5-20x higher|
|**Latency**|Seconds|Minutes|
|**Reliability**|High|Lower (errors compound)|
|**Debugging**|Easy (fixed steps)|Hard (dynamic paths)|
|**Flexibility**|Low|High|
|**Predictability**|High|Low|

**Anthropic's advice:** "Agentic systems often trade latency and cost for better task performance, and you should consider when this tradeoff makes sense."

---

## Red Flags: You Probably DON'T Need an Agent

|What You're Building|Why Not an Agent|Use Instead|
|---|---|---|
|Chatbot that answers questions|No decisions, just respond|Single LLM + RAG|
|Content generator from template|Fixed steps|Workflow|
|Form that generates output|Linear: input → output|Single LLM call|
|Classification/extraction|One-shot task|Single LLM call|
|Translation/summarization|No tools needed|Single LLM call|
|RAG Q&A|Fixed retrieve→generate|Single LLM + RAG|

**The test:** Can you draw a flowchart with no decision diamonds? → Not an agent.

---

## Green Flags: You Might Need an Agent

|Task Characteristic|Example|
|---|---|
|Unknown number of steps|"Debug until tests pass"|
|Must decide between paths|"Research topic X using whatever sources are relevant"|
|Self-correction needed|"If this approach fails, try alternatives"|
|Open-ended goals|"Find the best solution" (not "execute these 3 steps")|
|Dynamic tool selection|"Use whatever tools help" vs "always search then summarize"|
|Extended autonomy|"Handle this ticket end-to-end"|

---

## Decision Tree

```
START: What are you building?
          │
          ▼
┌─────────────────────────────────┐
│ Can you define exact steps?     │
└─────────────────────────────────┘
          │
    YES   │   NO
          │    └──────────────────────────────┐
          ▼                                   ▼
┌──────────────────────┐        ┌─────────────────────────┐
│ Need external data?  │        │ Open-ended problem?     │
└──────────────────────┘        └─────────────────────────┘
    │           │                    │           │
  NO │         YES│               NO │          YES│
    ▼            ▼                   ▼            ▼
┌────────┐  ┌────────────┐    ┌───────────┐  ┌────────┐
│Single  │  │Single call │    │Workflow   │  │ AGENT  │
│LLM call│  │+ RAG       │    │with tools │  │        │
└────────┘  └────────────┘    └───────────┘  └────────┘

                    │                              │
                    │         Need external        │
                    │         tools/actions?       │
                    │               │              │
                    │         YES   │   NO         │
                    │               ▼              │
                    │        ┌───────────┐         │
                    └───────▶│ Workflow  │◀────────┘
                             └───────────┘
```

---

## Cost Reality Check

From industry data:

|Approach|Relative Cost|Relative Build Time|
|---|---|---|
|Single LLM call|1x|1x|
|Workflow (chained)|2-5x|2x|
|Agent|5-20x|7x|

**Question to ask:** Is the task complexity worth 5-20x cost?

**Anthropic's finding:** "The most successful implementations weren't using complex frameworks. Instead, they were building with simple, composable patterns."

---

## The "If a Single Prompt Can Solve It" Test

> "If a single Prompt can solve the problem, don't use an Agent."

Before building an agent, try:

1. **Can I solve this with one well-crafted prompt?**
    
    - Add context, examples, constraints
    - Use Chain-of-Thought in the prompt
    - Provide clear output format
2. **If not, can I chain 2-3 prompts?**
    
    - Fixed sequence, no branching
    - Each step is deterministic
3. **If not, can I use a workflow with tools?**
    
    - You control flow
    - Tools are called at known points
4. **Only if all above fail → Consider an agent**
    

---

## Production Reality (From LangChain Survey 2025)

- 57% of organizations have agents in production
- But most "agents" are actually workflows
- 89% require observability to debug
- 52% run offline evaluations
- Human review remains essential for high-stakes decisions

**Translation:** Even teams running "agents" in production often use simpler patterns for most tasks, reserving true autonomous agents for specific use cases.

---

## Practical Examples

### Example 1: Customer Support Bot

**Wrong approach:** Build an agent that can "handle anything"  
**Right approach:**

- RAG for answering product questions (Level 1)
- Workflow for processing returns (Level 2)
- Human escalation for edge cases

### Example 2: Document Processing

**Wrong approach:** Agent that "intelligently processes documents"  
**Right approach:**

- Classify document type (Level 0)
- Extract fields based on type (Level 0)
- Validate extracted data (Level 0)
- Chain these steps (Level 2)

### Example 3: Code Debugging

**May actually need an agent:**

- Unknown which files are relevant
- Unknown what the fix will be
- Must try, evaluate, retry
- Needs to decide when "done"

→ This is legitimate agent territory

---

## Key Takeaways

1. **Default to simple** — Single LLM call → RAG → Workflow → Agent
    
2. **Agents are for decisions, not tasks** — If you can define the steps, use a workflow
    
3. **Agents cost 5-20x more** — In tokens, latency, and debugging time
    
4. **Open-ended ≠ "use AI"** — Many open-ended problems need human judgment, not agents
    
5. **Workflows are underrated** — Fixed sequences with good prompts solve most problems
    
6. **Trust must be earned** — Only use autonomous agents in sandboxed, well-tested environments
    
7. **Observability is mandatory** — You can't debug what you can't see
    

---

## Connection to Previous Topics

- **Agent Loop / ReAct:** These are the HOW; this topic is about WHEN
- **Tool Calling:** Tools don't require agents—workflows can use tools too
- **What Is an Agent:** Now you know when autonomy is actually needed

## Up Next

With the conceptual foundation complete, the next topic covers the **Anatomy of a Tool Definition**—diving deeper into how to design tools that work well with both workflows and agents.