# What You Would Have Learned from These Docs

## LangChain Text Splitters — Summary

LangChain's docs recommend starting with `RecursiveCharacterTextSplitter` for most use cases. It provides a solid balance between keeping context intact and managing chunk size. [Langchain](https://docs.langchain.com/oss/python/integrations/splitters)

**Core philosophy:** Text is naturally organized into hierarchical units such as paragraphs, sentences, and words. LangChain's splitters leverage this inherent structure to create splits that maintain natural language flow, maintain semantic coherence within splits, and adapt to varying levels of text granularity. [Langchain](https://docs.langchain.com/oss/python/integrations/splitters)

**Available splitters:**

|Splitter Type|Use Case|
|---|---|
|`CharacterTextSplitter`|Basic fixed-size splitting|
|`RecursiveCharacterTextSplitter`|Default choice — respects text hierarchy|
|`MarkdownTextSplitter`|Markdown-specific separators|
|`PythonCodeTextSplitter`|Python syntax-aware|
|`HTMLNodeParser`|HTML tag-based|
|`SentenceSplitter` (via NLTK/spaCy)|Natural language boundaries|

**Key parameters:**

- `chunk_size` — target size
- `chunk_overlap` — shared characters between chunks
- `separators` — hierarchy of split characters (default: `["\n\n", "\n", " ", ""]`)
- `length_function` — how to measure (characters vs tokens)

`RecursiveCharacterTextSplitter` has a `from_language()` class method that returns an instance configured for a specific programming language with appropriate separators. [LangChain](https://api.python.langchain.com/en/latest/character/langchain_text_splitters.character.RecursiveCharacterTextSplitter.html)

It also has `from_tiktoken_encoder()` and `from_huggingface_tokenizer()` methods for token-based length measurement instead of character-based. [LangChain](https://api.python.langchain.com/en/latest/character/langchain_text_splitters.character.RecursiveCharacterTextSplitter.html)

---

## LlamaIndex Node Parsers — Summary

LlamaIndex calls chunks "Nodes" and splitters "Node Parsers." The abstraction is richer — nodes inherit metadata from parent documents and maintain relationships.

**Three categories of parsers:**

### 1. File-Based Parsers

Parse by file type, respecting structure:

|Parser|Content Type|
|---|---|
|`SimpleFileNodeParser`|Auto-selects best parser per file type|
|`HTMLNodeParser`|HTML tags (configurable which tags)|
|`JSONNodeParser`|JSON structure|
|`MarkdownNodeParser`|Markdown structure|

### 2. Text Splitters

Similar to LangChain:

|Splitter|Description|
|---|---|
|`SentenceSplitter`|Respects sentence boundaries (their default)|
|`TokenTextSplitter`|Token-count based|
|`CodeSplitter`|Language-aware code splitting|
|`SemanticSplitterNodeParser`|Embedding-based semantic chunking|
|`SentenceWindowNodeParser`|Each sentence as a node, with surrounding context in metadata|

### 3. Relation-Based Parsers

**`HierarchicalNodeParser`** — This is the parent-child chunking we discussed:

python

```python
from llama_index.core.node_parser import HierarchicalNodeParser

node_parser = HierarchicalNodeParser.from_defaults(
    chunk_sizes=[2048, 512, 128]  # Hierarchy: large → medium → small
)
```

When combined with the `AutoMergingRetriever`, this enables us to automatically replace retrieved nodes with their parents when a majority of children are retrieved. This process provides the LLM with more complete context for response synthesis. [Llamaindex](https://developers.llamaindex.ai/python/framework/module_guides/loading/node_parsers/modules/)

**`SentenceWindowNodeParser`** — Each sentence becomes a node, but surrounding sentences are stored in metadata:

python

```python
from llama_index.core.node_parser import SentenceWindowNodeParser

node_parser = SentenceWindowNodeParser.from_defaults(
    window_size=3,  # sentences on either side
    window_metadata_key="window",
    original_text_metadata_key="original_sentence",
)
```

This is useful for precise embedding (embed just the sentence) while retaining context (the window) for LLM synthesis.

---

## What You Would Have Missed Without Reading the Docs

1. **`SentenceWindowNodeParser`** — A pattern I didn't mention. It's a middle ground: embed small (one sentence for precision), but retrieve big (the window for context). Different from parent-child because the window is metadata, not a separate stored chunk.
2. **`CodeSplitter`** — Language-aware splitting using tree-sitter. Not just splitting on `\ndef`, but actually parsing the AST.
3. **`from_language()` method** — LangChain's `RecursiveCharacterTextSplitter` has built-in language-specific separator presets you can invoke directly.
4. **Chaining parsers** — LlamaIndex docs mention combining file-based parsers (for structure) with text splitters (for size constraints) in sequence.
5. **`SemanticSplitterNodeParser`** in LlamaIndex — Their implementation of semantic chunking, with `buffer_size` and `breakpoint_percentile_threshold` parameters explicitly documented.

---

## Bottom Line

The docs would have given you:

- Exact class names and import paths
- Parameter names and defaults
- Built-in presets (language-specific, tokenizer-specific)
- Patterns like SentenceWindow that I synthesized imperfectly

What I gave you was conceptual understanding of _why_ these patterns exist. The docs give you _how_ to use the actual implementations. Both matter — but for implementation, always verify against current docs since these libraries evolve fast.