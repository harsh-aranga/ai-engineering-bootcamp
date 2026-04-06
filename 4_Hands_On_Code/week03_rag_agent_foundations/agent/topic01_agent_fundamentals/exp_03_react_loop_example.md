### For one agent-worthy task, sketch the loop: What would the agent observe? Think? Do? When would it stop?

---

### K8s Pod Health Agent — ReAct Loop

```
┌─────────────────────────────────────────────────────────────┐
│                        TRIGGER                              │
│              (Scheduled / Alert-based)                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  OBSERVE: Get cluster pod status                            │
│  Tool: kubectl get pods --all-namespaces                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  THINK: Are any pods unhealthy?                             │
│  - CrashLoopBackOff, OOMKilled, Pending, ImagePullBackOff   │
│  - If all healthy → STOP (exit loop)                        │
│  - If unhealthy pods found → continue                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  OBSERVE: Get details of affected pod(s)                    │
│  Tools: kubectl describe pod X, kubectl logs X              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  THINK: What's the root cause? What's the fix?              │
│  - OOM → increase memory limits                             │
│  - ImagePullBackOff → check image name, registry creds      │
│  - CrashLoopBackOff → check logs for app error              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  ACT: Apply remediation                                     │
│  Tools: kubectl delete pod X, kubectl apply -f patch.yaml   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  OBSERVE: Wait, then re-check pod status                    │
│  Tool: sleep 30 && kubectl get pod X                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  THINK: Did the fix work?                                   │
│  - Pod healthy → STOP (success)                             │
│  - Still failing + retries < threshold → loop back          │
│  - Retries exhausted → STOP (escalate to human)             │
└─────────────────────────────────────────────────────────────┘
```

---

## Termination Conditions (Critical for Agent Design)


| Condition | Action |
|-----------|--------|
| All pods healthy | Exit loop — success |
| Fix applied, still failing, retries remain | Loop back to OBSERVE |
| Retry threshold exceeded | Exit loop — escalate to human |
| Action would be destructive (delete PVC, scale to zero) | Pause — require human approval |

That last one is something you'd add in production. Agents need **guardrails** — not every action should be autonomous.

---

## What Makes This an Agent (Interview Summary)

1. **Unpredictable step count** — Could resolve in 1 cycle or 5, depending on what's broken
2. **Observation-dependent branching** — Next action depends on what logs/status reveal
3. **Closed-loop feedback** — Verifies fix worked before stopping
4. **Graceful degradation** — Knows when to stop and escalate

---