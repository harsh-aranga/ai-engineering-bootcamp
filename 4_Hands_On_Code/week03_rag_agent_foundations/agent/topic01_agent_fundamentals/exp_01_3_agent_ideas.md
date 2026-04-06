**"Give me three tasks that genuinely need an agent architecture versus a single LLM call."**

---

**1. Infrastructure incident response (K8s, cloud ops)**

A pod is crashing. The agent needs to: check pod status → read logs → correlate with node metrics → decide if it's OOM, network, or config issue → take corrective action → verify fix worked.

Why it needs an agent: The number of steps is unknown upfront. Each observation determines the next action. A single call can't do this because the diagnosis unfolds dynamically.

**2. Multi-step research with source validation**

"Find the latest quarterly revenue for three competing companies and compare trends."

The agent needs to: search for each company → locate credible sources → extract numbers → handle cases where data is missing or conflicting → maybe search again with different terms → synthesize comparison.

Why it needs an agent: Tool use in a loop. If one search returns garbage, the agent must recognize that and retry. A single RAG call assumes retrieval always succeeds.

**3. Complex booking or scheduling with constraints**

"Book me a flight to Tokyo that works around my existing calendar, costs under $1500, and arrives before 6pm local time."

The agent needs to: read calendar → search flights → find options don't fit → adjust dates or airports → recheck calendar for conflicts → iterate until viable option found or report impossible.

Why it needs an agent: Constraint satisfaction across multiple tools with backtracking. No fixed recipe.

---

**The pattern I'd highlight:**

Agents are necessary when the task requires *closed-loop control* — observe, reason, act, observe again. If you can write a deterministic script with fixed steps, you don't need an agent. If the next step depends on what you learned from the previous step, and you might need to backtrack or retry, that's agent territory.

---