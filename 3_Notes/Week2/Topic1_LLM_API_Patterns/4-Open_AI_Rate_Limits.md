# OpenAI API – Rate Limits (Reference Notes)
## What are rate limits?
Rate limits cap how much you can use the API within a time window to:
- Protect system stability
- Prevent abuse
- Ensure fair usage across customers

They apply **per organization + per model**.

---
# Core Limit Types
## 1. Requests Per Minute (RPM)
- Max number of API calls per minute.
- Hit when you send too many requests too quickly.
- Typical failure: `429 Too Many Requests`.

Use case impact:
- Chatbots with many small calls
- High-concurrency systems

## 2. Tokens Per Minute (TPM)
- Max tokens (input + output) processed per minute.
- Large prompts or long responses consume TPM fast.

Use case impact:
- Long context prompts
- Batch processing
- Agent chains

Key insight:
> Fewer requests ≠ lower usage if each request is token-heavy.

## 3. Requests Per Day (RPD) / Tokens Per Day (TPD)
- Daily caps for overall usage.
- Mostly relevant for cost control and free / lower tiers.

---
# Model-Specific Limits
- Each model has **its own RPM / TPM limits**
- Using multiple models splits usage across independent buckets

Example:
- Hitting limits on `gpt-4.1` does **not** affect `gpt-4o-mini`

---
# What Happens When You Hit Limits?
- API returns **HTTP 429**
- Response includes headers indicating:
  - Which limit was exceeded
  - When you can retry

Never retry immediately in a tight loop.

---
# Recommended Handling Patterns

## Exponential Backoff
- Retry after increasing delays (e.g., 1s → 2s → 4s)
- Add jitter to avoid retry storms
## Token-Aware Design
- Trim prompts aggressively
- Cache system prompts
- Avoid repeating schemas / instructions
## Throughput Smoothing
- Queue requests
- Spread load over time instead of bursts

---
# Scaling Options
- Request higher limits from OpenAI
- Redesign flows (batching, async, caching)
- Move heavy tasks off real-time paths

---
# Mental Model
Think of rate limits as **bandwidth, not errors**:
- RPM = request bandwidth
- TPM = compute bandwidth
- Design like a distributed system, not a script

---
# Approximate OpenAI Rate Limits (Mental Model Table)

| Usage Tier                  | Requests / min (RPM) | Tokens / min (TPM) | Typical Fit                         |
| --------------------------- | -------------------- | ------------------ | ----------------------------------- |
| **Individual / Solo Dev**   | ~60–100 RPM          | ~40k–100k TPM      | Local dev, scripts, experiments     |
| **Small Team / Startup**    | ~300–600 RPM         | ~200k–500k TPM     | Internal tools, MVPs, light prod    |
| **Growing Product**         | ~1k–3k RPM           | ~1M–3M TPM         | SaaS backend, agents, pipelines     |
| **Large Org / Enterprise**  | 5k+ RPM              | 5M+ TPM            | High-traffic prod, batch + realtime |
| **Custom / Approved Scale** | Negotiated           | Negotiated         | Mission-critical workloads          |
## How to read this table (important)
- **RPM is rarely the real bottleneck**  
    TPM almost always hits first with:
    - Long prompts
    - Agent loops
    - Batch jobs
- **TPM scales cost _and_ throughput**  
    Higher TPM = more parallel thinking, not just more text.
- **Multiple models = multiple buckets**  
    Splitting workloads across models spreads limits.

## Rule-of-thumb heuristics
- Chat apps → **RPM-bound**
- Agents / RAG / long context → **TPM-bound**
- Batch processing → **Daily caps matter more**
- Streaming ≠ cheaper (tokens still count)