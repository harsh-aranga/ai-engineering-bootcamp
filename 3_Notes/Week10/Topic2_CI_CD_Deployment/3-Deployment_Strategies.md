# Deployment Strategies: Blue-Green, Canary, and Rolling

## Why Deployment Strategy Matters

The moment you deploy new code, you're making a bet: this version is better than the last. Deployment strategy determines the stakes of that bet.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     THE DEPLOYMENT RISK EQUATION                             │
│                                                                              │
│   Risk = (% of users affected) × (time to detect) × (time to rollback)      │
│                                                                              │
│   All-at-once:  100% × minutes × minutes = HIGH RISK                        │
│   Canary:       10% × seconds × seconds = LOW RISK                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

Three questions define your deployment strategy:

1. **How many users see the new version immediately?** (Blast radius)
2. **How fast can you detect problems?** (Observability)
3. **How fast can you undo the deployment?** (Rollback speed)

---

## Strategy 1: Basic Deployment (Recreate)

The simplest approach: stop the old version, start the new one.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RECREATE DEPLOYMENT                                  │
│                                                                              │
│   Time 0:    [  OLD v1 RUNNING  ]     ← Serving traffic                     │
│                                                                              │
│   Time 1:    [  OLD v1 STOPPED  ]     ← Downtime begins                     │
│                                                                              │
│   Time 2:    [  NEW v2 STARTING ]     ← Starting new version                │
│                                                                              │
│   Time 3:    [  NEW v2 RUNNING  ]     ← Serving traffic again               │
│                                                                              │
│              ←──── DOWNTIME ────→                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Characteristics

|Aspect|Value|
|---|---|
|**Downtime**|Yes (seconds to minutes)|
|**Risk**|High (100% of users hit new version immediately)|
|**Rollback**|Redeploy old version (slow)|
|**Infrastructure cost**|1x (no extra resources)|
|**Complexity**|Minimal|

### When to Use

- Development/staging environments
- Internal tools with low uptime requirements
- Scheduled maintenance windows
- Applications that can tolerate brief outages

### When to Avoid

- Production systems with SLAs
- User-facing applications
- Systems where downtime costs money

---

## Strategy 2: Blue-Green Deployment

Maintain two identical environments. One serves traffic (Blue), one waits with the new version (Green). Switch instantly.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BLUE-GREEN DEPLOYMENT                                 │
│                                                                              │
│                         LOAD BALANCER                                        │
│                              │                                               │
│              ┌───────────────┴───────────────┐                              │
│              │                               │                              │
│              ▼                               ▼                              │
│       ┌─────────────┐                 ┌─────────────┐                       │
│       │    BLUE     │                 │   GREEN     │                       │
│       │    (v1)     │                 │    (v2)     │                       │
│       │  [ACTIVE]   │                 │  [STANDBY]  │                       │
│       └─────────────┘                 └─────────────┘                       │
│                                                                              │
│   Step 1: Blue serves all traffic. Green has new version.                   │
│   Step 2: Test Green thoroughly (health checks, smoke tests).               │
│   Step 3: Switch load balancer to Green.                                    │
│   Step 4: Blue becomes standby. Instant rollback available.                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### The Switch

The critical moment is the load balancer switch:

```
BEFORE SWITCH:
  User Request → Load Balancer → Blue (v1) → Response

AFTER SWITCH:
  User Request → Load Balancer → Green (v2) → Response

ROLLBACK (if problems):
  Switch load balancer back to Blue → Instant recovery
```

### Characteristics

|Aspect|Value|
|---|---|
|**Downtime**|Zero|
|**Risk**|Low (can test before switching)|
|**Rollback**|Instant (switch back to Blue)|
|**Infrastructure cost**|2x during deployment|
|**Complexity**|Moderate|

### When to Use

- Production systems requiring zero downtime
- Applications where instant rollback is critical
- Teams that can afford temporary double infrastructure
- Deployments where you want to test in production-like environment before switching

### When to Avoid

- Stateful applications with complex data migration (both environments need same data)
- Cost-constrained environments where 2x infrastructure is prohibitive
- Very frequent deployments (constant 2x cost)

### Implementation Approaches

**Platform-managed** (easiest):

- Railway, Render, Fly.io handle this automatically
- Push code → Platform deploys to new environment → Switches traffic

**Load balancer configuration**:

- AWS ALB: Update target group
- Nginx: Change upstream server
- Kubernetes: Update service selector

**DNS-based** (simplest but slowest):

- Point DNS from blue.example.com to green.example.com
- Risk: DNS propagation takes time (not truly instant)

---

## Strategy 3: Canary Deployment

