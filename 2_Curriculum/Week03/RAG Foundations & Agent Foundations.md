# Week 3: Parallel Tracks Begin

> **Track:** Parallel (RAG + Agents) **Time:** 2 hours/day (1 hour RAG + 1 hour Agents) **Goal:** Understand RAG and Agents conceptually, then start building the foundational components of each.

---

## Overview

### RAG Track (1 hour/day)

|Days|Topic|Output|
|---|---|---|
|1-2|RAG Fundamentals|Conceptual understanding + simple end-to-end demo|
|3-4|Document Loading|Mini Challenge complete|
|5-6|Chunking Strategies|Mini Challenge complete|
|7|Mini Build|Document Processing Pipeline|

### Agent Track (1 hour/day)

|Days|Topic|Output|
|---|---|---|
|1-2|Agent Fundamentals|Conceptual understanding + simple tool-using example|
|3-4|Function Calling / Tool Use|Mini Challenge complete|
|5-6|Tool Design Principles|Mini Challenge complete|
|7|Mini Build|Simple Agent with Tools (no framework)|

---

# RAG TRACK

---

## Days 1-2 (RAG): RAG Fundamentals

### Why This Matters

RAG (Retrieval-Augmented Generation) is how you make LLMs useful for your data. Without RAG:

- LLMs only know their training data (stale, generic)
- Fine-tuning is expensive and doesn't handle frequently changing data
- You can't answer questions about private/proprietary documents

Understanding RAG end-to-end prevents you from blindly copying tutorials and failing when something breaks.

### What to Learn

**Core Concepts:**

- What RAG is: Retrieve relevant context → Augment the prompt → Generate response
- Why RAG over fine-tuning (cost, freshness, flexibility)
- The full pipeline: Load → Chunk → Embed → Store → Retrieve → Generate
- Vector databases: What they are, why they exist (conceptual, not hands-on yet)
- Failure modes: Bad chunking, bad retrieval, context stuffing, hallucination despite context

**The RAG Pipeline Visualized:**

```
[Documents] → [Chunking] → [Embedding] → [Vector Store]
                                              ↓
[User Query] → [Embed Query] → [Similarity Search] → [Top K Chunks]
                                                          ↓
                              [Augmented Prompt] ← [Query + Retrieved Chunks]
                                                          ↓
                                                    [LLM Response]
```

**Practical Skills:**

- Explain RAG to a non-technical person
- Identify when RAG is the right solution vs. alternatives
- Trace through the pipeline: given a query, what happens at each step?

### Resources

**Primary:**

- Pinecone RAG Guide: https://www.pinecone.io/learn/retrieval-augmented-generation/
- LangChain RAG Conceptual Guide: https://python.langchain.com/docs/concepts/rag/
- Original RAG Paper (skim abstract + intro): https://arxiv.org/abs/2005.11401

**Secondary:**

- Search: "RAG vs fine-tuning when to use"
- Search: "RAG failure modes" — understand what goes wrong

### Day 1 Tasks (1 hour)

**First 30 min — Learn:**

1. Read Pinecone RAG guide end-to-end (20 min)
2. Draw the RAG pipeline from memory — verify against the diagram above (10 min)

**Next 30 min — Explore:**

1. Find a simple RAG tutorial (LangChain or LlamaIndex quickstart)
2. Run it end-to-end with sample data — don't customize, just see it work
3. Trace through: Where are documents loaded? Where chunked? Where embedded? Where stored? Where retrieved?

### Day 2 Tasks (1 hour)

**First 30 min — Deepen:**

1. Read about RAG failure modes — what causes bad retrieval? (15 min)
2. Read about vector databases conceptually — what is similarity search? (15 min)

**Next 30 min — Experiment:**

1. Using your Day 1 demo, try a query that should work → verify it retrieves relevant chunks
2. Try a query that's slightly off-topic → see what it retrieves
3. Try a query using different words for same concept (synonym test) → does it still work?
4. Note: What surprised you? What failed?

### 5 Things to Ponder (RAG Fundamentals)

1. You have 10,000 documents. A user asks a question. RAG retrieves the top 5 chunks. But the answer was in document #8,742 which wasn't retrieved. The LLM confidently answers using the wrong chunks. How would you even know this happened?
    
2. RAG retrieves chunks, not full documents. You get 5 chunks from 5 different documents. The user's answer requires understanding that chunks 2 and 4 are from the same document and are related. How would the LLM know this?
    
