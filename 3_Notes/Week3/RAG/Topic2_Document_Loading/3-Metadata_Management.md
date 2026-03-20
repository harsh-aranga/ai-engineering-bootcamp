# Metadata Extraction in Document Loading

## What Metadata Is

Metadata is **data about your data**. It's everything _except_ the content itself that provides context about where the content came from, when it was created, who created it, and how it's structured.

```python
document = {
    "content": "Revenue increased 15% year-over-year...",  # What the LLM reasons about
    "metadata": {                                          # Context about the content
        "source": "quarterly_report_q3_2024.pdf",
        "page": 7,
        "file_type": "pdf",
        "title": "Q3 2024 Financial Results",
        "author": "Finance Team",
        "created_date": "2024-10-15",
        "section": "Financial Highlights"
    }
}
```

The content gets embedded and retrieved. The metadata travels alongside it, enabling filtering, attribution, and debugging.

---

## Why Metadata Matters for RAG

### 1. Filtering at Query Time

User asks: "What were our Q3 2024 results?"

Without metadata, you search all documents. With metadata:

```python
# Pseudo-code for filtered retrieval
results = vector_store.search(
    query="Q3 2024 results",
    filter={"quarter": "Q3", "year": 2024}
)
```

You narrow the search space _before_ semantic similarity runs. Faster, more precise.

### 2. Attribution in Responses

User asks a question. RAG retrieves a chunk. LLM answers. User asks: "Where did you get this?"

Without metadata: "I found this in your documents." (Useless)

With metadata: "This information is from page 7 of 'Q3 2024 Financial Results', dated October 15, 2024." (Verifiable)

### 3. Debugging Bad Retrieval

Your RAG system gives a wrong answer. You need to understand why.

Without metadata: You have a chunk of text. Where did it come from? Which document? Which page? No idea.

With metadata: You can trace back to the exact source, see what else was on that page, understand if the loader mangled something.

### 4. Relevance and Recency

Two documents discuss the same topic. One is from 2020, one from 2024. For many queries, the 2024 document is more relevant.

Without date metadata: You can't distinguish them.

With date metadata: You can boost recent documents or filter out stale ones.

---

## Types of Metadata

### Intrinsic Metadata (Embedded in the File)

This metadata exists inside the document itself. You extract it, you don't infer it.

|Metadata|Where It Comes From|Example|
|---|---|---|
|Title|Document properties, `<title>` tag|"Q3 Earnings Report"|
|Author|Document properties|"Jane Smith"|
|Created date|File system or document properties|"2024-10-15"|
|Modified date|File system|"2024-10-20"|
|Page count|PDF structure|24|
|Word count|Computed from content|5,420|

**PDF example (using pypdf):**

```python
from pypdf import PdfReader

reader = PdfReader("report.pdf")
info = reader.metadata

metadata = {
    "title": info.title,
    "author": info.author,
    "created_date": info.creation_date,
    "page_count": len(reader.pages)
}
```

**HTML example:**

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html_content, "html.parser")

metadata = {
    "title": soup.title.string if soup.title else None,
    "description": soup.find("meta", {"name": "description"})["content"] 
                   if soup.find("meta", {"name": "description"}) else None,
    "author": soup.find("meta", {"name": "author"})["content"]
              if soup.find("meta", {"name": "author"}) else None
}
```

### Extrinsic Metadata (From Context)

This metadata doesn't exist in the file—you know it from the context of how/where the document was obtained.

|Metadata|How You Know It|Example|
|---|---|---|
|Source URL|You fetched it from there|"https://company.com/reports/q3.pdf"|
|Collection/category|You organized it|"financial_reports"|
|Ingestion timestamp|You recorded it|"2024-10-25T14:30:00Z"|
|Uploader/owner|Your system tracked it|"finance_team"|

You have to explicitly capture this at load time—it won't be in the file.

```python
import datetime

