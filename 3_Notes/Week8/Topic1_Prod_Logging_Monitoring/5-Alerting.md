# Note 5: Alerting — Rules, Thresholds, and Avoiding Alert Fatigue

## Purpose of Alerting: Know Before Users Complain

Dashboards tell you the system is broken when you're looking at them. Alerts tell you the system is broken when you're not.

The goal is simple: **detect problems before users report them**.

If you're learning about outages from customer complaints, Twitter, or your CEO, your alerting has failed. Good alerting gives you a head start — ideally enough time to diagnose and fix before impact is widespread.

But there's a tension: too many alerts and you'll ignore them all. Too few and you'll miss real problems. The art of alerting is finding the balance — **every alert should mean something**.

---

## Alert Design Principles

Before writing any alert rules, internalize these three principles:

### 1. Actionable

**Every alert should have a clear response.**

If an alert fires and the on-call engineer asks "what am I supposed to do about this?" — it's a bad alert.

Good alert:

> "Error rate exceeded 5% for 5 minutes" **Action:** Check logs for error type, check external API status, consider rolling back recent deployment.

Bad alert:

> "Memory usage above 60%" **Action:** Uh... wait? This might be normal. Or it might be a leak. Who knows?

If you can't write a runbook entry for an alert, it shouldn't exist.

### 2. Meaningful

**If you routinely ignore it, it shouldn't be an alert.**

Alerts that cry wolf train engineers to dismiss all alerts. Every false positive erodes trust in the system.

Signs of a meaningless alert:

- "Oh, that one fires every Tuesday. Just ignore it."
- "It's been firing for 3 days. We're looking into it eventually."
- "That threshold is way too sensitive. We should fix it." (But no one does.)

If an alert isn't worth investigating, delete it or fix its threshold.

### 3. Timely

**Fast enough to act, not so fast it's noisy.**

An alert that fires after 10 seconds of elevated error rate might catch transient spikes that resolve themselves. An alert that waits 30 minutes might miss a window where you could have prevented impact.

The `for` clause in alert rules exists for this reason. It requires a condition to persist before firing:

```yaml
# Only fire if error rate > 5% for 5 continuous minutes
- alert: HighErrorRate
  expr: sum(rate(llm_requests_total{status="error"}[5m])) / sum(rate(llm_requests_total[5m])) > 0.05
  for: 5m  # Must persist for 5 minutes
```

This prevents alerts from firing on brief spikes that self-resolve.

---

## Key Alerts for LLM Systems

Here are the essential alerts for an LLM application:

### 1. High Error Rate (Critical)

```yaml
# Reference: Prometheus alerting rules documentation
# https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/

groups:
  - name: llm_alerts
    rules:
      - alert: LLMHighErrorRate
        expr: |
          sum(rate(llm_requests_total{status="error"}[5m])) 
          / 
          sum(rate(llm_requests_total[5m])) 
          > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "LLM error rate exceeded 5%"
          description: "Error rate is {{ $value | humanizePercentage }} over the last 5 minutes."
          runbook_url: "https://wiki.example.com/runbooks/llm-high-error-rate"
```

**Why this matters:** 5% error rate means 1 in 20 users is getting a failure. At scale, that's hundreds or thousands of failed requests per hour.

**Threshold rationale:**

- < 1%: Normal baseline for most systems
- 1-5%: Elevated, worth watching but not paging
- > 5%: Definitely something wrong, needs immediate attention
    

### 2. Latency Degradation (Warning)

```yaml
      - alert: LLMLatencyDegraded
        expr: |
          histogram_quantile(0.95, sum by (le) (rate(llm_request_latency_seconds_bucket[5m])))
          > 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "p95 latency exceeded 5 seconds"
          description: "95th percentile latency is {{ $value | humanizeDuration }} over the last 10 minutes."
          runbook_url: "https://wiki.example.com/runbooks/llm-latency-degraded"
```

**Why this matters:** Slow responses frustrate users and can cause timeouts in downstream systems. A 10-minute `for` clause prevents alerting on brief spikes.

