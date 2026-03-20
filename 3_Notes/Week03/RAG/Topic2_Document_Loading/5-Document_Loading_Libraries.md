## Document Loading Libraries: Quick Reference

### pypdf

**What:** Low-level PDF text extraction library.

**Use for:** Reading PDFs directly, extracting text page-by-page, accessing PDF metadata.

```python
from pypdf import PdfReader

reader = PdfReader("report.pdf")
for page in reader.pages:
    text = page.extract_text()
```

**Limitations:** Basic text extraction only. Tables become jumbled. No OCR for scanned PDFs.

---

### unstructured

**What:** Multi-format loader that classifies content into semantic elements (Title, NarrativeText, Table, etc.).

**Use for:** Loading many file types with one API, getting structure-aware extraction.

```python
from unstructured.partition.auto import partition

elements = partition("document.pdf")  # Works with PDF, HTML, DOCX, etc.
```

**Note:** Core library is free/open source. Advanced features (better tables, image extraction) are paid API.

---

### LangChain Document Loaders

**What:** Collection of 100+ pre-built loaders that return standardized `Document` objects.

**Use for:** Quick integration with many sources (files, web, databases, cloud storage).

```python
from langchain_community.document_loaders import PyPDFLoader

loader = PyPDFLoader("report.pdf")
docs = loader.load()  # Returns List[Document] with page_content + metadata
```

**Note:** Uses libraries like `pypdf`, `unstructured` under the hood. Convenient wrapper, not magic.

---

### LlamaIndex Document Loaders (Readers)

**What:** Similar to LangChain—pre-built loaders returning standardized `Document` objects.

**Use for:** Same use cases as LangChain, different ecosystem.

```python
from llama_index.readers.file import PDFReader

reader = PDFReader()
docs = reader.load_data("report.pdf")  # Returns List[Document] with text + metadata
```

**Note:** LlamaIndex calls them "Readers" instead of "Loaders." Same concept.

---

### When to Use What

| Situation                                     | Use                                                |
| --------------------------------------------- | -------------------------------------------------- |
| Learning how extraction works                 | `pypdf`, `beautifulsoup` (raw libraries)           |
| Quick prototype, standard formats             | LangChain or LlamaIndex loaders                    |
| Multiple file types, need structure awareness | `unstructured`                                     |
| Production with specific format needs         | Choose based on extraction quality for that format |