metadata = {
    "source_url": "https://company.com/reports/q3_2024.pdf",
    "collection": "quarterly_reports",
    "ingested_at": datetime.datetime.utcnow().isoformat(),
    "ingested_by": "data_pipeline_v2"
}
```

### Derived Metadata (Computed from Content)

This metadata is inferred or computed by analyzing the content.

|Metadata|How It's Computed|Example|
|---|---|---|
|Language|Language detection|"en"|
|Content type|Classification|"financial_report"|
|Key entities|NER extraction|["Apple Inc.", "Q3 2024"]|
|Summary|LLM summarization|"Quarterly earnings showing..."|
|Chunk index|Position in sequence|3 of 15|

```python
from langdetect import detect

content = "Revenue increased significantly in the third quarter..."
metadata = {
    "language": detect(content),  # "en"
    "word_count": len(content.split()),
    "char_count": len(content)
}
```

### Structural Metadata (Position Within Document)

This metadata describes where the content sits within the document's structure.

|Metadata|What It Captures|Example|
|---|---|---|
|Page number|Position in PDF|7|
|Section header|Hierarchical location|"Financial Highlights > Revenue"|
|Chunk sequence|Order among chunks|"chunk 3 of 12"|
|Parent document|Source before chunking|"quarterly_report_q3_2024.pdf"|

Structural metadata is critical for:

- Pointing users to exact locations ("see page 7")
- Maintaining context during chunking (what section is this chunk from?)
- Reassembling context (get surrounding chunks)

---

## Metadata Schema Design

Before you start loading documents, decide what metadata you'll track. This is a schema design problem.

### Questions to Ask

1. **What will users filter by?**
    
    - Date ranges? → Capture dates
    - Document types? → Capture categories
    - Departments/teams? → Capture ownership
2. **What do users need for attribution?**
    
    - Source document name
    - Page/section for navigation
    - Date for recency
3. **What will you need for debugging?**
    
    - Ingestion timestamp
    - Processing pipeline version
    - Original file path

### Example Schema

```python
metadata_schema = {
    # Identification
    "doc_id": str,           # Unique identifier
    "source": str,           # Filename or URL
    "file_type": str,        # pdf, html, md, docx
    
    # Temporal
    "created_date": str,     # When document was created (ISO format)
    "modified_date": str,    # When document was last modified
    "ingested_at": str,      # When we loaded it
    
    # Structural
    "page": int,             # Page number (PDFs)
    "section": str,          # Section header if available
    "chunk_index": int,      # Position after chunking
    "total_chunks": int,     # Total chunks from this document
    
    # Categorical
    "document_type": str,    # report, memo, policy, etc.
    "department": str,       # finance, engineering, legal
    
    # Content-derived
    "language": str,         # Detected language
    "word_count": int        # Content length
}
```

---

## Practical Extraction Patterns

### Pattern 1: Extract at Load Time

Capture all available metadata when you first read the file:

```python
import os
import datetime
from pypdf import PdfReader

def load_pdf_with_metadata(file_path: str) -> dict:
    reader = PdfReader(file_path)
    info = reader.metadata
    
    # File system metadata
    stat = os.stat(file_path)
    
    pages = []
    for page_num, page in enumerate(reader.pages):
        pages.append({
            "content": page.extract_text(),
            "metadata": {
                # Intrinsic (from PDF)
                "title": info.title if info else None,
                "author": info.author if info else None,
                "created_date": str(info.creation_date) if info and info.creation_date else None,
                
                # Extrinsic (from context)
                "source": os.path.basename(file_path),
                "file_path": file_path,
                "file_type": "pdf",
                
                # Structural
                "page": page_num + 1,  # 1-indexed for human readability
                "total_pages": len(reader.pages),
                
                # System
                "file_size_bytes": stat.st_size,
                "ingested_at": datetime.datetime.utcnow().isoformat()
            }
        })
    
    return pages