Deploy the new version to a small percentage of traffic. Monitor. Gradually increase.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CANARY DEPLOYMENT                                    │
│                                                                              │
│                         LOAD BALANCER                                        │
│                              │                                               │
│                         ┌────┴────┐                                         │
│                         │ 90%/10% │                                         │
│              ┌──────────┴─────────┴──────────┐                              │
│              │                               │                              │
│              ▼                               ▼                              │
│       ┌─────────────┐                 ┌─────────────┐                       │
│       │    OLD      │                 │   CANARY    │                       │
│       │    (v1)     │                 │    (v2)     │                       │
│       │    90%      │                 │    10%      │                       │
│       └─────────────┘                 └─────────────┘                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### The Gradual Rollout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CANARY PROGRESSION                                    │
│                                                                              │
│   Stage 1:  v1: 100%  |  v2: 0%     ← Deploy canary                         │
│                                                                              │
│   Stage 2:  v1: 90%   |  v2: 10%    ← Monitor for 15 min                    │
│             ✓ Error rate normal                                             │
│             ✓ Latency normal                                                │
│                                                                              │
│   Stage 3:  v1: 75%   |  v2: 25%    ← Monitor for 15 min                    │
│             ✓ Error rate normal                                             │
│             ✓ Latency normal                                                │
│                                                                              │
│   Stage 4:  v1: 50%   |  v2: 50%    ← Monitor for 30 min                    │
│             ✓ Error rate normal                                             │
│             ✓ Latency normal                                                │
│                                                                              │
│   Stage 5:  v1: 0%    |  v2: 100%   ← Rollout complete                      │
│                                                                              │
│   IF PROBLEMS AT ANY STAGE:                                                 │
│   → Route 100% back to v1 immediately                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Characteristics

|Aspect|Value|
|---|---|
|**Downtime**|Zero|
|**Risk**|Very low (only small % affected initially)|
|**Rollback**|Fast (route traffic away from canary)|
|**Infrastructure cost**|1.1x to 2x depending on canary size|
|**Complexity**|Higher (requires traffic splitting, monitoring)|

### When to Use

- High-risk changes (new features, major refactors)
- Applications with high traffic (statistical significance)
- Teams with strong monitoring/observability
- When you need real-world validation before full rollout

### When to Avoid