**Threshold rationale:** 5 seconds is generous for LLM systems. Adjust based on your SLO.

### 3. Cost Spike (Warning)

```yaml
      - alert: LLMCostSpike
        expr: |
          sum(rate(llm_cost_usd_total[1h])) * 3600
          > 
          2 * avg_over_time(sum(rate(llm_cost_usd_total[1h]))[24h:1h]) * 3600
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "LLM cost spike detected"
          description: "Hourly cost is 2x the 24-hour average."
          runbook_url: "https://wiki.example.com/runbooks/llm-cost-spike"
```

**Why this matters:** A bug that sends verbose prompts or loops can burn through budget in hours. The 2x threshold catches genuine anomalies without alerting on normal daily variation.

**Alternative simpler version:**

```yaml
      - alert: LLMHourlyCostHigh
        expr: sum(rate(llm_cost_usd_total[1h])) * 3600 > 10  # More than $10/hour
        for: 30m
        labels:
          severity: warning
```

### 4. Single User Abuse (Warning)

```yaml
      - alert: LLMUserAbuse
        expr: |
          sum by (user_id) (increase(llm_requests_total[1h])) > 500
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "User {{ $labels.user_id }} exceeding request limits"
          description: "User has made {{ $value }} requests in the last hour."
          runbook_url: "https://wiki.example.com/runbooks/llm-user-abuse"
```

**Why this matters:** One user hammering your API can affect all users (rate limits, cost, capacity).

**Note:** This requires `user_id` as a label, which has cardinality concerns (see Note 3). An alternative is to track this in application logs and alert from your log aggregator.

### 5. Budget Approaching (Info)

```yaml
      - alert: LLMDailyBudgetApproaching
        expr: sum(llm_cost_usd_total) > 80  # $80 of $100 daily budget
        labels:
          severity: info
        annotations:
          summary: "Daily LLM budget 80% consumed"
          description: "Spent ${{ $value }} of $100 daily budget."
```

**Why this matters:** Gives you advance warning to investigate before hitting hard limits.

---

## Severity Levels: Critical, Warning, Info

Not all alerts deserve the same response. Severity levels route alerts to appropriate channels:

|Severity|Meaning|Response|Channel|
|---|---|---|---|
|**Critical**|Service is down or severely degraded|Wake someone up|PagerDuty, phone call|
|**Warning**|Degradation or concerning trend|Create a ticket, investigate during business hours|Slack, email|
|**Info**|Notable but not urgent|Log it, review periodically|Slack channel, dashboard|

**Critical alerts should be rare.** If you're getting paged nightly, either your system is broken or your thresholds are wrong.

**Example routing in Alertmanager:**

```yaml
# Reference: Prometheus Alertmanager configuration
# https://prometheus.io/docs/alerting/latest/configuration/

route:
  group_by: ['alertname']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default-receiver'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
    - match:
        severity: warning
      receiver: 'slack-warnings'
    - match:
        severity: info
      receiver: 'slack-info'

receivers:
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '<your-pagerduty-key>'
        
  - name: 'slack-warnings'
    slack_configs:
      - channel: '#llm-alerts'
        send_resolved: true
        
  - name: 'slack-info'
    slack_configs:
      - channel: '#llm-info'
        send_resolved: true
        
  - name: 'default-receiver'
    slack_configs:
      - channel: '#llm-alerts'
```

---

## Threshold Selection: The Art of Not Crying Wolf

Setting thresholds is the hardest part of alerting. Too tight and you'll drown in false positives. Too loose and you'll miss real problems.

### The Threshold Spectrum

```
TOO TIGHT                                           TOO LOOSE
    |                                                   |
    v                                                   v
Error rate > 0.1%                               Error rate > 50%
for 30 seconds                                  for 1 hour

Result: Fires on                               Result: Only fires
every tiny blip.                               when system is
Alert fatigue.                                 completely broken.
Alerts ignored.                                Missed problems.
```

### How to Set Initial Thresholds

**Start loose, tighten based on data.**

