# Rollback Mechanisms and Triggers

## Why Rollback Is Critical

Deployments fail. This isn't pessimism—it's operational reality. The question isn't whether you'll need to rollback, but how fast you can do it when you need to.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     INCIDENT DURATION EQUATION                               │
│                                                                              │
│   Total Impact = Time to Detect + Time to Decide + Time to Rollback         │
│                                                                              │
│   Fast detection (monitoring)     → 2 minutes                               │
│   Fast decision (clear triggers)  → 1 minute                                │
│   Fast rollback (blue-green)      → 30 seconds                              │
│   ────────────────────────────────────────────                              │
│   Total incident: 3.5 minutes                                               │
│                                                                              │
│   vs.                                                                        │
│                                                                              │
│   Slow detection (user reports)   → 30 minutes                              │
│   Slow decision (who decides?)    → 15 minutes                              │
│   Slow rollback (redeploy)        → 10 minutes                              │
│   ────────────────────────────────────────────                              │
│   Total incident: 55 minutes                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

The difference between a 4-minute incident and a 55-minute incident is the difference between "minor blip" and "users leaving, trust eroding, revenue lost."

---

## Automatic Rollback Triggers

Automatic triggers remove human decision time from the equation. When conditions are met, rollback happens without waiting for someone to notice and decide.

### Error Rate Threshold

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ERROR RATE TRIGGER                                    │
│                                                                              │
│   Normal error rate: 0.1% (baseline)                                        │
│                                                                              │
│   Trigger condition:                                                        │
│   IF error_rate > 5% FOR 2 consecutive minutes                              │
│   THEN trigger rollback                                                     │
│                                                                              │
│   Why 2 minutes?                                                            │
│   - Too short: false positives from temporary spikes                        │
│   - Too long: users suffer while you wait                                   │
│                                                                              │
│   Why 5%?                                                                   │
│   - Low enough to catch real problems                                       │
│   - High enough to avoid noise                                              │
│   - Calibrate based on your normal error rate                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Latency Threshold

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       LATENCY TRIGGER                                        │
│                                                                              │
│   Baseline p95 latency: 500ms                                               │
│                                                                              │
│   Trigger condition:                                                        │
│   IF p95_latency > 1500ms (3x baseline) FOR 2 consecutive minutes           │
│   THEN trigger rollback                                                     │
│                                                                              │
│   Why p95, not average?                                                     │
│   - Average hides outliers                                                  │
│   - p95 catches "some users are suffering" scenarios                        │
│   - p99 may be too sensitive to noise                                       │
│                                                                              │
│   Why 3x baseline?                                                          │
│   - Captures meaningful degradation                                         │
│   - Accounts for normal variance                                            │
│   - Adjust based on your SLOs                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Health Check Failures

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     HEALTH CHECK TRIGGER                                     │
│                                                                              │
│   Health endpoint: GET /health                                              │
│   Check frequency: Every 10 seconds                                         │
│                                                                              │
│   Trigger condition:                                                        │
│   IF 3 consecutive health checks fail                                       │
│   THEN mark instance unhealthy                                              │
│                                                                              │
│   IF all instances unhealthy                                                │
│   THEN trigger rollback                                                     │
│                                                                              │
│   Health check implementation:                                              │
│   - Return 200 if app can serve requests                                    │
│   - Check critical dependencies (database, cache)                           │
│   - Don't check non-critical services                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

Example health check endpoint:

```python
# Health check that verifies critical dependencies
@app.get("/health")
async def health_check():
    checks = {
        "database": check_database(),
        "vector_store": check_vector_store(),
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        content={"status": "healthy" if all_healthy else "unhealthy", "checks": checks},
        status_code=status_code
    )

def check_database() -> bool:
    try:
        db.execute("SELECT 1")
        return True
    except Exception:
        return False

def check_vector_store() -> bool:
    try:
        vector_store.heartbeat()
        return True
    except Exception:
        return False
```