3. Your company updates product documentation weekly. With fine-tuning, you'd need to retrain weekly. With RAG, you just update the vector store. But what happens to chunks from old/outdated documents? How do you handle versioning?
    
4. User asks: "What's our refund policy?" RAG retrieves chunks about refunds. But the policy changed last month, and both old and new policy chunks exist in the store. Which one gets retrieved? What determines this?
    
5. RAG adds retrieved chunks to the prompt, using up context window. You have a 4K context window. System prompt uses 500 tokens. Retrieved chunks use 2000 tokens. User message uses 200 tokens. Only 1300 tokens left for response. Is this a good tradeoff? How would you decide?
    

---

## Days 3-4 (RAG): Document Loading

### Why This Matters

Documents come in messy formats: PDFs with tables, markdown with code blocks, web pages with navigation, Word docs with headers. If you load them wrong:

- You lose structure (tables become gibberish)
- You include noise (navigation menus, footers, ads)
- You miss content (images with text, scanned PDFs)

Garbage in, garbage out. Bad loading = bad chunks = bad retrieval = wrong answers.

### What to Learn

**Core Concepts:**

- Document types: PDF, markdown, HTML, Word, plain text, CSV
- Structure preservation vs. plain text extraction
- Metadata extraction (title, source, date, page number)
- Handling special content: tables, code blocks, images
- Web scraping basics for HTML content

**Practical Skills:**

- Load PDFs and extract clean text
- Load markdown preserving structure
- Load web pages without navigation/boilerplate
- Attach useful metadata to loaded documents

### Resources

**Primary:**

- LlamaIndex Document Loaders: https://docs.llamaindex.ai/en/stable/module_guides/loading/
- LangChain Document Loaders: https://python.langchain.com/docs/concepts/document_loaders/
- `pypdf` library: https://pypdf.readthedocs.io/
- `unstructured` library: https://unstructured.io/

**Secondary:**

- Search: "extract tables from PDF python"
- Search: "web scraping beautiful soup tutorial"

### Day 3 Tasks (1 hour)

**First 30 min — Learn:**

1. Browse LlamaIndex or LangChain document loader docs — see what's available (15 min)
2. Understand the concept of `Document` object: content + metadata (10 min)
3. Read about `unstructured` library — what it handles (5 min)

**Next 30 min — Experiment:**

1. Install: `pip install pypdf unstructured langchain-community`
2. Load a simple PDF — print the extracted text
3. Load a markdown file — compare what you get vs. raw file
4. Load a web page (use requests + BeautifulSoup or a loader) — see how much noise you get

### Day 4 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Build a `load_document()` function:

```python
def load_document(file_path: str) -> list[dict]:
    """
    Loads a document and returns list of content chunks with metadata.
    
    Supports: .pdf, .md, .txt, .html
    
    Returns:
        List of {"content": str, "metadata": {"source": str, "page": int, ...}}
    """
    pass
```

**Success Criteria:**

- [ ] Correctly detects file type from extension
- [ ] Loads PDF and extracts text (test with a multi-page PDF)
- [ ] Loads markdown preserving basic structure
- [ ] Loads plain text
- [ ] Loads HTML and strips navigation/boilerplate (just main content)
- [ ] Attaches metadata: source filename, page number (for PDFs), file type
- [ ] Handles file not found gracefully (doesn't crash)
- [ ] Tested with at least 4 different files (one of each type)

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Document Loading)

1. You load a PDF of a financial report. It has tables showing quarterly revenue. After extraction, the table becomes: "Q1 Q2 Q3 Q4 100 200 150 180". How do you preserve table structure so the LLM understands Q1=100, Q2=200?
    
2. You're loading web pages. Page has: navigation menu, main article, sidebar ads, footer links, cookie banner. You only want the article. How would you reliably extract just the main content across different websites?
    
3. Your document is a scanned PDF (image-based, not text). `pypdf` extracts nothing. What's your fallback? What are the tradeoffs of OCR?
    
4. You load 1000 documents. 50 of them fail to load (corrupted, password-protected, weird encoding). Should you: (A) skip and continue, (B) error and stop, (C) something else? How do you track what failed and why?
    
5. Metadata: You store `source: "quarterly_report.pdf"`. Later, user asks a question, RAG retrieves a chunk, LLM answers. User asks "where did you get this information?" How does metadata enable this? What metadata would be most useful to capture?
    

