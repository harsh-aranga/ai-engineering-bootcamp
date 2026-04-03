"""
This script corresponds to Day 3-4->Day 3->Experiment->
Load a markdown file — compare what you get vs. raw file
"""

from langchain_community.document_loaders import UnstructuredMarkdownLoader

from common.logger import get_logger
from common.dumper import dump_json

logger = get_logger(__file__)

def load_and_print_markdown(markdown:str) -> None:
    """
    Loads a markdown using unstructured. Prints them as individual elements
    :param markdown:
    :return:
    """
    markdown_loader = UnstructuredMarkdownLoader(
        file_path=markdown,
        mode="elements",
        strategy="fast"
    )

    elements = markdown_loader.load()
    dump_json([elem.model_dump() for elem in elements], "Elements Of the Markdown Page")
    logger.info(f"Count of elements: {len(elements)}")
    for item_number, element in enumerate(elements):
        logger.info(f"Item number {item_number}: {element}")

if __name__ == "__main__":
    load_and_print_markdown("Document_Loading_Libraries.md")