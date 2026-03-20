# AI Engineering Bootcamp — Curriculum Guide

## What This Is

A structured self-learning curriculum to become a production-ready AI Engineer. The goal is job-market readiness and the ability to deliver AI work that goes beyond "I can call the OpenAI API."

---

## Learning Structure

### Overall Flow

```
FOUNDATIONS (Week 1-2) — Sequential
       ↓
RAG TRACK ←→ AGENT TRACK (Week 3-6) — Parallel, 1 hour each daily
       ↓
COMBINED PHASE (Week 7-9) — RAG + Agents + Ops + Evaluation
       ↓
DEPLOYMENT (Week 10) — Optional Reference
       ↓
PORTFOLIO PROJECTS (Week 11+)
```

### Time Commitment

- 2 hours/day
- During parallel phase: 1 hour RAG + 1 hour Agents (same day)

---

## Topic Sequence (Curriculum)

### Phase 1: Foundations (Sequential)

**Week 1:**

- Tokenization
- Embeddings
- Prompt Engineering Fundamentals
- Mini Build: Prompt Analyzer CLI

**Week 2:**

- LLM API Patterns (chat completion, streaming, error handling)
- Context Window Management
- Cost Optimization Basics
- Mini Build: Robust LLM Client Wrapper

---

### Phase 2: Parallel Tracks

#### RAG Track (1 hour/day)

**Week 3 RAG:**

- Document Loading (PDFs, markdown, web, structured data)
- Chunking Strategies (fixed, recursive, semantic)
- Mini Build: Document Processing Pipeline

**Week 4 RAG:**

- Vector Stores (ChromaDB, then Qdrant or Pinecone)
- Indexing Strategies
- Basic Retrieval
- Mini Build: Working RAG v1 (basic Q&A over docs)

**Week 5 RAG:**

- Hybrid Search (BM25 + dense vectors)
- Reranking (cross-encoders)
- Query Transformation (HyDE, expansion)
- Mini Build: RAG v2 (improved retrieval)

**Week 6 RAG:**

- RAG Evaluation (retrieval metrics, answer quality)
- Debugging Bad Retrieval
- Final Build: Production RAG System with Eval Pipeline

#### Agent Track (1 hour/day)

**Week 3 Agents:**

- Function Calling / Tool Use (raw, no framework)
- Tool Design Principles
- Mini Build: Simple Tool-Using Script (no framework)

**Week 4 Agents:**

- LangGraph Fundamentals (nodes, edges, state)
- Basic Agent Loop
- Mini Build: Single Agent with 3+ Tools in LangGraph

**Week 5 Agents:**

- State Management
- Memory Systems (conversation, summary, vector)
- Human-in-the-Loop Patterns
- Mini Build: Agent with Memory + Checkpointing

**Week 6 Agents:**

- Multi-Agent Patterns (orchestrator, supervisor, peer)
- Agent Evaluation
- Final Build: Multi-Agent System with Eval

---

### Phase 3: Combined (Sequential)

**Week 7:**

- RAG + Agent Integration (agent decides when to retrieve)
- Agentic RAG Patterns (iterative retrieval, self-correction)
- Mini Build: Research Assistant v1

**Week 8:**

- Observability & Tracing (LangSmith or LangFuse)
- LLMOps Basics (logging, monitoring, alerting)
- Cost Tracking in Production
- Mini Build: Add Full Observability to Research Assistant

**Week 9:**

- Hallucination Detection & Mitigation
- Error Handling & Fallbacks
- Production Hardening
- Final Build: Production-Ready Research Assistant

---

### Phase 4: Deployment (Optional Reference)

**Week 10:**

- Docker + Cloud Deployment
- CI/CD + Deployment Strategies
- Model Migration & Versioning
- Design Documents (no hands-on required)

---

### Phase 5: Portfolio & Job Prep

**Week 11+:**

- Portfolio Project 1 (new domain, apply all patterns)
- Portfolio Project 2 (speed run, prove transferability)
- System Design Interview Prep
- Common Failure Modes & Debugging Practice

---

## Depth Philosophy

**Include a topic if:** Skipping it would cause mistakes in production or interviews.

**Skip a topic if:** It's "nice to know" but not essential for building/debugging.

| Topic | Include? | Reason |
|-------|----------|--------|
| Tokenization mechanics | ✅ Yes | Causes cost/limit mistakes |
| Transformer attention math | ❌ No | Not needed to build/debug |
| Embeddings conceptually | ✅ Yes | Can't debug RAG without it |
| Fine-tuning embeddings | ✅ Yes | Real performance gains |
| Training LLMs from scratch | ❌ No | Not the goal |
| Prompt engineering | ✅ Yes | Primary interface with models |
| LangGraph internals | ✅ Yes | Need to debug agent issues |
| Every agent framework | ❌ No | Learn one deeply (LangGraph) |
| Evaluation methods | ✅ Yes | Can't improve without measuring |
| MLOps/LLMOps basics | ✅ Yes | Production requirement |

---

## Success Criteria (End State)

After completing this bootcamp, you should be able to:

1. Build a production-grade RAG system with evaluation pipeline
2. Build a multi-step agent with tools, memory, and human-in-loop
3. Combine RAG + Agents into a working application
4. Explain architectural decisions in interviews
5. Debug common failure modes (bad retrieval, hallucination, runaway agents)
6. Have 2-3 portfolio projects on GitHub
7. System design an AI application on whiteboard

---

**Note:** Week 1-2 are sequential foundations. Week 3+ splits into parallel RAG and Agent tracks, hence the subfolder structure change.