- Low-traffic applications (can't detect problems with 10% of 100 requests/day)
- Simple changes where risk is well understood
- Teams without monitoring infrastructure

### Canary Selection: Random vs Targeted

**Random** (default):

- 10% of all requests go to canary
- Simple to implement
- Statistically representative

**Targeted** (advanced):

- Internal users first
- Beta testers
- Specific regions
- Employees only

```python
# Pseudocode: targeted canary
def route_request(user_id: str) -> str:
    if user_id in INTERNAL_USERS:
        return "canary"
    if user_id in BETA_TESTERS:
        return "canary"
    if random.random() < 0.10:  # 10% of remaining
        return "canary"
    return "stable"
```

---

## Strategy 4: Rolling Deployment

Update instances one at a time. At any moment, some instances run old version, some run new.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ROLLING DEPLOYMENT                                    │
│                                                                              │
│   Time 0:  [v1] [v1] [v1] [v1]     ← All old                                │
│                                                                              │
│   Time 1:  [v2] [v1] [v1] [v1]     ← One updated                            │
│                                                                              │
│   Time 2:  [v2] [v2] [v1] [v1]     ← Two updated                            │
│                                                                              │
│   Time 3:  [v2] [v2] [v2] [v1]     ← Three updated                          │
│                                                                              │
│   Time 4:  [v2] [v2] [v2] [v2]     ← All new                                │
│                                                                              │
│   Load balancer distributes traffic across all healthy instances.           │
│   During rollout, users may hit v1 or v2 depending on which instance.       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Characteristics

|Aspect|Value|
|---|---|
|**Downtime**|Zero|
|**Risk**|Medium (gradual, but version mixing)|
|**Rollback**|Moderate (reverse the rolling update)|
|**Infrastructure cost**|1x (no extra resources)|
|**Complexity**|Low to moderate|

### When to Use

- Multiple instances of a stateless service
- Changes that are backward-compatible
- Kubernetes deployments (default behavior)
- Applications where mixed versions are acceptable

### When to Avoid

- Single-instance deployments (becomes recreate)
- Breaking API changes
- Changes where v1 and v2 can't coexist
- Stateful applications with version-specific data formats

### The Version Mixing Problem

During a rolling deployment, both versions serve traffic simultaneously:

```
User A request → Instance 1 (v2) → Response A
User A request → Instance 3 (v1) → Response B  ← Different behavior!
```

This is fine if:

- Both versions behave identically for existing functionality
- New features in v2 are additive (not breaking)

This breaks if:

- v2 changes response format
- v2 removes functionality v1 had
- Client expects consistent behavior within a session

---

## Strategy Comparison

|Strategy|Downtime|Risk|Rollback Speed|Cost|Complexity|Best For|
|---|---|---|---|---|---|---|
|**Recreate**|Yes|High|Slow (redeploy)|1x|Low|Dev/staging|
|**Blue-Green**|No|Low|Instant|2x|Moderate|Most production|
|**Canary**|No|Very Low|Fast|~1.1x|High|High-risk changes|
|**Rolling**|No|Medium|Moderate|1x|Low|Stateless services|

### Decision Tree

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CHOOSING A DEPLOYMENT STRATEGY                            │
│                                                                              │
│   Can you tolerate downtime?                                                │
│   └── Yes → Recreate (simplest)                                             │
│   └── No ↓                                                                  │
│                                                                              │
│   Is the change high-risk?                                                  │
│   └── Yes → Canary (validate with small %)                                  │
│   └── No ↓                                                                  │
│                                                                              │
│   Can you afford 2x infrastructure temporarily?                             │
│   └── Yes → Blue-Green (instant rollback)                                   │
│   └── No ↓                                                                  │
│                                                                              │
│   Do you have multiple instances?                                           │
│   └── Yes → Rolling (gradual update)                                        │
│   └── No → Blue-Green (even temporarily)                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## AI-Specific Deployment Concerns

AI applications have unique risks that standard deployment thinking doesn't cover.

### Prompt Changes Are High-Risk

A one-word prompt change can break your entire system:

```python
# v1: Works fine
SYSTEM_PROMPT = "You are a helpful research assistant."

# v2: Breaks JSON parsing downstream
SYSTEM_PROMPT = "You are a helpful research assistant. Always respond conversationally."
```

**Recommendation**: Treat prompt changes as high-risk deployments. Use canary or thorough staging testing.

### Model Endpoint Versioning

Cloud providers update model versions. Your code might silently start using a different model:

```python
# Dangerous: May change behavior without code change
model = "gpt-4o"

# Safe: Pinned to specific version
model = "gpt-4o-2024-08-06"
```

**Recommendation**: Always pin model versions in production. Test model updates explicitly before deploying.

### Embedding Model Consistency

Embeddings are model-specific. Mixing models breaks retrieval:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EMBEDDING MODEL MISMATCH                                  │
│                                                                              │
│   Index built with: text-embedding-ada-002                                  │
│   Query embedded with: text-embedding-3-small                               │
│                                                                              │
│   Result: Semantic similarity is meaningless.                               │
│           Retrieval returns garbage.                                        │
│                                                                              │
│   RULE: Never mix embedding models in the same index.                       │
│         Embedding model change = full reindex.                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deployment implication**: If you change embedding models, you need to:

1. Build new index with new embeddings
2. Deploy new code pointing to new index
3. Keep old index available for rollback

This is effectively a blue-green deployment for your vector store.

### Response Format Changes

If your agent returns structured data, format changes break consumers:

```python
# v1 response
{"answer": "Paris", "confidence": 0.95}

# v2 response (breaking change)
{"response": {"text": "Paris", "score": 0.95}}
```

**Recommendation**:

- Version your API contracts
- Use canary deployment for format changes
- Maintain backward compatibility during transition

### LLM API Rate Limits and Costs

Deployment can spike API usage:

```
Normal traffic: 100 requests/min
Deployment + retries + health checks: 500 requests/min
→ Hit rate limit
→ Deployment looks broken (but it's just throttled)
```

**Recommendation**:

- Monitor API usage during deployment
- Use exponential backoff
- Consider separate API keys for health checks

---

## Platform-Managed Deployments

Modern deployment platforms handle strategy automatically:

|Platform|Default Strategy|Configuration|
|---|---|---|
|**Railway**|Blue-Green|Automatic|
|**Render**|Blue-Green|Automatic|
|**Fly.io**|Rolling|Configurable|
|**Kubernetes**|Rolling|Configurable (RollingUpdate, Recreate)|
|**AWS ECS**|Rolling|Configurable|
|**Vercel**|Blue-Green (preview deploys)|Automatic|

For most AI applications starting out, **platform-managed blue-green** is the right choice:

- Zero configuration
- Zero downtime
- Easy rollback
- No operational overhead

Graduate to canary when:

- You have traffic to make it meaningful
- You have monitoring to detect issues
- Changes are high-risk enough to justify complexity

---

## Key Takeaways

1. **Deployment strategy determines your risk exposure**: How many users are affected if the deployment is broken?
    
2. **Blue-Green is the default for production**: Zero downtime, instant rollback, moderate complexity.
    
3. **Canary for high-risk changes**: Validate with real traffic before full rollout.
    
4. **Rolling for stateless services**: Efficient but requires backward compatibility.
    
5. **Recreate only for non-critical environments**: Simplest but has downtime.
    
6. **AI-specific risks require extra caution**:
    
    - Prompt changes can break behavior silently
    - Model versions must be pinned
    - Embedding models can never be mixed in the same index
    - Response format changes need API versioning
7. **Start with platform-managed deployments**: Railway, Render, and similar platforms handle blue-green automatically.
    

---

## What's Next

Note 4 covers **rollback strategies**—what happens when your deployment fails and you need to recover quickly. Automatic triggers, rollback mechanisms, and the tricky edge cases (especially database migrations).