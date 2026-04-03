"""
This script corresponds to Day 3-4->Day 4->Mini Challenge->
Build a load_document() function:
Success Criteria:

Correctly detects file type from extension
Loads PDF and extracts text (test with a multi-page PDF)
Loads markdown preserving basic structure
Loads plain text
Loads HTML and strips navigation/boilerplate (just main content)
Attaches metadata: source filename, page number (for PDFs), file type
Handles file not found gracefully (doesn't crash)
Tested with at least 4 different files (one of each type)
"""
from unstructured.partition.auto import partition

from common.logger import get_logger
from common.dumper import dump_json

logger = get_logger(__file__)

def load_document(source: str) -> list[dict]:
    """
    Loads a document and returns list of content chunks with metadata.
    Supports: .pdf, .md, .txt, .html
    Returns:
        List of {"content": str, "metadata": {"source": str, "page": int, ...}}
    """
    try:
        if source.startswith("http"):
            elements = partition(url=source, ssl_verify=False)
        else:
            elements = partition(filename=source)

        content = [
            {
                "content": element.text,
                "metadata": element.metadata.to_dict()
            }
            for element in elements
        ]
        dump_json(content, "content read")
        return content
    except Exception:
        logger.exception("Error reading file")
        return []

if __name__ == "__main__":
    # logger.info(load_document("https://example.com"))

    # logger.info(load_document("Published_Paper_AI_Cache.pdf"))

    # logger.info(load_document("Document_Loading_Libraries.md"))

    # logger.info(load_document("sample.txt"))

    logger.info(load_document("sample.xyz"))