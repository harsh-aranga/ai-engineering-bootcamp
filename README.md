# AI Engineering Bootcamp

A structured, self-paced curriculum to go from "I can call OpenAI API" to building production-grade RAG systems and multi-agent architectures.

---

## What This Is

This is not a tutorial collection. It's a 10-week learning path designed to build **production-ready AI engineering skills**.

You'll learn:
- **RAG**: Chunking, vector stores, hybrid search, reranking, evaluation, debugging bad retrieval
- **Agents**: Function calling, LangGraph, state management, memory, human-in-the-loop, multi-agent patterns
- **Production**: Observability, LLMOps, hallucination detection, error handling, deployment strategies

Each week has:
- **Concepts** — What you need to understand
- **Mini builds** — Small projects to apply what you learned
- **Things to Ponder** — Questions to deepen understanding
- **Final builds** — Portfolio-worthy projects

---

## Who This Is For

**This is for you if:**
- You're an engineer with programming experience
- You want to build AI systems, not just understand them conceptually
- You can commit ~2 hours/day
- You want depth over breadth

**This is NOT for you if:**
- You're new to programming
- You want ML theory and math
- You're looking for quick tutorials
- You just want to copy-paste code

---

## What You'll Be Able to Do

After completing this bootcamp:

1. Build a production-grade RAG system with evaluation pipeline
2. Build a multi-step agent with tools, memory, and human-in-the-loop
3. Combine RAG + Agents into working applications
4. Explain architectural decisions in interviews
5. Debug common failure modes (bad retrieval, hallucination, runaway agents)
6. Have 2-3 portfolio projects on GitHub
7. System design an AI application on a whiteboard

---

## Curriculum Structure

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

### Week-by-Week Overview

| Week | Phase | Topics |
|------|-------|--------|
| 1 | Foundations | Tokenization, Embeddings, Prompt Engineering |
| 2 | Foundations | LLM API Patterns, Context Management, Structured Outputs |
| 3 | Parallel | **RAG**: Document Loading, Chunking · **Agents**: Function Calling, Tool Design |
| 4 | Parallel | **RAG**: Vector Stores, Basic Retrieval · **Agents**: LangGraph Fundamentals |
| 5 | Parallel | **RAG**: Hybrid Search, Reranking · **Agents**: State, Memory, Human-in-Loop |
| 6 | Parallel | **RAG**: Evaluation, Debugging · **Agents**: Multi-Agent Patterns, Eval |
| 7 | Combined | RAG + Agent Integration, Agentic RAG Patterns |
| 8 | Combined | Observability, LLMOps, Cost Tracking |
| 9 | Combined | Hallucination Detection, Error Handling, Production Hardening |
| 10 | Deployment | Docker, CI/CD, Model Migration & Versioning |
| 11+ | Portfolio | Apply everything to new domains |

---

## How to Use This Repo

### Option 1: Follow the Provided Notes

1. Start with `2_Curriculum/Week1/` to understand the week's goals
2. Work through `3_Notes/Week1/` notes in numbered order
3. Complete the mini builds and Things to Ponder
4. Move to the next week

### Option 2: Generate Your Own Notes

1. Use the weekly plans in `2_Curriculum/` as prompts
2. Feed them to an LLM (Claude, GPT, etc.) to generate personalized notes
3. Adapt depth and examples to your background

### Repo Structure

```
ai-engineering-bootcamp/
├── README.md                    # You are here
├── CURRICULUM.md                # Detailed curriculum guide
├── 1_Plan/                      # Weekly learning plans
│   ├── Project Instructions.md  # Overall guiding instructions for bootcamp 
├── 2_Curriculum/                # Weekly learning plans
│   ├── Week1/
│   ├── Week2/
│   └── ...
├── 3_Notes/                     # Notes and learnings
│   ├── Week1/
│   │   ├── Topic1-Tokenization/
│   │   ├── Topic2-Embeddings/
│   │   └── Topic3-PromptEngineering/
│   ├── Week3/
│   │   ├── AGENT/              # Agent track notes
│   │   └── RAG/                # RAG track notes
│   └── ...
└── images/                      # Referenced diagrams
```

**Note:** Weeks 1-2 are sequential. Weeks 3-6 split into parallel RAG and Agent tracks (hence the subfolders).

---

## Rules (Don't Skip These)

### 1. Do the Mini Builds

Reading is not learning. Building is learning. The mini builds are where concepts become skills. Skip them and you'll forget everything in a week.

### 2. Answer Things to Ponder

Each topic has reflection questions. Don't just read them — actually answer them. Write your answers down. This is where understanding deepens.

### 3. Depth Over Speed

Better to truly understand 3 topics than skim 10. If something isn't clicking, slow down. Re-read. Build something small. Ask questions.

### 4. Don't Rush to the Next Week

Complete the checklist at the end of each week before moving on. If you can't explain a concept or build the mini project, you're not ready.

---

## Prerequisites

- **Python**: Comfortable writing functions, classes, working with APIs
- **Command Line**: Basic navigation, running scripts
- **Git**: Clone, commit, push (basics are enough)
- **Time**: ~2 hours/day, 5-6 days/week
- **API Access**: OpenAI and/or Anthropic API keys (free tiers work for learning)

---

## Acknowledgments

This curriculum was built using Claude as a learning partner — for planning, generating notes, validating understanding, and iterating on explanations.

The structure, depth decisions, and content reflect real learning needs: what actually matters when you're building production AI systems.

---

## License

MIT License — use, modify, share freely.

If this helped you, a star or mention is appreciated.