### Critical Alerts

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ALERT-BASED TRIGGER                                     │
│                                                                              │
│   Integration with monitoring system (PagerDuty, Opsgenie, etc.)            │
│                                                                              │
│   If alert severity == CRITICAL                                             │
│   AND alert relates to deployed service                                     │
│   AND deployment happened in last 30 minutes                                │
│   THEN trigger automatic rollback                                           │
│                                                                              │
│   This catches issues that don't fit simple thresholds:                     │
│   - Memory leak (gradual, then sudden)                                      │
│   - Downstream service overwhelmed                                          │
│   - Business metric anomaly                                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Manual Rollback Triggers

Some issues can't be caught automatically. These require human judgment.

### User Reports

```
Users: "The search results are garbage."
Monitoring: Everything looks fine.

Why monitoring missed it:
- Error rate: 0% (app returned responses)
- Latency: Normal (responses were fast)
- Health checks: Passing

The problem: Semantic failure.
The app worked, but the outputs were wrong.
```

For AI applications, this is common. The system functions technically but produces poor results.

### Quality Degradation

AI-specific quality issues that trigger manual rollback:

|Issue|Symptom|Why Automatic Triggers Miss It|
|---|---|---|
|**Hallucinations increased**|Users report false information|No technical error|
|**Response quality dropped**|Outputs less helpful|Subjective quality|
|**Prompt broke edge cases**|Works for most, fails for some|Aggregate metrics look fine|
|**Wrong model loaded**|Different behavior|No errors, just different|

### Business Decision

Sometimes rollback is a business call, not a technical one:

- Feature not ready (shipped by mistake)
- Negative user feedback (feature works but users hate it)
- Legal/compliance issue discovered
- Competitive concern (revealed roadmap)

---

## Rollback Mechanisms

Four primary ways to rollback, ordered by speed:

### Mechanism 1: Load Balancer Switch (Instant)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     LOAD BALANCER SWITCH                                     │
│                                                                              │
│   BEFORE:                                                                   │
│   Load Balancer ──▶ Green (v2, broken)                                      │
│                     Blue (v1, standby)                                      │
│                                                                              │
│   ROLLBACK:                                                                 │
│   Load Balancer ──▶ Blue (v1, now active)                                   │
│                     Green (v2, now standby)                                 │
│                                                                              │
│   Time: < 30 seconds                                                        │
│                                                                              │
│   Requirement: Blue-Green deployment                                        │
│   Requirement: Old environment still running                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Pros**: Instant, no rebuild required. **Cons**: Only works with blue-green, requires keeping old environment running.

### Mechanism 2: Feature Flag Disable (Instant)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FEATURE FLAG DISABLE                                     │
│                                                                              │
│   Code deployed:                                                            │
│   if feature_flags.is_enabled("new_rag_pipeline"):                          │
│       return new_rag_pipeline(query)                                        │
│   else:                                                                     │
│       return old_rag_pipeline(query)                                        │
│                                                                              │
│   ROLLBACK:                                                                 │
│   Disable "new_rag_pipeline" flag in dashboard                              │
│   All users immediately get old_rag_pipeline                                │
│                                                                              │
│   Time: < 10 seconds                                                        │
│                                                                              │
│   Requirement: Feature flag infrastructure                                  │
│   Requirement: Both code paths deployed                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Pros**: Instant, granular control, no deployment needed. **Cons**: Requires flag infrastructure, code complexity.

### Mechanism 3: Container Rollback (Fast)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CONTAINER ROLLBACK                                       │
│                                                                              │
│   Current: Running image myapp:abc123 (broken)                              │
│   Previous: Image myapp:def456 exists in registry                           │
│                                                                              │
│   ROLLBACK:                                                                 │
│   Deploy myapp:def456 instead of myapp:abc123                               │
│                                                                              │
│   Time: 30 seconds - 2 minutes                                              │
│                                                                              │
│   Requirement: Previous image in registry (immutable tags)                  │
│   Requirement: Platform supports image deployment                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

