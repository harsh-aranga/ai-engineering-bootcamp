# Handling Special Content: Tables, Code Blocks, Images

## The Core Problem

Documents aren't just prose. They contain structured and non-textual elements that carry significant information but don't survive naive text extraction.

|Content Type|Information It Carries|What Naive Extraction Produces|
|---|---|---|
|Tables|Row-column relationships, comparisons|Jumbled words, lost relationships|
|Code blocks|Executable logic, syntax, formatting|Broken indentation, lost boundaries|
|Images|Visual information, diagrams, charts|Nothing (completely lost)|

These elements often contain the _most important_ information in a document. A financial report's tables matter more than its prose. A technical doc's code examples are what developers actually need.

---

## Tables

### Why Tables Are Hard

Tables encode relationships through position. "Q1" and "$2.1B" are related because they're in the same row. This positional relationship is semantic meaning—and it's exactly what plain text extraction destroys.

**Original table:**

|Product|Q1 Sales|Q2 Sales|
|---|---|---|
|Widget A|$1.2M|$1.5M|
|Widget B|$800K|$950K|

**After naive PDF extraction:**

```
Product Q1 Sales Q2 Sales Widget A $1.2M $1.5M Widget B $800K $950K
```

Or worse (column-by-column extraction):

```
Product Widget A Widget B Q1 Sales $1.2M $800K Q2 Sales $1.5M $950K
```

Now try asking "What were Q2 sales for Widget B?" The LLM has to reconstruct the table mentally from a word soup.

### Extraction Strategies

**Strategy 1: Table-Aware PDF Libraries**

`pdfplumber` extracts tables as structured data:

```python
import pdfplumber

with pdfplumber.open("report.pdf") as pdf:
    page = pdf.pages[0]
    tables = page.extract_tables()
    
    for table in tables:
        # table = [
        #   ['Product', 'Q1 Sales', 'Q2 Sales'],
        #   ['Widget A', '$1.2M', '$1.5M'],
        #   ['Widget B', '$800K', '$950K']
        # ]
        print(table)
```

**Strategy 2: Convert to Markdown**

Once you have structured table data, convert to markdown—a format LLMs understand well:

```python
def table_to_markdown(table: list[list[str]]) -> str:
    if not table:
        return ""
    
    lines = []
    # Header row
    lines.append("| " + " | ".join(table[0]) + " |")
    # Separator
    lines.append("| " + " | ".join(["---"] * len(table[0])) + " |")
    # Data rows
    for row in table[1:]:
        lines.append("| " + " | ".join(row) + " |")
    
    return "\n".join(lines)

# Result:
# | Product | Q1 Sales | Q2 Sales |
# | --- | --- | --- |
# | Widget A | $1.2M | $1.5M |
# | Widget B | $800K | $950K |
```

**Strategy 3: Explicit Row Descriptions**

For complex tables or when markdown isn't enough:

```python
def table_to_explicit(table: list[list[str]]) -> str:
    if not table or len(table) < 2:
        return ""
    
    headers = table[0]
    lines = [f"Table with columns: {', '.join(headers)}"]
    
    for row in table[1:]:
        pairs = [f"{headers[i]}={row[i]}" for i in range(len(headers))]
        lines.append(f"Row: {', '.join(pairs)}")
    
    return "\n".join(lines)

# Result:
# Table with columns: Product, Q1 Sales, Q2 Sales
# Row: Product=Widget A, Q1 Sales=$1.2M, Q2 Sales=$1.5M
# Row: Product=Widget B, Q1 Sales=$800K, Q2 Sales=$950K
```

### Table Edge Cases

**Merged cells:** Headers span multiple columns. Most extractors handle this poorly.

**Nested tables:** Tables inside tables. Rare but nightmarish.

**Implicit headers:** First row isn't labeled as header. You have to infer.

**Split across pages:** Table starts on page 3, continues on page 4. Extraction gives you two separate tables.

**No borders:** Visual tables created with spacing, not actual table structure. Extractors might miss them entirely.

---

## Code Blocks

### Why Code Blocks Matter

In technical documentation, code is the payload. The prose explains; the code demonstrates. Losing code fidelity means your RAG system can't answer "how do I use this API?"

**What can go wrong:**

1. **Lost indentation** — Python becomes unparseable
2. **Lost boundaries** — Code merges with surrounding prose
3. **Lost syntax** — Special characters get mangled
4. **Language confusion** — Multiple code blocks in different languages

### Extraction Strategies

**Strategy 1: Preserve Markdown Fencing**

If the source is markdown, keep the fences:

```python
def preserve_code_blocks(markdown_content: str) -> str:
    # Code blocks are already marked with ``` fences
    # Just make sure you don't strip them during processing
    return markdown_content  # Keep as-is
```

The triple backticks tell the LLM "this is code, preserve formatting."

**Strategy 2: Detect and Mark Code in HTML**

```python
from bs4 import BeautifulSoup