1. **Look at your baseline.** If error rate normally fluctuates between 0.1% and 0.8%, setting a threshold at 1% will fire on normal variation.
    
2. **Add a buffer.** If baseline is 0.5%, set threshold at 2-3% — well above normal but still catching real problems.
    
3. **Use the `for` clause.** A 2% error rate for 30 seconds might be a blip. For 10 minutes, it's a real issue.
    
4. **Review and adjust.** After 2 weeks, look at:
    
    - How many times did this alert fire?
    - Were those fires actionable?
    - Did we miss any incidents this alert should have caught?

### Example: Latency Threshold

Your system's p95 latency normally sits around 2 seconds:

```
Week 1: Set threshold at 10 seconds (very loose)
  → Fires once, legitimate outage. Good.

Week 2: Tighten to 7 seconds
  → Fires twice, both worth investigating. Good.

Week 3: Tighten to 5 seconds
  → Fires four times, two were blips that self-resolved. 
  → Consider increasing `for` clause to 15 minutes.

Week 4: Keep 5 seconds, `for: 15m`
  → Fires twice, both actionable. Stable.
```

This iterative approach is more effective than guessing.

---

## Alert Fatigue: The Real Danger

Alert fatigue is when engineers stop paying attention to alerts because there are too many, most of which are noise.

**The progression:**

1. System has 50 alerts, 10 of which fire daily
2. Engineers learn which ones to ignore
3. A real critical alert fires, but it looks like the noisy ones
4. Engineer dismisses it, assuming it's another false positive
5. Major outage, could have been prevented

**This is not hypothetical.** Alert fatigue has contributed to real incidents at major companies.

### Signs of Alert Fatigue

- Alerts sit in a channel for hours before anyone looks
- Engineers mute alert channels or filter them to a folder
- Common response to alerts is "oh, that one again"
- Post-mortems reveal alerts fired but were ignored

### The Solution: Fewer, Better Alerts

**Every alert should pass this test:**

> "If this alert fires at 3 AM, will the on-call engineer thank you for waking them up?"

If the answer is "no" or "maybe" — it shouldn't be a paging alert.

**Concrete steps:**

1. **Audit existing alerts.** For each alert:
    
    - How often did it fire last month?
    - What percentage of fires were actionable?
    - If < 80% actionable, fix the threshold or delete it.
2. **Require runbooks.** No alert without a documented response. If you can't write what to do, you can't justify the alert.
    
3. **Set ownership.** Every alert should have a team responsible. If no one owns it, no one will fix it when it's noisy.
    
4. **Review regularly.** Monthly alert review: which alerts fired? Were they useful? What did we miss?
    

### Inhibition and Grouping

Alertmanager provides tools to reduce noise:

**Grouping:** Multiple alerts of the same type are batched into a single notification.

```yaml
route:
  group_by: ['alertname', 'severity']
  group_wait: 30s      # Wait before sending first notification
  group_interval: 5m   # Wait before sending updates
  repeat_interval: 4h  # How often to repeat if not resolved
```

**Inhibition:** One alert suppresses related alerts.

```yaml
inhibit_rules:
  # If the whole service is down, don't also alert about high latency
  - source_match:
      alertname: 'LLMServiceDown'
    target_match:
      alertname: 'LLMLatencyDegraded'
    equal: ['service']
```

If `LLMServiceDown` is firing, there's no point also firing `LLMLatencyDegraded` — you already know there's a problem.

---

## Alerting Tools

### Prometheus Alertmanager

The native alerting solution for Prometheus. Handles:

- Receiving alerts from Prometheus
- Grouping, deduplication, silencing, inhibition
- Routing to notification channels (Slack, PagerDuty, email, webhooks)

Configuration lives in `alertmanager.yml`. Alert rules live in Prometheus config (or separate rule files).

### Grafana Alerts

Grafana can also evaluate alert rules, useful if you're already using Grafana for dashboards. Works with any data source, not just Prometheus.

- Define alerts directly on dashboard panels
- Simpler setup if you don't want a separate Alertmanager
- Less powerful grouping/inhibition than Alertmanager

