# Document Loading: Conceptual Notes

## What Document Loading Actually Is

Document loading is the process of extracting usable text and metadata from raw files so they can be processed by downstream components (chunking, embedding, retrieval). It's the **first transformation** in your RAG pipeline.

Think of it as translation: you're converting from "file format the computer stores" to "text + context the LLM can reason about."

```
Raw File (PDF, HTML, DOCX, MD)
           ↓
    Document Loader
           ↓
Structured Output: { content: str, metadata: dict }
```

---

## Why It's Harder Than It Looks

### The Naive Assumption

"Just read the file and get text."

### The Reality

**PDFs are not text files.** They're page description languages—instructions for where to draw characters on a page. There's no guarantee characters are stored in reading order. Tables might be stored column-by-column or cell-by-cell depending on how the PDF was generated.

**HTML is noisy.** A webpage might be 80% navigation, ads, footers, and JavaScript—20% actual content. The content you want is buried.

**Scanned documents are images.** If someone scanned a paper document, you have pixels, not characters. Extraction requires OCR (Optical Character Recognition), which introduces errors.

**Structure gets lost.** A table in a Word doc is semantically meaningful (row/column relationships). After naive extraction, it might become a jumbled sequence of words with no indication of what belongs together.

---

## The Document Object Model

Most frameworks (LangChain, LlamaIndex) standardize on a simple structure:

```python
# Conceptual representation
document = {
    "content": "The actual extracted text...",
    "metadata": {
        "source": "quarterly_report.pdf",
        "page": 3,
        "file_type": "pdf",
        "title": "Q3 2024 Financial Results",
        "created_date": "2024-10-15",
        # ... any other useful context
    }
}
```

**Content** is what gets embedded and retrieved.

**Metadata** is what gets stored alongside and used for:

- Filtering (only search documents from 2024)
- Attribution (tell user where answer came from)
- Debugging (why did this chunk get retrieved?)

---

## Loading Different File Types

### Plain Text (.txt)

**Complexity: Trivial**

Just read the file. The only consideration is encoding (UTF-8, Latin-1, etc.).

```python
with open("file.txt", "r", encoding="utf-8") as f:
    content = f.read()
```

### Markdown (.md)

**Complexity: Low**

Markdown is already text, but has structure (headers, code blocks, lists). You can either:

- Load as plain text (lose explicit structure markers)
- Parse the structure (know that "## Section" is a heading)

For most RAG use cases, loading as plain text works fine—the structural markers themselves provide context to the LLM.

### HTML

**Complexity: Medium**

Raw HTML contains:

- Actual content (article text)
- Navigation (menus, breadcrumbs)
- Boilerplate (headers, footers, sidebars)
- Scripts and styles (JavaScript, CSS)
- Ads and tracking

**Extraction approaches:**

1. **Strip all tags** – Gives you text but includes navigation, footers, etc.
2. **Target specific elements** – Look for `<article>`, `<main>`, or content-specific classes
3. **Readability algorithms** – Libraries like `readability-lxml` or `trafilatura` use heuristics to identify "main content"

### PDF

**Complexity: High**

PDFs vary wildly:

|Type|What You Get|Challenge|
|---|---|---|
|Native PDF (text-based)|Characters with positions|Reading order, table structure|
|Scanned PDF (image-based)|Pixels|Requires OCR|
|Hybrid PDF|Mix of both|Need to detect and handle each|

**Common libraries:**

- `pypdf` – Basic text extraction, fast, lightweight
- `pdfplumber` – Better with tables, extracts positional info
- `unstructured` – Higher-level, handles many formats including OCR
- `PyMuPDF (fitz)` – Fast, good balance of features

### Word Documents (.docx)

**Complexity: Medium**

DOCX files are actually ZIP archives containing XML. Libraries like `python-docx` parse this structure.

Tables, headers, footnotes are preserved in the XML structure—you can extract them with their relationships intact if you need to.

---

## The Metadata Question

What metadata should you capture? Depends on your use case, but commonly useful:

|Metadata|Why It Matters|
|---|---|
|`source` (filename/URL)|Attribution, debugging|
|`page` (for PDFs)|Point user to exact location|
|`file_type`|May affect how you chunk later|
|`title`|Display to users|
|`created_date` / `modified_date`|Relevance ranking, filtering|
|`author`|Trust/authority signals|
|`section_header`|Context for chunks|

**Key principle:** Capture metadata at load time that you'll need at retrieval time. It's expensive to go back and re-extract later.

---

## What Can Go Wrong

### 1. Silent Failures

File loads but extraction is garbage. PDF text comes out as "Q1 Q2 Q3 Q4 100 200 150 180" instead of a readable table. You don't notice until retrieval quality tanks.

**Mitigation:** Sample and visually inspect extracted content during development.

### 2. Missing Content

Scanned PDFs return empty strings. Images with text are ignored. Password-protected files silently fail.

**Mitigation:** Track extraction metrics (character count, page count) and flag anomalies.

### 3. Too Much Content

HTML page loads with navigation, cookie banners, related articles. Your chunks are now polluted with irrelevant content.

**Mitigation:** Use content extraction libraries, not raw HTML parsing.

### 4. Encoding Issues

Non-UTF-8 files, special characters, different line endings. Can cause crashes or mojibake (garbled text like "donâ€™t").

**Mitigation:** Detect encoding, normalize to UTF-8, handle errors gracefully.

---

## Framework vs. Raw Approach

**Using a framework (LangChain/LlamaIndex):**

```python
from langchain_community.document_loaders import PyPDFLoader

loader = PyPDFLoader("report.pdf")
documents = loader.load()  # Returns list of Document objects
```

**Going raw:**

```python
from pypdf import PdfReader

reader = PdfReader("report.pdf")
for page_num, page in enumerate(reader.pages):
    text = page.extract_text()
    # Build your own document structure
```

**Tradeoff:** Frameworks give you consistency and less code. Raw gives you control and understanding. For learning, start raw, then use frameworks.

---

## Mental Model Summary

Document loading is **lossy translation**. You're converting from a rich format (layout, fonts, images, tables) to plain text. Every conversion loses something.

Your job is to:

1. **Minimize loss** of semantically important information
2. **Maximize removal** of noise and irrelevant content
3. **Capture metadata** that will be useful downstream
4. **Handle failures** gracefully and visibly

The quality of everything downstream—chunking, embedding, retrieval, generation—depends on what you extract here. There's no recovering from bad loading.