Platform-specific commands:

```bash
# Kubernetes
kubectl rollout undo deployment/research-assistant

# Railway
railway up --image myapp:def456

# Fly.io
fly deploy --image myapp:def456
```

**Pros**: Fast, doesn't require rebuild, immutable artifacts. **Cons**: Platform-dependent, still requires deployment time.

### Mechanism 4: Re-deploy Previous Version (Slow)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     RE-DEPLOY PREVIOUS VERSION                               │
│                                                                              │
│   Current: Running code from commit abc123 (broken)                         │
│   Previous: Commit def456 worked fine                                       │
│                                                                              │
│   ROLLBACK:                                                                 │
│   1. Checkout def456                                                        │
│   2. Run full CI/CD pipeline                                                │
│   3. Build new image                                                        │
│   4. Deploy                                                                 │
│                                                                              │
│   Time: 5-15 minutes                                                        │
│                                                                              │
│   Requirement: None (always available)                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```bash
# Manual rollback via git
git checkout def456
git push origin HEAD:main --force  # Dangerous, but works

# Better: Revert commit and push
git revert abc123
git push origin main
# Pipeline runs normally
```

**Pros**: Always works, no special infrastructure. **Cons**: Slow, requires full pipeline run.

### Mechanism Comparison

|Mechanism|Speed|Requirements|Reliability|
|---|---|---|---|
|**Load Balancer Switch**|< 30s|Blue-Green deployment|High|
|**Feature Flag Disable**|< 10s|Flag infrastructure|High|
|**Container Rollback**|30s - 2min|Image in registry|High|
|**Re-deploy Previous**|5-15min|None|Always works|

**Recommendation**: Have multiple mechanisms available. Use the fastest one that applies to your situation.

---

## Rollback Gotchas

Rollback isn't always clean. Here are the edge cases that cause problems.

### Database Migrations

The most common rollback blocker.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MIGRATION ROLLBACK PROBLEM                               │
│                                                                              │
│   v1 code expects:                                                          │
│   users table: id, name, email                                              │
│                                                                              │
│   v2 migration adds:                                                        │
│   users table: id, name, email, phone (new column)                          │
│                                                                              │
│   v2 code expects phone column to exist.                                    │
│                                                                              │
│   SCENARIO: v2 deployed, migration runs, then v2 breaks.                    │
│                                                                              │
│   If you rollback to v1:                                                    │
│   - Database still has phone column                                         │
│   - v1 code doesn't know about it                                           │
│   - Usually fine (v1 ignores extra columns)                                 │
│                                                                              │
│   BUT if migration was:                                                     │
│   - REMOVE column email                                                     │
│   - RENAME column name → full_name                                          │
│                                                                              │
│   Rollback to v1:                                                           │
│   - v1 expects columns that no longer exist                                 │
│   - v1 is broken                                                            │
│   - You need a reverse migration                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Design principle**: Make migrations backward-compatible.

```
SAFE MIGRATIONS (old code still works):
✅ Add new column (old code ignores it)
✅ Add new table (old code doesn't query it)
✅ Add new index (old code benefits)

DANGEROUS MIGRATIONS (old code breaks):
❌ Remove column (old code queries it)
❌ Rename column (old code uses old name)
❌ Change column type (old code assumes old type)
❌ Add NOT NULL without default (old code inserts fail)
```

**Pattern: Expand-Contract Migration**

For breaking changes, split into two deployments:

```
Step 1 (Expand):
- Add new column
- Update new code to write to both old and new columns
- Deploy, verify

Step 2 (Contract):
- Migrate data from old to new column
- Update code to use only new column
- Deploy, verify

Step 3 (Cleanup):
- Remove old column
- Deploy
```

Now you can rollback at any step without data loss.

