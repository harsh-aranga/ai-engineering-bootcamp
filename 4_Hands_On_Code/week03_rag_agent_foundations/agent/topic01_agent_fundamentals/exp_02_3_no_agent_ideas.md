**"Give me three tasks that DON'T need an agent."**

---

**1. Single-turn factual retrieval**

"What's our refund policy?" → Retrieve document → Generate answer → Done.

Why no agent: One retrieval, one generation. No decision point. No "did that work? should I try again?" If retrieval fails, you just say "I don't know" — you're not autonomously retrying with different strategies.

**2. Preference update or CRUD operations**

"Change my notification setting to email-only."

Why no agent: This is intent extraction + API call. The LLM parses the request, extracts parameters, you execute. There's no loop, no observation of results changing the next action. It's a *function call*, not an *agent*.

**3. Simple lookup with known structure**

"What's the weather in Chennai?"

Why no agent: Single tool call, deterministic response. The LLM doesn't need to reason about whether to try a different approach. Call weather API → return result. Done.

---

These tasks share a pattern: **the path is fully determined before execution begins.** You know exactly what to do, you do it, you're done. There's no feedback loop, no branching based on intermediate results, no retries with different strategies.

The litmus test for agent decisions:

| Question | Agent needed? |
|----------|---------------|
| Is there exactly one path through this task? | No |
| Could the task fail in a way that requires a *different approach* (not just retry)? | Yes |
| Does the next step depend on interpreting the result of the previous step? | Yes |