```

### Pattern 2: Propagate Metadata Through Chunking

When you chunk documents, metadata must travel with each chunk:

```python
def chunk_document(document: dict, chunk_size: int) -> list[dict]:
    content = document["content"]
    base_metadata = document["metadata"]
    
    chunks = []
    # Simple chunking (you'll learn better strategies later)
    for i in range(0, len(content), chunk_size):
        chunk_content = content[i:i + chunk_size]
        
        chunk_metadata = base_metadata.copy()
        chunk_metadata["chunk_index"] = len(chunks)
        chunk_metadata["chunk_start_char"] = i
        
        chunks.append({
            "content": chunk_content,
            "metadata": chunk_metadata
        })
    
    # Update total_chunks now that we know it
    for chunk in chunks:
        chunk["metadata"]["total_chunks"] = len(chunks)
    
    return chunks
```

### Pattern 3: Enrich Metadata Post-Load

Sometimes you compute metadata after initial loading:

```python
from langdetect import detect

def enrich_metadata(document: dict) -> dict:
    content = document["content"]
    metadata = document["metadata"]
    
    # Derived metadata
    metadata["language"] = detect(content) if len(content) > 20 else "unknown"
    metadata["word_count"] = len(content.split())
    metadata["char_count"] = len(content)
    
    # Content-based classification (simple example)
    content_lower = content.lower()
    if "quarterly" in content_lower and "revenue" in content_lower:
        metadata["document_type"] = "financial_report"
    elif "policy" in content_lower:
        metadata["document_type"] = "policy_document"
    else:
        metadata["document_type"] = "general"
    
    return document
```

---

## Common Mistakes

### 1. Capturing Metadata You Never Use

Every metadata field has storage cost. If you're capturing 20 fields but only filtering/displaying 3, you're wasting space and adding complexity.

**Fix:** Start minimal. Add fields when you have a concrete use case.

### 2. Inconsistent Schemas Across Document Types

PDFs have page numbers. HTML doesn't. If your schema requires `page` for all documents, HTML documents break or have `null` values.

**Fix:** Design for the union of all document types. Make type-specific fields optional.

```python
# Good: Optional fields with clear semantics
metadata = {
    "page": 7,              # Present for PDFs
    "section": "Overview",  # Present for structured docs
    "url": None,            # Present for web pages
}
```

### 3. Losing Metadata During Processing

You load a document with rich metadata. You chunk it. You embed it. Somewhere in the pipeline, metadata gets dropped. Now your vectors have no context.

**Fix:** Treat metadata as first-class. Every transformation should explicitly handle metadata propagation.

### 4. Not Normalizing Values

One document has `created_date: "2024-10-15"`. Another has `created_date: "October 15, 2024"`. A third has `created_date: 1728950400` (Unix timestamp).

**Fix:** Normalize at ingestion time. Pick a format (ISO 8601 for dates) and convert everything.

```python
from dateutil import parser

def normalize_date(date_value) -> str:
    if date_value is None:
        return None
    if isinstance(date_value, (int, float)):
        # Unix timestamp
        return datetime.datetime.fromtimestamp(date_value).isoformat()
    if isinstance(date_value, str):
        return parser.parse(date_value).isoformat()
    return str(date_value)
```

---

## What Metadata Enables Downstream

Thinking ahead to where this metadata gets used:

|Stage|How Metadata Is Used|
|---|---|
|**Indexing**|Stored alongside vectors in vector store|
|**Retrieval**|Pre-filter by date, type, department before similarity search|
|**Reranking**|Boost recent documents, authoritative sources|
|**Generation**|Include source attribution in prompt|
|**Response**|Display source, page number to user|
|**Debugging**|Trace retrieved chunks back to original documents|

The metadata you capture at load time determines what's possible at every subsequent stage. You can't filter by date if you didn't capture dates. You can't attribute to page numbers if you didn't track pages.

---

## Mental Model

Metadata is your **provenance chain**—the record of where content came from and what context surrounds it.

In RAG, the content answers "what does the document say?" The metadata answers:

- "Where did this come from?"
- "When was this written?"
- "Is this still relevant?"
- "Can I trust this source?"
- "How do I find the original?"

Capture metadata with the mindset of a future debugger or a user who needs to verify. What would they need to know about this chunk that isn't in the text itself?