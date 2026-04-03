"""
This script corresponds to Day 3-4->Day 3->Experiment->
Load a simple PDF — print the extracted text
"""
from pypdf import PdfReader
from sqlalchemy.sql.base import elements

from common.logger import get_logger
from common.dumper import dump_json

logger = get_logger(__file__)

def load_and_print_pdf(pdf_name:str) -> None:
    """
    Loads the given pdf and prints its pages using PyPDF
    :param pdf_name:
    :return:
    """
    reader = PdfReader(pdf_name)

    pdf_dump = {
        "pdf_header": reader.pdf_header,
        "is_encrypted": reader.is_encrypted,
        "metadata": dict(reader.metadata or {}),
        "page_count": len(reader.pages),
        "pages": [
            {
                "page_number": i,
                "text": page.extract_text()
            }
            for i, page in enumerate(reader.pages)
        ]
    }

    dump_json(pdf_dump, "Entire Reader Object")

    logger.info("PDF read successfully. Printing pages...")
    for page_data in pdf_dump["pages"]:
        logger.info(f"Page {page_data['page_number'] + 1} Content: {page_data['text']}")

if __name__ == "__main__":
    load_and_print_pdf("Published_Paper_AI_Cache.pdf")