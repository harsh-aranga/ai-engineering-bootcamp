# Day 5: LangChain Tool Schema Analysis

## What I Learned

### LangChain doesn't have "built-in" tools

The term is misleading. Tools are scattered across:
- `langchain_core.tools` — just base classes, no actual tools
- `langchain_community.tools` — community-maintained (DuckDuckGo, Wikipedia, Arxiv)
- `langchain_experimental.tools` — risky stuff (PythonREPL)
- Partner packages (`langchain-tavily`, etc.) — separate pip installs

Nothing is truly batteries-included. LangChain chose extensibility over built-in.

---

## 5 Tools Analyzed

| Tool | Package | Input | Output |
|------|---------|-------|--------|
| TavilySearch | `langchain-tavily` | Rich params (query, max_results, topic, time_range, domains, search_depth) | Structured JSON (title, URL, snippet, images) |
| DuckDuckGoSearchRun | `langchain_community` | Single string query | Unstructured string blob |
| WikipediaQueryRun | `langchain_community` | Single string query | Unstructured string blob |
| ArxivQueryRun | `langchain_community` | Single string query | Unstructured string blob |
| PythonREPLTool | `langchain_experimental` | Python code as string | Execution output string |

---

## What Makes Tavily Well-Designed

- Rich parameter set with sensible defaults
- Structured JSON return (not a string blob)
- Runtime vs init-time param separation (prevents context window issues)
- Clear field descriptions

Profit motive drove quality — they wanted adoption. But the patterns are transferable.

---

## What's Wrong With Community Tools

**ArxivQueryRun missing:**
- max_results, sort_by (relevance/date), category_filter, date_range, pagination

**WikipediaQueryRun missing:**
- language, max_results, summary_only flag
- WikipediaAPIWrapper HAS top_k_results and doc_content_chars_max but they're not exposed in schema — LLM can't set them dynamically

**DuckDuckGoSearchRun missing:**
- region, time_range, safe_search

**Common flaw:** Single string in, string blob out. No structured returns. Model has to parse text.