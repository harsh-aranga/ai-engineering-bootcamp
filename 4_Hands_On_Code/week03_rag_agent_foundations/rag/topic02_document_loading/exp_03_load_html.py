"""
This script corresponds to Day 3-4->Day 3->Experiment->
Load a web page (use requests + BeautifulSoup or a loader) — see how much noise you get
"""
from typing import Literal

from unstructured.partition.html import partition_html

import requests
import urllib3
from bs4 import BeautifulSoup

from common.logger import get_logger
from common.dumper import dump_json

logger = get_logger(__file__)

def load_and_print_html(website_link:str, load_type:Literal["bs4", "unstructured"]="bs4") -> None:
    """
    Loads a website using BeautifulSoup or Langchain based on load_type. Prints them as individual elements
    :param load_type:
    :param website_link:
    :return:
    """
    # Suppress the warning spam
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if load_type == "bs4":
        response = requests.get(website_link, verify=False)
        soup = BeautifulSoup(response.text, "html.parser")
        dump_json(soup.prettify(), "BS4 extract")
        logger.info(soup.get_text())  # Wall of noise
    else:
        elements = partition_html(url=website_link, ssl_verify=False)
        dump_json([element.to_dict() for element in elements], "Unstructured extract")
        logger.info([element.to_dict() for element in elements])


if __name__ == "__main__":
    # load_and_print_html("https://example.com")
    # load_and_print_html("https://httpbin.org/html", "unstructured")
    load_and_print_html("https://motherfuckingwebsite.com", "unstructured")