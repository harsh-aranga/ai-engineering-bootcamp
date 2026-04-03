"""
Build a chunk_document() function:

Success Criteria:

Implements at least 2 strategies: fixed and recursive
Respects chunk_size (chunks should be approximately this size, not wildly over)
Applies overlap correctly (adjacent chunks share overlap content)
Preserves and extends metadata (adds chunk_index)
Handles edge cases: content shorter than chunk_size, empty content
Test: Same document, different strategies — print and compare chunk quality
Bonus: Implement semantic chunking (split on paragraph/section boundaries)
"""
import logging
from typing import Any, Literal
from pydantic import SecretStr

from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from unstructured.partition.md import partition_md

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

logger = get_logger(__file__)
config = get_config()
open_ai_key = SecretStr(config.get("OPEN_AI_KEY"))

embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=open_ai_key)

def load_markdown_document(source: str) -> tuple[list[dict[str, str | Any]], str] | None:
    """
    Loads a Markdown document and returns list of content chunks with metadata.
    Returns:
        List of {"content": str, "metadata": {"source": str, "page": int, ...}}
    """
    try:
        elements = partition_md(source)

        content = [
            {
                "content": element.text,
                "metadata": element.metadata.to_dict()
            }
            for element in elements
        ]
        dump_json(content, "content read")

        text_read = ""
        for item in content:
            text_read += " " + item.get("content")

        return content, text_read
    except Exception:
        logger.exception("Error reading file")
        return None


def chunk_document(
        content: str,
        strategy: Literal["fixed", "recursive", "semantic"] = "fixed",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        source_metadata: dict = None
) -> list[dict]:
    """
    Chunks document content using specified strategy.

    Returns:
        List of {"content": str, "metadata": {..., "chunk_index": int}}
    """

    if not content or not content.strip():
        return []

    source_metadata = source_metadata or {}

    if len(content) <= chunk_size:
        return [{"content": content, "metadata": {**source_metadata, "chunk_index": 0}}]

    if strategy == "fixed":
        splitter = CharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separator=" ",
            add_start_index=True,  # track index in original document
        )
    elif strategy == "recursive":
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,  # track index in original document
        )
    elif strategy == "semantic":
        splitter = SemanticChunker(
            min_chunk_size=chunk_size,
            embeddings=embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=95
        )
    else:
        logging.exception("Invalid Method. Supported methods: fixed or recursive")
        raise ValueError("Invalid splitter method")

    all_splits = splitter.split_text(content)

    response_json = [
        {
            "content": chunk_data,
            "metadata": {
                **source_metadata,
                "chunk_index": chunk_number
            }
        }
        for chunk_number, chunk_data in enumerate(all_splits)
    ]

    logger.info(f"Split text into {len(all_splits)} chunks.")
    dump_json(response_json, f"Chunks obtained by {strategy}")

    return response_json


if __name__ == "__main__":

    metadata = {
        "source": "sample.md",
        "type": "markdown",
        "author": "John Doe"
    }

    doc_content, text = load_markdown_document("sample.md")

    # chunks = chunk_document(text, "fixed", chunk_size=500, chunk_overlap=0, source_metadata=metadata)

    # chunks = chunk_document(text, "fixed", chunk_size=500, chunk_overlap=100, source_metadata=metadata)

    # chunks = chunk_document(text, "recursive", chunk_size=500, chunk_overlap=100, source_metadata=metadata)

    chunks = chunk_document(text, "semantic", chunk_size=500, chunk_overlap=100, source_metadata=metadata)

    for count, chunk in enumerate(chunks):
        if count <= 5:
            logger.info(f"Chunk {count}: \n{chunk}")