---

## Days 5-6 (RAG): Chunking Strategies

### Why This Matters

Chunking is where most RAG systems silently fail. Wrong chunk size or strategy means:

- Too small: Chunks lack context, retrieval finds fragments
- Too large: Chunks contain multiple topics, retrieval brings irrelevant content
- Bad boundaries: Sentences cut mid-thought, code split from its explanation

Chunking is the #1 lever for improving RAG quality. Most tutorials use defaults. You won't.

### What to Learn

**Core Concepts:**

- Fixed-size chunking (by character/token count)
- Recursive chunking (split by paragraphs, then sentences, then words)
- Semantic chunking (split by meaning/topic shifts)
- Overlap: Why chunks should overlap, how much
- Chunk size tradeoffs: retrieval precision vs. context completeness

**Practical Skills:**

- Implement multiple chunking strategies
- Measure chunk quality (not just "it runs")
- Choose chunk size based on content type
- Handle special content (code, tables, lists)

### Resources

**Primary:**

- LangChain Text Splitters: https://python.langchain.com/docs/concepts/text_splitters/
- LlamaIndex Node Parsers: https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/
- Chunking strategies blog: Search "chunking strategies for RAG" — read 2-3 articles

**Secondary:**

- Search: "semantic chunking RAG"
- Search: "chunk size optimization RAG"

### Day 5 Tasks (1 hour)

**First 30 min — Learn:**

1. Read LangChain text splitters conceptual docs (15 min)
2. Understand the difference: CharacterTextSplitter vs. RecursiveCharacterTextSplitter (10 min)
3. Read about chunk overlap — why it exists, typical values (5 min)

**Next 30 min — Experiment:**

1. Take a document from Day 3-4
2. Chunk it with fixed size (500 chars, no overlap)
3. Chunk same doc with fixed size (500 chars, 50 char overlap)
4. Chunk with recursive splitter (same size)
5. Compare: Print first 5 chunks from each. Which looks more coherent?

### Day 6 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Build a `chunk_document()` function:

```python
def chunk_document(
    content: str,
    strategy: str = "recursive",  # "fixed", "recursive", "semantic"
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    metadata: dict = None
) -> list[dict]:
    """
    Chunks document content using specified strategy.
    
    Returns:
        List of {"content": str, "metadata": {..., "chunk_index": int}}
    """
    pass
```

**Success Criteria:**

- [ ] Implements at least 2 strategies: fixed and recursive
- [ ] Respects chunk_size (chunks should be approximately this size, not wildly over)
- [ ] Applies overlap correctly (adjacent chunks share overlap content)
- [ ] Preserves and extends metadata (adds chunk_index)
- [ ] Handles edge cases: content shorter than chunk_size, empty content
- [ ] Test: Same document, different strategies — print and compare chunk quality
- [ ] Bonus: Implement semantic chunking (split on paragraph/section boundaries)

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Chunking)

1. You chunk a legal document into 500-token chunks. One clause spans 800 tokens. Your chunker splits it into two chunks. Now the legal meaning is broken across chunks, and neither chunk is complete. How would you handle long, indivisible content?
    
2. Chunk size 200 vs. 1000 tokens. Smaller chunks = more precise retrieval but less context per chunk. Larger chunks = more context but might retrieve irrelevant content. How would you empirically determine the right size for YOUR data?
    
3. You have code documentation: text explaining code, then code blocks, then more text. Your chunker splits mid-code-block. How would you modify chunking to respect code boundaries?
    
4. Overlap of 50 tokens means adjacent chunks share 50 tokens. Why is this useful for retrieval? Can overlap be too large? What's the cost of overlap (hint: storage, embedding cost)?
    
5. Semantic chunking sounds ideal — split by meaning, not arbitrary size. But how do you detect "meaning boundaries"? What would a simple heuristic look like? What would a sophisticated approach look like?
    

---

## Day 7 (RAG): Mini Build — Document Processing Pipeline

### What to Build

A complete document processing pipeline that takes raw documents and outputs chunked, metadata-rich content ready for embedding.

### Specifications