### PagerDuty, Opsgenie, VictorOps

Dedicated incident management platforms. Use these for:

- On-call scheduling
- Escalation policies (if person A doesn't acknowledge, page person B)
- Incident tracking and post-mortems

Alertmanager routes critical alerts to these; they handle the human workflow.

### Slack / Email

Fine for warnings and info-level alerts. Not appropriate for critical alerts (too easy to miss).

---

## Runbooks: What to Do When the Alert Fires

An alert without a runbook is a trap. The engineer gets paged, opens the alert, and thinks "okay... now what?"

Every alert should link to a runbook that answers:

1. **What does this alert mean?** (Brief explanation)
2. **What's the likely impact?** (Users affected, severity)
3. **What are the common causes?** (Top 3-5 reasons this fires)
4. **How do I investigate?** (Specific commands, dashboards, log queries)
5. **How do I mitigate?** (Immediate steps to reduce impact)
6. **Who should I escalate to?** (If I can't fix it)

### Example Runbook: High Error Rate

````markdown
# Runbook: LLMHighErrorRate

## What this means
Error rate has exceeded 5% for at least 5 minutes. More than 1 in 20 requests are failing.

## Impact
- Users are seeing error messages or timeouts
- Downstream systems may be affected
- Revenue impact if this is customer-facing

## Common causes
1. **External API outage** — Model provider (OpenAI, Anthropic) is down or rate-limiting
2. **Bad deployment** — Recent code change introduced a bug
3. **Vector store unavailable** — RAG retrieval is failing
4. **Resource exhaustion** — Out of memory, connection pool exhausted

## Investigation steps

### Step 1: Check error types in logs
```bash
# Query logs for error breakdown
grep "status=error" /var/log/llm/app.log | jq '.error_type' | sort | uniq -c | sort -rn
````

### Step 2: Check model provider status

- OpenAI: https://status.openai.com
- Anthropic: https://status.anthropic.com

### Step 3: Check recent deployments

- Was there a deployment in the last hour?
- Check deployment history: `kubectl rollout history deployment/llm-service`

### Step 4: Check resource utilization

- Memory: `kubectl top pods`
- Connections: Check database connection pool metrics

## Mitigation

### If external API outage:

- Enable fallback to secondary provider if available
- Consider serving cached responses for common queries
- Communicate outage to stakeholders

### If bad deployment:

- Rollback: `kubectl rollout undo deployment/llm-service`
- Verify error rate drops

### If resource exhaustion:

- Scale up: `kubectl scale deployment/llm-service --replicas=X`
- Restart pods if memory leak: `kubectl rollout restart deployment/llm-service`

## Escalation

- If not resolved in 30 minutes: Page senior engineer
- If customer-facing impact: Notify customer success team

### Example Runbook: Latency Spike

```markdown
# Runbook: LLMLatencyDegraded

## What this means
p95 latency has exceeded 5 seconds for at least 10 minutes. Many users are experiencing slow responses.

## Impact
- Poor user experience
- Potential timeouts in downstream systems
- Increased infrastructure costs (requests held longer)

## Common causes
1. **Model provider slowdown** — Provider is degraded but not fully down
2. **Retrieval bottleneck** — Vector store is slow or overloaded
3. **Large responses** — Model generating unusually long outputs
4. **Cold start** — New pods warming up after scaling
```
## Investigation steps

### Step 1: Identify which step is slow
Check the step latency breakdown dashboard:
- Retrieval slow? → Vector store issue
- Generation slow? → Model provider issue
- All steps slow? → Network or infrastructure issue

### Step 2: Check step-level metrics
```promql
# Which step is contributing most to latency?
histogram_quantile(0.95, sum by (step, le) (rate(llm_step_latency_seconds_bucket[5m])))
```
### Step 3: Check model provider latency

- Look at generation step specifically
- Check provider status pages

### Step 4: Check for unusual queries

- Are there queries with very high token counts?
- Is one query type disproportionately slow?

## Mitigation

### If model provider slowdown:

- Wait and monitor (usually resolves within 30 minutes)
- Consider routing to secondary provider

### If retrieval bottleneck:

- Check vector store metrics (CPU, memory, query queue)
- Reduce retrieval count temporarily
- Scale vector store if possible

### If large responses:

- Check for prompt issues causing verbose output
- Verify max_tokens is set appropriately

## Escalation

- If not resolved in 30 minutes: Page senior engineer
- If SLO at risk: Escalate to leadership
## Complete Alert Rules File

Here's a complete example for an LLM system:

```yaml
# llm_alerts.yml
# Reference: Prometheus alerting rules documentation
# https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/

groups:
  - name: llm_critical
    rules:
      - alert: LLMHighErrorRate
        expr: |
          sum(rate(llm_requests_total{status="error"}[5m])) 
          / 
          sum(rate(llm_requests_total[5m])) 
          > 0.05
        for: 5m
        labels:
          severity: critical
          service: llm
        annotations:
          summary: "LLM error rate exceeded 5%"
          description: "Error rate is {{ $value | humanizePercentage }}."
          runbook_url: "https://wiki.example.com/runbooks/llm-high-error-rate"
          
      - alert: LLMServiceDown
        expr: sum(rate(llm_requests_total[5m])) == 0
        for: 2m
        labels:
          severity: critical
          service: llm
        annotations:
          summary: "LLM service appears down"
          description: "No requests processed in the last 2 minutes."
          runbook_url: "https://wiki.example.com/runbooks/llm-service-down"

  - name: llm_warnings
    rules:
      - alert: LLMLatencyDegraded
        expr: |
          histogram_quantile(0.95, sum by (le) (rate(llm_request_latency_seconds_bucket[5m])))
          > 5
        for: 10m
        labels:
          severity: warning
          service: llm
        annotations:
          summary: "p95 latency exceeded 5 seconds"
          description: "95th percentile latency is {{ $value | humanizeDuration }}."
          runbook_url: "https://wiki.example.com/runbooks/llm-latency-degraded"
          
      - alert: LLMCostSpike
        expr: sum(rate(llm_cost_usd_total[1h])) * 3600 > 10
        for: 30m
        labels:
          severity: warning
          service: llm
        annotations:
          summary: "LLM hourly cost exceeded $10"
          description: "Current hourly rate: ${{ $value | printf \"%.2f\" }}."
          runbook_url: "https://wiki.example.com/runbooks/llm-cost-spike"
          
      - alert: LLMLowRetrievalQuality
        expr: |
          histogram_quantile(0.5, sum by (le) (rate(llm_retrieval_top_score_bucket[15m])))
          < 0.5
        for: 30m
        labels:
          severity: warning
          service: llm
        annotations:
          summary: "Retrieval quality degraded"
          description: "Median top retrieval score is {{ $value | printf \"%.2f\" }}."
          runbook_url: "https://wiki.example.com/runbooks/llm-low-retrieval"

  - name: llm_info
    rules:
      - alert: LLMDailyBudgetApproaching
        expr: sum(llm_cost_usd_total) > 80
        labels:
          severity: info
          service: llm
        annotations:
          summary: "Daily LLM budget 80% consumed"
          description: "Spent ${{ $value | printf \"%.2f\" }} of $100 daily budget."
```

---

## Key Takeaways

1. **Alerts are not dashboards.** They're interrupts. Every alert should demand action.
    
2. **Three principles: Actionable, Meaningful, Timely.** If an alert fails any of these, fix or delete it.
    
3. **Severity levels route appropriately.** Critical pages you. Warning creates a ticket. Info logs for review.
    
4. **Start loose, tighten with data.** Better to miss early alerts than to create fatigue that causes you to miss real ones.
    
5. **Alert fatigue is the enemy.** Fewer, better alerts beat many noisy ones. Audit regularly.
    
6. **Every alert needs a runbook.** If you can't write what to do, you can't justify the alert.
    
7. **Use grouping and inhibition.** Reduce noise by batching related alerts and suppressing symptoms when the cause is already alerting.