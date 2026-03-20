# Structure Preservation vs. Plain Text Extraction

## The Core Distinction

**Plain text extraction:** Get all the characters out of the document as a single string. Throw away everything else—layout, formatting, relationships between elements.

**Structure preservation:** Maintain semantic relationships between elements. Know that these cells belong to a table, this text is a heading, these items are a list, this is a code block.

---

## Why This Matters for RAG

Consider a financial report table:

**Original structure (what the human sees):**

|Quarter|Revenue|Growth|
|---|---|---|
|Q1 2024|$2.1B|+12%|
|Q2 2024|$2.4B|+14%|
|Q3 2024|$2.2B|-8%|

**Plain text extraction (what naive loading produces):**

```
Quarter Revenue Growth Q1 2024 $2.1B +12% Q2 2024 $2.4B +14% Q3 2024 $2.2B -8%
```

Or worse, depending on how the PDF was created:

```
Quarter Q1 2024 Q2 2024 Q3 2024 Revenue $2.1B $2.4B $2.2B Growth +12% +14% -8%
```

**Now imagine the query:** "What was the revenue growth in Q2?"

With plain text, the LLM has to reconstruct the table relationships from a jumbled string. It might work. It might hallucinate. It's fragile.

With preserved structure, the chunk contains:

```
| Q2 2024 | $2.4B | +14% |
```

The relationship between Q2 and +14% is explicit. The LLM doesn't have to guess.

---

## What "Structure" Actually Means

Structure is semantic relationships between content elements:

|Structure Type|What It Captures|Example|
|---|---|---|
|**Hierarchy**|Parent-child relationships|Heading → subheading → paragraph|
|**Tabular**|Row-column relationships|Cell at row 2, column 3|
|**Sequential**|Ordered relationships|Step 1, Step 2, Step 3|
|**Nested**|Containment relationships|Code block inside a section|
|**Reference**|Pointer relationships|Footnote linked to text|

Plain text extraction discards all of this. You get characters in some order, but the _meaning_ of their arrangement is lost.

---

## The Tradeoff Space

This isn't binary. There's a spectrum:

```
Pure Plain Text ←————————————————————→ Full Structure Preservation
     ↑                                              ↑
  Simple                                        Complex
  Fast                                          Slower
  Universal                                     Format-specific
  Lossy                                         Faithful
```

**Pure plain text:**

- Fastest to implement
- Works on anything with text
- Loses all structural semantics

**Full structure preservation:**

- Complex parsing logic per format
- Outputs structured data (JSON, XML, markdown with conventions)
- Maintains semantic relationships

**Practical middle ground:**

- Convert structure to text representations the LLM can understand
- Tables become markdown tables
- Lists keep their markers
- Headings keep their hierarchy indicators

---

## Practical Approaches by Document Type

### PDF Tables

**Plain extraction (pypdf):**

```python
from pypdf import PdfReader

reader = PdfReader("financial_report.pdf")
text = reader.pages[0].extract_text()
# Tables become jumbled text
```

**Structure-aware extraction (pdfplumber):**

```python
import pdfplumber

with pdfplumber.open("financial_report.pdf") as pdf:
    page = pdf.pages[0]
    tables = page.extract_tables()
    
    for table in tables:
        # table is a list of rows, each row is a list of cells
        # [['Quarter', 'Revenue', 'Growth'], ['Q1 2024', '$2.1B', '+12%'], ...]
        
        # Convert to markdown for LLM consumption
        markdown_table = convert_to_markdown(table)
```

The extracted table can then be converted to a format the LLM understands:

```markdown
| Quarter | Revenue | Growth |
|---------|---------|--------|
| Q1 2024 | $2.1B   | +12%   |
```

### HTML Structure

**Plain extraction:**

```python
from bs4 import BeautifulSoup

html = "<h1>Title</h1><p>First paragraph.</p><ul><li>Item 1</li><li>Item 2</li></ul>"
soup = BeautifulSoup(html, "html.parser")
text = soup.get_text()
# "Title First paragraph. Item 1 Item 2"
```

**Structure-preserving extraction:**

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html, "html.parser")

# Preserve heading hierarchy
for h in soup.find_all(['h1', 'h2', 'h3']):
    level = int(h.name[1])
    h.string = '#' * level + ' ' + h.get_text()

# Preserve list structure
for li in soup.find_all('li'):
    li.string = '- ' + li.get_text()

text = soup.get_text(separator='\n')
# "# Title\nFirst paragraph.\n- Item 1\n- Item 2"
```

### Markdown (Already Structured)

Markdown is interesting because it's already text with structure encoded in it.

**Option 1: Keep as-is** The structure markers (`#`, `-`, `|`) are text the LLM can interpret.

**Option 2: Parse and extract** Use a markdown parser to identify sections, then chunk by section boundaries.

```python
import re

content = """
# Introduction
First section content.

## Background
Subsection content here.

## Methods
Another subsection.
"""

# Split by headers, keeping header with its content
sections = re.split(r'(^#{1,3} .+$)', content, flags=re.MULTILINE)
```

---

## When Plain Text Is Actually Fine

Not every document needs structure preservation:

**Plain text works when:**

- Document is prose (articles, essays, narratives)
- No tables, lists, or complex formatting
- Chunks will be large enough to contain full context
- Speed/simplicity matters more than precision

**Structure preservation matters when:**

- Tables with relationships (financial data, specifications, comparisons)
- Technical documentation with code blocks
- Legal documents with numbered clauses and references
- Any content where position conveys meaning

---

## The Chunking Connection

Structure preservation affects how you chunk.

**Plain text chunking:** Split by character count or token count. Hope you don't cut a table in half.

**Structure-aware chunking:** Use structural boundaries.

- Don't split in the middle of a table
- Keep heading with its content
- Respect code block boundaries
- Use section markers as natural chunk boundaries

This is why loading and chunking aren't fully independent—what you preserve at load time determines what boundaries you can respect at chunk time.

---

## Representing Structure for LLMs

The LLM ultimately receives text. So even if you preserve structure, you need to serialize it.

**Common approaches:**

**1. Markdown representation**

```markdown
## Financial Results

| Quarter | Revenue |
|---------|---------|
| Q1 | $2.1B |
| Q2 | $2.4B |
```

LLMs trained on code and markdown understand this well.

**2. Explicit descriptions**

```
The following is a table with 2 columns (Quarter, Revenue) and 2 data rows:
Row 1: Quarter=Q1, Revenue=$2.1B
Row 2: Quarter=Q2, Revenue=$2.4B
```

More verbose but unambiguous.

**3. JSON/structured format**

```json
{
  "type": "table",
  "headers": ["Quarter", "Revenue"],
  "rows": [["Q1", "$2.1B"], ["Q2", "$2.4B"]]
}
```

Precise but uses more tokens.

---

## Mental Model

Think of structure preservation as **information triage**:

1. **What relationships exist** in the original document?
2. **Which relationships matter** for answering questions about this content?
3. **How to encode those relationships** in a text format the LLM can interpret?

Plain text extraction answers "what characters are here?" Structure preservation answers "how do these characters relate to each other?"

For RAG, the question is always: will the LLM be able to answer correctly without knowing this relationship? If a table becomes a word soup and the LLM can still figure it out—maybe plain text is fine. If the answer depends on knowing that X and Y are in the same row—you need structure.