```python
from doc_processor import DocumentProcessor

processor = DocumentProcessor(
    chunk_strategy="recursive",
    chunk_size=500,
    chunk_overlap=50
)

# Process single document
chunks = processor.process_file("report.pdf")
# Returns: [{"content": "...", "metadata": {"source": "report.pdf", "page": 1, "chunk_index": 0}}, ...]

# Process directory
all_chunks = processor.process_directory("./documents/", file_types=[".pdf", ".md", ".txt"])
# Returns: all chunks from all files

# Get stats
stats = processor.get_stats()
# Returns: {"files_processed": 10, "total_chunks": 342, "avg_chunk_size": 487, "failed_files": ["corrupt.pdf"]}
```

### Success Criteria

- [ ] Handles PDF, markdown, and plain text files
- [ ] Implements recursive chunking with configurable size and overlap
- [ ] Tracks comprehensive metadata: source, page (if applicable), chunk_index, file_type
- [ ] Processes entire directories, not just single files
- [ ] Tracks and reports failures (doesn't crash on bad files)
- [ ] Provides useful stats (files processed, chunks created, failures)
- [ ] Tested on at least 10 real documents of mixed types
- [ ] Clean code: could hand to another developer and they'd understand it

### Things to Ponder (Post-Build)

1. You built this to run locally. Now you need to process 100,000 documents. What breaks? How would you scale this (parallelization, cloud, queues)?
    
2. Your pipeline processes a document and creates 50 chunks. Tomorrow, the document is updated. You reprocess — get 52 chunks. How do you handle updates in a real system? Replace all chunks? Diff and update? What are the tradeoffs?
    
3. You process documents once and store chunks. But what if you want to try different chunking strategies later? Do you re-process everything? How would you design for experimentation?
    
4. Your pipeline currently outputs chunks. The next step is embedding. Would you embed in this pipeline or keep it separate? What are the design considerations?
    
5. You process a mix of documents: some technical, some conversational, some legal. Should chunking strategy be the same for all? How might you automatically detect content type and adjust?
    

---

# AGENT TRACK

---

## Days 1-2 (Agents): Agent Fundamentals

### Why This Matters

An agent is not a chatbot. A chatbot responds. An agent _acts_. Agents:

- Decide what to do (not just what to say)
- Use tools to interact with the world
- Handle multi-step tasks autonomously

If you don't understand the agent loop, you'll build fragile chains that break on unexpected inputs instead of robust agents that adapt.

### What to Learn

**Core Concepts:**

- What makes an agent different from a simple LLM call
- The Agent Loop: Observe → Think → Act → Observe (repeat)
- ReAct pattern: Reasoning + Acting in one framework
- Tools/Functions: How agents interact with the world
- When to use agents vs. simple prompts vs. chains

**The Agent Loop Visualized:**

```
[User Task] → [Agent]
                 ↓
         ┌─────────────────┐
         │  OBSERVE        │ ← Current state, tool results
         │       ↓         │
         │  THINK          │ ← Reason about what to do next
         │       ↓         │
         │  ACT            │ ← Call a tool OR respond to user
         │       ↓         │
         │  (Loop if needed)│
         └─────────────────┘
                 ↓
          [Final Response]
```

**Practical Skills:**

- Identify when a task needs an agent vs. simpler solution
- Trace through agent execution: what happens at each step?
- Understand tool calling at a conceptual level

### Resources

**Primary:**

- ReAct Paper (read abstract + examples): https://arxiv.org/abs/2210.03629
- LangChain Agent Concepts: https://python.langchain.com/docs/concepts/agents/
- OpenAI Function Calling Guide: https://platform.openai.com/docs/guides/function-calling

**Secondary:**

- Search: "ReAct prompting explained"
- Search: "LLM agents tutorial" — find a simple walkthrough

### Day 1 Tasks (1 hour)

**First 30 min — Learn:**

1. Read ReAct paper abstract + look at Figure 1 examples (15 min)
2. Read LangChain agent concepts page (15 min)

**Next 30 min — Explore:**

1. Think of 3 tasks that NEED an agent (can't be solved with one LLM call)
2. Think of 3 tasks that DON'T need an agent (simple prompt works)
3. For one agent-worthy task, sketch the loop: What would the agent observe? Think? Do? When would it stop?

### Day 2 Tasks (1 hour)

**First 30 min — Deepen:**

1. Read OpenAI function calling guide (20 min)
2. Understand: How does the LLM know what tools are available? How does it "call" them? (10 min)

**Next 30 min — Experiment:**

1. Using OpenAI playground or API, define a simple function (e.g., `get_weather(city)`)
2. Ask the model a question that requires the function
3. See how the model responds — it doesn't call the function, it tells you it WANTS to call it
4. Understand: You (the code) actually execute the function and feed results back

### 5 Things to Ponder (Agent Fundamentals)

1. You build an agent with a "send_email" tool. User says "email my boss that I quit." Agent has the capability. Should it just do it? What guardrails should exist? Who's responsible if it sends something wrong?
    
2. Agent is trying to book a flight. It searches, finds options, but needs user's credit card to complete. How does the agent handle "I need information I don't have"? What's the graceful way to pause and ask?
    
3. Simple task: "What's 2+2?" Does this need an agent with a calculator tool, or is a direct LLM response fine? At what complexity threshold does a tool become necessary?
    
4. Agent has 10 tools available. For a given task, only 2 are relevant. How does the agent know which tools to use? What happens if it picks the wrong tool? How do you debug this?
    
5. Agent is in a loop: Think → Act → Observe → Think → Act → Observe... What stops it? What if it gets stuck in an infinite loop trying the same thing? What's your termination strategy?
    

---

## Days 3-4 (Agents): Function Calling / Tool Use

### Why This Matters

Function calling is how agents interact with the world. Without it, agents can only talk. With it, they can:

- Search the web
- Query databases
- Call APIs
- Execute code
- Literally anything you can write a function for

This is the bridge between "AI that chats" and "AI that does."

### What to Learn

**Core Concepts:**

- Function schemas: How to describe a function to the LLM
- Parameters: Types, descriptions, required vs. optional
- The execution flow: LLM requests call → You execute → Return result → LLM continues
- Parallel function calls: Multiple tools in one response
- Handling function errors: What if the tool fails?

**Practical Skills:**

- Define clear function schemas
- Parse function call responses from the LLM
- Execute functions and return results in correct format
- Handle the full loop: user message → function call → result → final response

### Resources

**Primary:**

- OpenAI Function Calling: https://platform.openai.com/docs/guides/function-calling
- OpenAI Cookbook - Function Calling: https://cookbook.openai.com/examples/how_to_call_functions_with_chat_models
- Anthropic Tool Use: https://docs.anthropic.com/en/docs/build-with-claude/tool-use

**Secondary:**

- Search: "openai function calling python example"
- Your Week 2 structured outputs code — function calling builds on this

### Day 3 Tasks (1 hour)

**First 30 min — Learn:**

1. Read OpenAI function calling guide thoroughly (20 min)
2. Study the function schema format — understand each field (10 min)

**Next 30 min — Experiment:**

1. Define a simple function schema: `get_current_weather(location: str, unit: str = "celsius")`
2. Make an API call with this function available
3. Ask: "What's the weather in Tokyo?"
4. Parse the response — extract the function name and arguments
5. Simulate calling the function, return a fake result
6. Send the result back to the model, get final response

### Day 4 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Build a `tool_calling_loop()` function:

```python
def tool_calling_loop(
    user_message: str,
    tools: list[dict],  # List of function schemas
    tool_functions: dict[str, callable],  # {"function_name": actual_function}
    max_iterations: int = 5
) -> str:
    """
    Executes the full agent loop:
    1. Send user message with available tools
    2. If model wants to call a tool, execute it
    3. Send result back to model
    4. Repeat until model gives final response (no more tool calls)
    
    Returns: Final response text
    """
    pass
```

Test with these tools:

```python
def add(a: int, b: int) -> int:
    return a + b

def multiply(a: int, b: int) -> int:
    return a * b

def get_time() -> str:
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")
```

**Success Criteria:**

- [ ] Correctly parses function call requests from model response
- [ ] Executes the right function with correct arguments
- [ ] Sends tool results back in correct format
- [ ] Handles multi-step: "What's 2+3, then multiply by 4?" (requires 2 tool calls)
- [ ] Stops when model gives final response (no tool call)
- [ ] Respects max_iterations (doesn't loop forever)
- [ ] Handles tool execution errors gracefully (tool throws exception)
- [ ] Tested with at least 3 different queries requiring different tools

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Function Calling)

1. You define a tool `search_database(query: str)`. The model calls it with `query="SELECT * FROM users"`. That's SQL injection potential. How do you make tools safe from malicious or malformed inputs?
    
2. Model can request multiple parallel function calls in one response. When is this useful? When might parallel calls cause problems (think: dependencies between calls)?
    
3. Your tool `get_stock_price(symbol)` makes an API call that takes 5 seconds. Model calls it 3 times for 3 different stocks. Do you execute sequentially (15 seconds) or in parallel (5 seconds)? What's the tradeoff?
    
4. Model calls `send_message(to="friend", text="hey")`. Your function sends it. Model then says "Message sent!" But what if the function silently failed? How do you ensure the model (and user) know the true outcome?
    
5. You have 20 tools available. Model only sees tool schemas, not implementations. How detailed should descriptions be? What happens if descriptions are vague? What happens if they're too verbose (token cost)?
    

---

## Days 5-6 (Agents): Tool Design Principles

### Why This Matters

A well-designed tool makes agents smart. A poorly-designed tool makes agents stupid. The difference:

- Clear descriptions → Model knows when to use it
- Obvious parameters → Model passes correct values
- Predictable output → Model understands results
- Good error handling → Model recovers from failures

You'll build many tools. Learn to build them well from the start.

### What to Learn

**Core Concepts:**

- Tool naming: Verbs, clarity, specificity
- Parameter design: Types, constraints, required vs. optional
- Description writing: What the tool does, when to use it, what it returns
- Return value design: Structured, predictable, actionable
- Error handling: How tools should report failures

**Practical Skills:**

- Write tool descriptions that prevent misuse
- Design parameters that are hard to get wrong
- Build tools that report success/failure clearly
- Test tools with edge cases before giving to agents

### Resources

**Primary:**

- OpenAI Function Calling Best Practices: https://platform.openai.com/docs/guides/function-calling#best-practices
- Anthropic Tool Use Best Practices: https://docs.anthropic.com/en/docs/build-with-claude/tool-use#best-practices

**Secondary:**

- Search: "LLM tool design best practices"
- Look at LangChain built-in tools for inspiration: https://python.langchain.com/docs/integrations/tools/

### Day 5 Tasks (1 hour)

**First 30 min — Learn:**

1. Read OpenAI function calling best practices section (15 min)
2. Read Anthropic tool use best practices (15 min)
3. Note: What patterns appear in both? What do both emphasize?

**Next 30 min — Analyze:**

1. Look at 5 LangChain built-in tools (browse docs, see their schemas)
2. For each: What makes the description good or bad? Are parameters clear?
3. Find one tool you think is well-designed — why?
4. Find one you think could be improved — how?

### Day 6 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Design and implement 4 tools for a "Personal Assistant" agent:

1. **Calendar tool**: Check schedule, add events
2. **Web search tool**: Search the web (simulate with a mock)
3. **Note-taking tool**: Save and retrieve notes
4. **Calculator tool**: Perform calculations

For each tool, provide:

- Well-designed function schema (name, description, parameters)
- Implementation (can be simple/mocked)
- At least 2 test cases showing correct usage
- At least 1 test case showing how the model might misuse it and how your design prevents it

**Success Criteria:**

- [ ] All 4 tools have clear, specific names (verbs preferred)
- [ ] Descriptions explain WHAT it does + WHEN to use it + WHAT it returns
- [ ] Parameters have types, descriptions, and constraints where appropriate
- [ ] Return values are structured (not just strings) with success/error indicators
- [ ] Each tool handles at least one error case (e.g., calendar event in the past, note not found)
- [ ] Tools are testable independently of the agent
- [ ] Documentation: Someone else could use these tools from the schema alone

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Tool Design)

1. Tool: `delete_file(filename)`. Model hallucinates a filename that doesn't exist. Do you: (A) return "file not found" error, (B) silently succeed, (C) something else? What's the impact of each choice on the agent's behavior?
    
2. You're designing `search_web(query)`. Should it return: (A) raw HTML, (B) extracted text, (C) structured data {title, snippet, url}, (D) summarized results? What are the tradeoffs for each for an LLM consumer?
    
3. Tool: `send_email(to, subject, body)`. Should you add a `confirm: bool` parameter requiring explicit confirmation? Or is that the agent orchestration's job? Where does "safety" live — in the tool or the agent?
    
4. Your `calculator(expression)` takes a string like "2 + 3 * 4". This is flexible but dangerous (eval injection). Alternative: `calculator(operation, a, b)` — safer but limited. How do you balance flexibility and safety?
    
5. You have 50 tools. Model can only see ~10 before context gets cluttered. How do you decide which tools to include for a given conversation? Who decides — you statically, or dynamically based on user's first message?
    

---

## Day 7 (Agents): Mini Build — Simple Agent with Tools (No Framework)

### What to Build

A working agent that can handle multi-step tasks using tools you designed — built from scratch, no LangChain/LangGraph, just raw API calls and your code.

### Specifications

```python
from simple_agent import Agent

# Define tools
tools = [
    {
        "name": "calculate",
        "description": "Performs mathematical calculations",
        "parameters": {...},
        "function": calculate_fn
    },
    {
        "name": "search_notes",
        "description": "Searches saved notes",
        "parameters": {...},
        "function": search_notes_fn
    },
    {
        "name": "save_note",
        "description": "Saves a new note",
        "parameters": {...},
        "function": save_note_fn
    },
    {
        "name": "get_time",
        "description": "Gets current date and time",
        "parameters": {...},
        "function": get_time_fn
    }
]

agent = Agent(
    model="gpt-4o-mini",
    tools=tools,
    system_prompt="You are a helpful assistant with access to tools."
)

# Single task
response = agent.run("What's 15% of 230?")
# Agent uses calculator, returns answer

# Multi-step task  
response = agent.run("Save a note that I need to buy milk, then tell me the time")
# Agent: calls save_note, then calls get_time, then responds

# Conversation
response = agent.run("What notes do I have?")
# Agent: calls search_notes, returns results
```

### Success Criteria

- [ ] Agent can use tools to answer questions (tool selection works)
- [ ] Agent handles multi-step tasks (calls multiple tools in sequence)
- [ ] Agent knows when NOT to use tools (simple questions answered directly)
- [ ] Implements the full loop: LLM → tool call → execute → result → LLM → (repeat or respond)
- [ ] Max iterations limit prevents infinite loops
- [ ] Tool errors are handled gracefully (agent acknowledges failure, doesn't crash)
- [ ] Conversation history maintained (agent remembers previous exchanges)
- [ ] At least 4 working tools with good design (from Day 6)
- [ ] Tested with at least 5 different queries covering: single tool, multi tool, no tool needed, tool error

### Things to Ponder (Post-Build)

1. You built this without a framework. Now look at LangChain agents. What does LangChain give you that you had to build yourself? What's the value of the framework vs. custom code?
    
2. Your agent uses simple message history for memory. After 20 exchanges, context fills up. How would you extend this agent to handle long conversations? (Preview: this is what you'll solve in Week 5)
    
3. Your agent decides which tool to use based on the model's judgment. What if it consistently picks the wrong tool? How would you debug this? How would you improve tool selection?
    
4. You built tools as Python functions. What if a tool needs to call an external API that takes 30 seconds? How does this affect user experience? How would you handle long-running tools?
    
5. Your agent works for one user. What if you wanted to deploy it for 1000 concurrent users? What parts of your code would break? What would need to change? (Preview: Week 7+ production concerns)
    

---

# WEEK 3 CHECKLIST

## RAG Track Completion Criteria

- [ ] **RAG Fundamentals:** Can explain RAG pipeline end-to-end, know when to use RAG vs. alternatives
- [ ] **Document Loading:** Can load PDFs, markdown, text, HTML; extract clean content with metadata
- [ ] **Chunking:** Can implement multiple strategies, understand tradeoffs, choose appropriate chunk size
- [ ] **Mini Build:** Working document processing pipeline on GitHub

## Agent Track Completion Criteria

- [ ] **Agent Fundamentals:** Can explain agent loop, ReAct pattern, when agents are needed
- [ ] **Function Calling:** Can define schemas, parse calls, execute tools, return results in the loop
- [ ] **Tool Design:** Can design tools with clear descriptions, safe parameters, good error handling
- [ ] **Mini Build:** Working agent with 4+ tools on GitHub (no framework)

## What's Next

**Week 4:**

- **RAG Track:** Vector stores, indexing, basic retrieval — you'll actually store and retrieve your chunks
- **Agent Track:** LangGraph fundamentals — graduate from raw code to structured framework

---

# NOTES SECTION

## RAG Track Notes

### Days 1-2 Notes (RAG Fundamentals)

### Days 3-4 Notes (Document Loading)

### Days 5-6 Notes (Chunking)

### Day 7 Notes (RAG Mini Build)

---

## Agent Track Notes

### Days 1-2 Notes (Agent Fundamentals)

### Days 3-4 Notes (Function Calling)

### Days 5-6 Notes (Tool Design)

### Day 7 Notes (Agent Mini Build)