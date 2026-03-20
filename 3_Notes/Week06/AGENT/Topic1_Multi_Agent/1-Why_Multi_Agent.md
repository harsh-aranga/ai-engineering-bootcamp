# Note 1: Why Multi-Agent — When Single Agents Break Down

> **Week 6 Agent Track — Days 1-2**  
> **Focus:** Understanding when single agents fail and the decision criteria for going multi-agent

---

## The Single Agent Ceiling

You've built capable single agents in Weeks 3-5. They work well for focused tasks with a handful of tools. But as you scale up — more tools, more complex workflows, longer tasks — you'll hit predictable failure modes.

Understanding _when_ single agents break down is more valuable than knowing _how_ to build multi-agent systems. Most production systems don't need multi-agent architectures. The ones that do have specific, identifiable problems that single agents can't solve.

---

## Failure Mode 1: Tool Overload

### The Problem

LLMs degrade at tool selection as the number of tools increases. This isn't a sharp cliff — it's a gradual erosion of accuracy.

**Empirical observation:** Most models start showing noticeable degradation around 10-15 tools. By 20+ tools, you'll see:

- Incorrect tool selection (calling search when it should call database)
- Tool confusion (mixing up similar tools)
- Hallucinated tool calls (calling tools that don't exist or with wrong parameters)
- Decision paralysis (excessive reasoning before acting)

### Why This Happens

Every tool description consumes context window space. With 20 tools, you might have 2,000-4,000 tokens just describing tools before any conversation begins. The LLM must:

1. Parse all tool descriptions
2. Understand each tool's purpose and parameters
3. Compare the current task against all options
4. Select the best match

This is a classification problem that gets harder as classes increase. The model's attention is spread across more options, and subtle distinctions between similar tools become harder to make.

### The Naive Solution (That Doesn't Scale)

"Just write better tool descriptions" helps marginally but doesn't solve the fundamental problem. You're still asking one model to be an expert router across all domains.

### The Multi-Agent Solution

Split tools across specialized agents. Instead of one agent with 20 tools:

```
Single Agent (struggles):
├── search_web
├── search_database  
├── query_analytics
├── send_email
├── schedule_meeting
├── create_document
├── edit_document
├── upload_file
├── query_crm
├── update_crm
├── generate_report
├── ... (10 more tools)

Multi-Agent (each agent has focused toolset):
├── Research Agent (3 tools: search_web, search_database, query_analytics)
├── Communication Agent (3 tools: send_email, schedule_meeting, query_crm)
├── Document Agent (4 tools: create_document, edit_document, upload_file, generate_report)
```

Each agent now has a manageable number of tools within its domain. The routing decision ("which agent handles this?") is simpler than the tool selection decision ("which of 20 tools handles this?").

---

## Failure Mode 2: Context Bloat

### The Problem

Long-running tasks accumulate context. Tool results, intermediate reasoning, previous attempts — all consume tokens. A single agent handling a complex research task might:

1. Search for information (500 tokens of results)
2. Analyze findings (200 tokens of reasoning)
3. Search for more detail (800 tokens of results)
4. Synthesize (300 tokens)
5. Search for verification (600 tokens)
6. Write draft (1,000 tokens)
7. Review and revise (500 tokens)

By step 7, you have 3,900+ tokens of accumulated context, much of which is no longer relevant. The original task instruction is now buried. The agent loses focus.

### Why This Happens

LLMs process the entire context window on every call. There's no built-in "forgetting" or "summarization" — everything stays in context until you remove it. The lost-in-the-middle effect compounds: important information in the middle of a long context gets less attention.

### The Multi-Agent Solution

Agents can have separate context boundaries. A Research Agent accumulates search results, then passes a _summary_ to the Writing Agent. The Writing Agent never sees the raw search results — only the distilled findings.

```
Research Agent Context:
[Search results: 2,000 tokens]
[Analysis: 500 tokens]
→ Outputs: 200-token summary of key findings

Writing Agent Context:
[200-token summary from Research Agent]
[Writing instructions]
→ Clean context, focused on writing task
```

Each agent maintains a smaller, focused context. Information flows between agents as compressed handoffs, not raw dumps.

---

## Failure Mode 3: Confused Routing (The "Jack of All Trades" Problem)

### The Problem

When one agent handles everything, its system prompt becomes a sprawling document covering multiple domains. The agent must simultaneously be:

- A researcher (thorough, citation-focused)
- A writer (creative, structured)
- A reviewer (critical, detail-oriented)
- A scheduler (precise, calendar-aware)

These personas have different optimal behaviors. A good researcher hedges and presents multiple viewpoints. A good writer makes decisions and commits to a narrative. Asking one agent to switch between modes based on context leads to:

- Tone inconsistency
- Mode confusion (reviewing when it should be writing)
- Prompt bloat (hundreds of tokens of behavioral instructions)

### The Multi-Agent Solution

Each agent has a focused persona with clear behavioral expectations:

```
Research Agent System Prompt (focused):
"You are a research specialist. Find comprehensive information,
cite sources, present multiple viewpoints. Never make claims
without evidence. Your output will be used by other specialists."

Writing Agent System Prompt (focused):
"You are a writing specialist. Take research findings and produce
clear, engaging content. Make editorial decisions. Commit to a
narrative. Your output will be reviewed by an editor."
```

Each prompt is shorter, clearer, and optimized for one mode of operation.

---

## The Cost/Latency Trade-Off

Multi-agent systems aren't free. Every agent invocation is an LLM call. Consider:

**Single Agent Approach:**

- 1 LLM call to process request
- 3 tool calls (research, write, review)
- 1 LLM call for final response
- **Total: 2 LLM calls**

**Multi-Agent Approach:**

- 1 Orchestrator call to route
- 1 Research Agent call + 1 tool call
- 1 Orchestrator call to route
- 1 Writing Agent call
- 1 Orchestrator call to route
- 1 Review Agent call
- 1 Orchestrator call for final response
- **Total: 7 LLM calls**

That's 3.5x the LLM calls for the same task. At scale, this means:

- 3.5x the cost
- 3.5x the latency (if sequential)
- 3.5x the failure points

### When This Trade-Off Is Worth It

The cost is justified when:

1. **Single agent accuracy is unacceptable:** If your single agent fails 30% of the time on complex tasks, and multi-agent reduces that to 5%, the extra cost is worth it.
    
2. **Task complexity is inherently high:** Some tasks genuinely require different expertise. A financial analysis task might need data retrieval, statistical analysis, and report writing — truly different skills.
    
3. **Quality matters more than speed:** Legal document review, medical information synthesis, high-stakes decisions.
    
4. **You can parallelize:** If Research Agent and Data Agent can run simultaneously, you don't pay the full latency penalty.
    

### When Single Agent Is Better

Stick with single agent when:

1. **Tool count is manageable (< 10):** No routing problem to solve.
    
2. **Tasks are homogeneous:** All tasks need similar capabilities.
    
3. **Latency is critical:** User-facing chat where every second matters.
    
4. **Single agent accuracy is acceptable:** If it works 95% of the time, don't over-engineer.
    

---

## Decision Framework: When to Go Multi-Agent

Before building a multi-agent system, answer these questions:

### Question 1: What's Breaking?

Don't go multi-agent because it sounds sophisticated. Identify the specific failure:

- "Our agent picks the wrong tool 25% of the time when we have 15+ tools" → Tool overload
- "Long research tasks lose coherence after 5 minutes" → Context bloat
- "The agent writes like a researcher when it should write like a marketer" → Persona confusion

If you can't articulate the failure, you probably don't need multi-agent.

### Question 2: Can You Fix the Single Agent?

Often, single-agent problems have single-agent solutions:

- Tool overload? Try tool grouping, better descriptions, or conditional tool availability.
- Context bloat? Implement summarization, context pruning, or message trimming.
- Persona confusion? Improve prompt structure or use few-shot examples.

Multi-agent is the solution when these approaches have been tried and failed.

### Question 3: Do You Have Natural Agent Boundaries?

Multi-agent works when tasks have clear divisions:

- Different tools for different domains (research tools vs. communication tools)
- Different expertise requirements (analysis vs. writing)
- Different quality criteria (speed vs. accuracy)

If your task is monolithic with no natural splits, forcing multi-agent creates artificial complexity.

### Question 4: Can You Afford the Overhead?

Multi-agent adds:

- Development complexity (multiple agents to build, test, maintain)
- Runtime cost (more LLM calls)
- Debugging difficulty (failures can occur in routing, individual agents, or handoffs)
- Latency (unless parallelized)

Make sure the benefits exceed these costs.

---

## Concrete Example: Research + Write + Review

Let's walk through a real decision.

**Task:** "Research recent developments in battery technology and write a 500-word summary for a non-technical audience."

### Single Agent Approach

One agent with tools: `web_search`, `write_document`

```
Agent receives task
→ Searches for battery technology developments
→ Reads search results (accumulating context)
→ Searches for more detail on promising topics
→ More context accumulates
→ Writes summary
→ Self-reviews (but with all the research noise in context)
→ Returns result
```

**Problems that emerge:**

- By writing time, context is cluttered with search results
- Agent tries to include everything it found (research mode bleeding into writing)
- Self-review is weak (same model, same biases, same context)

### Multi-Agent Approach

Three specialized agents:

**Research Agent** (tools: `web_search`)

- System prompt emphasizes thoroughness, source quality, fact-checking
- Outputs: Structured findings with key facts, sources, confidence levels
- Does NOT write prose — just extracts and organizes information

**Writing Agent** (tools: none — pure generation)

- System prompt emphasizes clarity, audience awareness, narrative structure
- Receives: Research findings summary (not raw search results)
- Outputs: Draft summary
- Makes editorial decisions about what to include/exclude

**Review Agent** (tools: none — pure evaluation)

- System prompt emphasizes critical reading, fact verification, audience fit
- Receives: Draft + original research findings
- Outputs: Specific feedback or approval
- Can request revision from Writing Agent

**Benefits:**

- Writing Agent has clean context (just the research summary, not raw search noise)
- Each agent optimizes for its specific role
- Review Agent provides genuine second opinion (different system prompt, different context)

**Costs:**

- 3x more agent definitions to maintain
- Orchestration logic to manage handoffs
- More LLM calls per task

### The Verdict

For this task, multi-agent is likely overkill if:

- You're doing this occasionally
- Quality requirements are moderate
- A single agent produces acceptable results 80%+ of the time

Multi-agent is justified if:

- You're doing this at scale (hundreds of summaries)
- Quality is critical (published content, client deliverables)
- Single agent consistently produces muddled output
- You need audit trails (which agent said what)

---

## The "Improve Single Agent First" Checklist

Before going multi-agent, try these single-agent improvements:

### For Tool Overload:

- [ ] Reduce tool count by combining similar tools
- [ ] Improve tool descriptions (be specific about when to use each)
- [ ] Use conditional tool availability (only show relevant tools based on conversation state)
- [ ] Add a "tool selection" step before tool execution

### For Context Bloat:

- [ ] Implement message trimming (remove old messages)
- [ ] Summarize tool results before adding to context
- [ ] Use the `trim_messages` utility (LangGraph provides this)
- [ ] Structure prompts to keep key instructions at the end (recency bias helps)

### For Persona Confusion:

- [ ] Restructure system prompt with clearer sections
- [ ] Add few-shot examples showing correct behavior for different situations
- [ ] Use explicit mode switching ("You are now in research mode...")
- [ ] Simplify — maybe the agent is trying to do too much

If you've worked through this checklist and still have problems, multi-agent becomes the right solution.

---

## Key Takeaways

1. **Multi-agent solves specific problems:** Tool overload, context bloat, persona confusion. Don't use it without identifying which problem you're solving.
    
2. **The cost is real:** More LLM calls means more latency, more cost, more failure points. Make sure the accuracy gains justify this.
    
3. **Natural boundaries matter:** Multi-agent works when tasks have clear divisions. Forcing artificial splits creates unnecessary complexity.
    
4. **Single agent improvements first:** Better prompts, tool descriptions, and context management often solve problems cheaper than multi-agent.
    
5. **Think in specialists:** When you do go multi-agent, each agent should be a focused specialist with a clear role, limited tools, and a tight system prompt.
    

---

## What's Next

Now that you understand _when_ to use multi-agent systems, the following notes cover _how_:

- **Note 2:** Supervisor/Orchestrator Pattern — One boss, many workers
- **Note 3:** Network/Collaboration Pattern — Peer agents working together
- **Note 4:** Swarm Pattern — Dynamic handoffs based on specialization
- **Note 5:** Handoffs and Communication — How agents pass information

---

## References

**Documentation searched for this note:**

- LangChain Docs: Workflows and Agents (https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- LangGraph Multi-Agent Concepts (https://langchain-ai.github.io/langgraphjs/concepts/multi_agent/)
- LangGraph Supervisor Library (https://github.com/langchain-ai/langgraph-supervisor-py)
- LangGraph Swarm Library (https://github.com/langchain-ai/langgraph-swarm-py)

**Key insight from LangChain team (2025):** "We now recommend using the supervisor pattern directly via tools rather than this library for most use cases. The tool-calling approach gives you more control over context engineering." — This reflects the preference for simpler solutions when possible.