def extract_with_code_blocks(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    
    # Find all code elements
    for code in soup.find_all(['code', 'pre']):
        # Get language if specified
        lang = code.get('class', [''])[0].replace('language-', '')
        
        # Wrap in markdown code fence
        code_text = code.get_text()
        code.string = f"\n```{lang}\n{code_text}\n```\n"
    
    return soup.get_text()
```

**Strategy 3: Explicit Code Block Metadata**

When chunking, track that a chunk contains code:

```python
def extract_code_with_metadata(content: str) -> list[dict]:
    import re
    
    chunks = []
    # Find fenced code blocks
    pattern = r'```(\w*)\n(.*?)```'
    
    for match in re.finditer(pattern, content, re.DOTALL):
        language = match.group(1) or "unknown"
        code = match.group(2)
        
        chunks.append({
            "content": f"```{language}\n{code}```",
            "metadata": {
                "content_type": "code",
                "language": language,
                "char_count": len(code)
            }
        })
    
    return chunks
```

### Code Block Considerations for RAG

**Chunking:** Don't split code blocks. A function split in half is useless.

**Embedding:** Code embeds differently than prose. Some embedding models handle code better than others. OpenAI's `text-embedding-3-*` models are trained on code. Specialized code embeddings (CodeBERT, etc.) exist.

**Retrieval:** Searching for code by natural language ("function that sorts a list") is a different problem than searching prose. Consider: does your retrieval need to find code, prose, or both?

---

## Images

### The Fundamental Challenge

Images are pixels. Text extraction produces nothing. But images often contain critical information:

- **Charts and graphs** — Trends, comparisons, data
- **Diagrams** — Architecture, workflows, relationships
- **Screenshots** — UI examples, error messages
- **Scanned text** — OCR required
- **Infographics** — Mixed visual and textual information

### Strategy 1: OCR for Text in Images

If the image contains text (scanned documents, screenshots), extract it:

```python
import pytesseract
from PIL import Image

def extract_text_from_image(image_path: str) -> str:
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image)
    return text
```

**OCR caveats:**

- Quality depends on image resolution
- Handwriting is unreliable
- Tables in images become jumbled text (same problem as PDFs)
- Non-English text needs language configuration

### Strategy 2: Vision LLM Description

Use a multimodal LLM to describe the image:

```python
import base64
from openai import OpenAI

def describe_image(image_path: str) -> str:
    client = OpenAI()
    
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Describe this image in detail. If it contains a chart or graph, describe the data and trends. If it's a diagram, explain the components and relationships."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_data}"}
                    }
                ]
            }
        ]
    )
    
    return response.choices[0].message.content
```

**This produces text** that can be embedded and retrieved. The image description becomes part of your searchable corpus.

### Strategy 3: Store Image Reference with Context

If you can't or don't want to process images, at least capture their existence and context:

```python
def extract_with_image_placeholders(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    
    for img in soup.find_all('img'):
        alt_text = img.get('alt', 'No description')
        src = img.get('src', 'unknown')
        
        # Replace image with descriptive placeholder
        placeholder = f"\n[IMAGE: {alt_text} (source: {src})]\n"
        img.replace_with(placeholder)
    
    return soup.get_text()
```

Now at least you know an image existed and what it was supposed to show.

### Strategy 4: Separate Image Index

For image-heavy documents, maintain a parallel index:

```python
document = {
    "content": "The architecture diagram below shows...",
    "metadata": {
        "source": "architecture.pdf",
        "page": 5
    },
    "images": [
        {
            "image_id": "arch_diagram_1",
            "page": 5,
            "description": "Three-tier architecture with load balancer, app servers, and database cluster",
            "image_path": "/images/arch_diagram_1.png"
        }
    ]
}
```

When the text chunk is retrieved, you can also surface the related image.

---

## Integrated Extraction Pipeline

Putting it together—a loader that handles all special content:

```python
import pdfplumber
from PIL import Image
import pytesseract
import io

def load_pdf_with_special_content(file_path: str) -> list[dict]:
    pages = []
    
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            content_parts = []
            
            # 1. Extract regular text
            text = page.extract_text() or ""
            if text.strip():
                content_parts.append(text)
            
            # 2. Extract tables and convert to markdown
            tables = page.extract_tables()
            for table in tables:
                if table:
                    md_table = table_to_markdown(table)
                    content_parts.append(f"\n{md_table}\n")
            
            # 3. Handle images
            images = page.images
            for img_info in images:
                # Extract image from PDF
                # This is simplified - actual extraction is more complex
                content_parts.append(f"\n[IMAGE on page {page_num + 1}]\n")
            
            pages.append({
                "content": "\n".join(content_parts),
                "metadata": {
                    "source": file_path,
                    "page": page_num + 1,
                    "has_tables": len(tables) > 0,
                    "has_images": len(images) > 0,
                    "table_count": len(tables),
                    "image_count": len(images)
                }
            })
    
    return pages
```

---

## Decision Framework

When you encounter special content, ask:

|Question|If Yes|If No|
|---|---|---|
|Does this content carry information needed to answer questions?|Must handle it|Can skip/placeholder|
|Can it be converted to text the LLM understands?|Convert it|Consider alternatives|
|Is the conversion reliable?|Automate it|Add human review or flag uncertainty|
|Does extraction quality matter for your use case?|Invest in better tools|Use simple approach|

### Effort vs. Value Matrix

```
                    High Information Value
                            ↑
         Financial Tables   │   Architecture Diagrams
         (Must extract      │   (Vision LLM or manual)
          perfectly)        │
                            │
    ←───────────────────────┼───────────────────────→
    Easy to Extract         │           Hard to Extract
                            │
         Markdown Code      │   Complex Nested Tables
         (Already text,     │   (Maybe good enough
          just preserve)    │    with basic extraction)
                            │
                            ↓
                    Low Information Value
```

---

## Mental Model

Special content is where naive extraction fails hardest. It's also often where the most important information lives.

Your job is to:

1. **Detect** — Know that special content exists
2. **Decide** — Is this content worth the extraction effort?
3. **Convert** — Transform to LLM-friendly text representation
4. **Preserve** — Keep relationships and structure intact
5. **Track** — Metadata should note what special content was present

The goal isn't perfect extraction of everything. It's ensuring that when a user asks a question, the information needed to answer it survives the loading process in a form the LLM can reason about.