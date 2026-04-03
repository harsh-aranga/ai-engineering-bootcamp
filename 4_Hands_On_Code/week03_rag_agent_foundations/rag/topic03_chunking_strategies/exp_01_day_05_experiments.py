"""
This script corresponds to Day 5-6->Day 5->Experiment->
1. Take a document from Day 3-4
2. Chunk it with fixed size (500 chars, no overlap)
3. Chunk same doc with fixed size (500 chars, 50 char overlap)
4. Chunk with recursive splitter (same size)
5. Compare: Print first 5 chunks from each. Which looks more coherent?
"""
import logging
from typing import Any, Literal

from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter
from unstructured.partition.md import partition_md

import bs4

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

logger = get_logger(__file__)


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


def chunk_document_orchestrator(text_to_chunk: str, overlap: int = 0,
                                method: Literal["fixed", "recursive"] = "fixed") -> list[str]:
    """
    Splits text as per the method requested. Can use overlap as necessary.
    :param text_to_chunk:
    :param method:
    :param overlap: if 0 no overlap. Else used for both fixed and recursive
    :return:
    """
    all_splits = []
    splitter = None
    if method == "fixed":
        splitter = CharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=overlap,
            separator=" ",
            add_start_index=True,  # track index in original document
        )
    elif method == "recursive":
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=overlap,
            add_start_index=True,  # track index in original document
        )
    else:
        logging.exception("Invalid Method. Supported methods: fixed or recursive")
        raise ValueError("Invalid splitter method")

    all_splits = splitter.split_text(text_to_chunk)

    json_for_dump = [
            {
                "count": chunk_number,
                "chunk": split
            }
            for chunk_number, split in enumerate(all_splits)
        ]

    logger.info(f"Split text into {len(all_splits)} chunks.")
    dump_json(json_for_dump, f"Chunks obtained by {method}")

    return all_splits


if __name__ == "__main__":
    content, text = load_markdown_document("sample.md")

    # chunks = chunk_document_orchestrator(text, 0, "fixed")

    # chunks = chunk_document_orchestrator(text, 50, "fixed")

    chunks = chunk_document_orchestrator(text, 50, "recursive")

    for count, chunk in enumerate(chunks):
        if count <= 5:
            logger.info(f"Chunk {count}: \n{chunk}")