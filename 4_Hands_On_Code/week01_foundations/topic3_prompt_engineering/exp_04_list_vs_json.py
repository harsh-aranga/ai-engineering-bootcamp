"""
This script corresponds to Day 5-6->Day 5->Hour 2->Experiment->

Output format:
Ask for "a list of 5 items" (vague format)
Ask for "a JSON array with exactly 5 strings" (specific format)
Which is more reliable for parsing programmatically?
"""
from typing import Literal
from openai.types.responses import Response

import sys

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

from openai import OpenAI

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key = open_ai_key)

def generate_openai_gpt_response(prompt: str, model: str = "gpt-5.4-mini") -> Response | None:
    """
    Takes a prompt and model. Returns the response
    :param prompt: The prompt that user sends
    :param model: The gpt model that will process the prompt. Defaults to gpt-5.4-mini
    :return: openai.resources.responses.Response
    """

    try:
        response = openai_client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=500,
            temperature=0
        )

        if response is not None:
            logger.info("Response created successfully")
            return response
    except Exception as e:
        logger.error("Error %s", e)
        return None

def prompt_execution_helper(prompt: str, type_of_prompt: str) -> None:
    """
    A helper method that executes the prompt and process it for output
    :param type_of_prompt: The prompt type for this run like list prompt, json prompt, etc.
    :param prompt: The prompt to run
    :return: None
    """
    answer_object = generate_openai_gpt_response(prompt)

    if answer_object is not None:
        dump_json(answer_object.model_dump(), type_of_prompt)
        logger.info("Answer for %s: %s", type_of_prompt, answer_object.output_text)
    else:
        logger.error("No response returned")

def vague_vs_specific_prompt_orchestrator() -> None:
    """
    The orchestrator for this script. Does a list of items run, followed by a json array list run for same question.
    Based on the type of prompt parameter executes appropriate flow.
    :return: None
    """

    list_prompt = "Give me a list of 5 vegetables, their color, their taste and avg weight of their one vegetable unit"
    prompt_execution_helper(list_prompt, "List prompt")

    zero_shot_json_prompt = """Give me a list of 5 vegetables, their color, their taste and avg weight of their one vegetable unit.
    I want them as json array of objects"""
    prompt_execution_helper(zero_shot_json_prompt, "Zero shot json prompt")

    one_shot_json_prompt = """Give me a list of 5 vegetables, their color, their taste and avg weight of their one vegetable unit.
    I want them as json array of objects like
    [
    {
        "name": "Onion",
        "color": ["purple", "white"], //can be multiple colors 
        "taste": "astringent",
        "avg_weight": "200 gms"
    }
    ]
    Return ONLY valid JSON. 
    Do not include markdown, explanations, or code blocks. 
    The response must be directly parseable using json.loads()."""
    prompt_execution_helper(one_shot_json_prompt, "One shot json prompt")

if __name__ == "__main__":
    vague_vs_specific_prompt_orchestrator()