### External State Inconsistency

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EXTERNAL STATE PROBLEM                                   │
│                                                                              │
│   v2 deployed:                                                              │
│   - Wrote entries to cache with new format                                  │
│   - Enqueued messages to queue with new schema                              │
│   - Updated third-party service config                                      │
│                                                                              │
│   v2 breaks, rollback to v1:                                                │
│   - Cache has v2-format entries (v1 can't read)                             │
│   - Queue has v2-schema messages (v1 can't process)                         │
│   - Third-party still has v2 config                                         │
│                                                                              │
│   Result: v1 is "running" but partially broken                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Mitigations**:

- Clear caches on rollback (if safe)
- Design queue messages to be version-tolerant
- Version external state changes separately from code

### User Experience Discontinuity

```
User A's experience:
10:00 - Uses new feature (v2)
10:05 - Rollback happens
10:06 - Feature disappears (v1)
10:07 - User confused, files support ticket
```

This is unavoidable with any rollback. Mitigations:

- Feature flags let you hide features without full rollback
- Clear user communication for major features
- Support team awareness of rollback

---

## Designing for Rollback

Build rollback-friendliness into your system from the start.

### Principle 1: Backward-Compatible Migrations

Old code should work with new schema:

```sql
-- WRONG: Breaking change
ALTER TABLE users DROP COLUMN email;

-- RIGHT: Additive change
ALTER TABLE users ADD COLUMN phone VARCHAR(20);
-- Old code ignores phone, new code uses it
```

### Principle 2: Versioned Artifacts

Every deployment should produce an immutable, versioned artifact:

```yaml
# Tag with git SHA, not "latest"
docker build -t myapp:${GITHUB_SHA} .

# Why:
# myapp:abc123 → exactly this code, forever
# myapp:latest → who knows what this is now?
```

### Principle 3: Keep Previous Version Running

After blue-green switch, don't immediately terminate the old environment:

```
Deploy v2 to Green
Switch traffic to Green
Wait 30 minutes           ← v1 (Blue) still running
Verify v2 is healthy
Then terminate v1         ← Now safe
```

### Principle 4: Test Rollback Procedure

Most teams test deployments. Few test rollbacks.

```
Pre-production checklist:
☐ Deploy to staging
☐ Run smoke tests
☐ Verify monitoring
☐ Rollback to previous version    ← THIS ONE
☐ Verify rollback works
☐ Re-deploy new version
☐ Promote to production
```

---

## Rollback Runbook Template

Document your rollback procedure before you need it.

```markdown
# Rollback Runbook: Research Assistant

## Quick Reference
- Primary rollback mechanism: Load balancer switch
- Fallback mechanism: Container rollback
- Estimated rollback time: < 1 minute (LB switch), < 3 minutes (container)

## Who Can Trigger Rollback
- On-call engineer (any severity)
- Team lead (business decisions)
- Automated triggers (see below)

## Automatic Rollback Triggers
- Error rate > 5% for 2 consecutive minutes
- p95 latency > 1500ms for 2 consecutive minutes
- 3 consecutive health check failures

## Manual Rollback: Load Balancer Switch
1. Go to [Platform Dashboard URL]
2. Navigate to Load Balancer → Target Groups
3. Switch active target group from "green" to "blue"
4. Verify traffic flowing to blue: check [monitoring URL]

## Manual Rollback: Container Rollback
1. Get previous image tag:
   ```bash
   # From deployment history
   railway logs --deployment previous
   # Note the image tag: myapp:def456
```

2. Deploy previous image:
    
    ```bash
    railway up --image myapp:def456
    ```
    
3. Verify deployment:
    
    ```bash
    curl https://research-assistant.example.com/health
    ```
    

## Post-Rollback Checklist

☐ Verify health endpoint returns 200 ☐ Verify error rate returned to baseline ☐ Verify latency returned to baseline ☐ Check key user flows manually ☐ Notify team in #incidents Slack channel

## Who to Notify

- Slack: #incidents (immediate)
- Slack: #engineering (within 30 minutes)
- Email: stakeholders@company.com (if user-facing impact > 5 minutes)

## Post-Incident Actions

1. Create incident ticket
2. Schedule post-mortem
3. Document root cause
4. Update runbook if needed

````

---

## AI-Specific Rollback Concerns

AI systems have rollback considerations that traditional applications don't.

### Prompt Rollback

Prompts are code. They need versioning and rollback capability.

```python
# Version prompts explicitly
PROMPTS = {
    "v1": {
        "system": "You are a helpful research assistant.",
        "user_template": "Answer this question: {query}"
    },
    "v2": {
        "system": "You are a helpful research assistant. Always cite sources.",
        "user_template": "Based on the context, answer: {query}\n\nContext: {context}"
    }
}

# Config or feature flag controls active version
active_prompt_version = config.get("prompt_version", "v1")
prompt = PROMPTS[active_prompt_version]
````

**Rollback**: Change `prompt_version` config. No code deployment needed.

### Model Rollback

If you pin model versions (you should), rollback means reverting the version:

```python
# Config-driven model selection
MODEL_CONFIG = {
    "production": "gpt-4o-2024-08-06",
    "rollback": "gpt-4o-2024-05-13"
}

model = MODEL_CONFIG[config.get("model_variant", "production")]
```

**Rollback**: Change `model_variant` to "rollback".

### Embedding Index Rollback

This is the tricky one. If you changed embedding models, you need the old index.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EMBEDDING ROLLBACK                                       │
│                                                                              │
│   v1: Using text-embedding-ada-002, index: "docs-ada-v1"                    │
│   v2: Using text-embedding-3-small, index: "docs-3small-v1"                 │
│                                                                              │
│   v2 deployed, switched to new index.                                       │
│   v2 breaks (unrelated reason).                                             │
│                                                                              │
│   To rollback:                                                              │
│   - v1 code needs "docs-ada-v1" index                                       │
│   - If you deleted it: can't rollback without reindexing                    │
│   - If you kept it: switch index config back                                │
│                                                                              │
│   Rule: Keep old indexes until confident in new version                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Pattern**: Config-driven index selection:

```python
INDEX_CONFIG = {
    "production": "docs-3small-v1",
    "rollback": "docs-ada-v1"
}

index_name = INDEX_CONFIG[config.get("index_variant", "production")]
vector_store = get_collection(index_name)
```

### Config Rollback

Many AI-specific settings live in config, not code:

- Model versions
- Temperature, max tokens
- Retrieval parameters (top_k, similarity threshold)
- Prompt versions

**Pattern**: Version your config files:

```yaml
# config/v1.yaml
model: gpt-4o-2024-05-13
temperature: 0.7
retrieval:
  top_k: 5
  threshold: 0.7

# config/v2.yaml
model: gpt-4o-2024-08-06
temperature: 0.5
retrieval:
  top_k: 10
  threshold: 0.6
```

**Rollback**: Switch which config file is loaded. No code change needed.

---

## Key Takeaways

1. **Rollback speed determines incident severity**: Invest in fast rollback mechanisms.
    
2. **Automatic triggers remove human decision latency**: Error rate, latency, health checks.
    
3. **Manual triggers catch what automation misses**: Quality issues, business decisions.
    
4. **Multiple mechanisms, ordered by speed**:
    
    - Load balancer switch (instant)
    - Feature flag disable (instant)
    - Container rollback (fast)
    - Re-deploy (slow, but always works)
5. **Database migrations are the main rollback blocker**: Make them backward-compatible.
    
6. **Test your rollback procedure**: Not just deployment.
    
7. **AI-specific concerns**:
    
    - Version prompts, models, and configs
    - Keep old embedding indexes until confident
    - Config-driven rollback is faster than code deployment
8. **Document rollback in a runbook**: Before you need it, not during the incident.
    

---

## What's Next

Note 5 covers **feature flags**—how to decouple deployment from release, enabling instant rollback and gradual rollout at the feature level rather than the deployment level.