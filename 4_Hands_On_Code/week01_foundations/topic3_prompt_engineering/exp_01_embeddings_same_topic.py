"""
This script corresponds to Day 5-6->Day 5->Hour 2->Experiment->

Vague vs. Specific:
Vague: "Write about climate change"
Specific: "Write 3 bullet points explaining why sea levels rise due to climate change, suitable for a 10-year-old"
Compare outputs
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
            max_output_tokens=100,
            temperature=1
        )

        if response is not None:
            logger.info("Response created successfully")
            return response
    except Exception as e:
        logger.error("Error %s", e)
        return None

def vague_vs_specific_prompt_orchestrator(type_of_prompt: Literal["vague", "specific"] = "vague") -> None:
    """
    The orchestrator for this script.
    Based on the type of prompt parameter executes appropriate flow.
    :param type_of_prompt: Literal. Takes two values "vague" and "specific". Defaults to specific
    :return: None
    """
    if type_of_prompt == "vague":
        answer_object = generate_openai_gpt_response("Write about climate change")
        json_dump_label = "llm response for vague prompt"
    else:
        answer_object = generate_openai_gpt_response("Write 3 bullet points explaining why sea levels rise due to climate change, "
                                                     "suitable for a 10-year-old")
        json_dump_label = "llm response for specific prompt"

    if answer_object is not None:
        dump_json(answer_object.model_dump(), json_dump_label)
        logger.info("Answer: %s", answer_object.output_text)
    else:
        logger.error("No response returned")

if __name__ == "__main__":
    prompt_type = sys.argv[1] if len(sys.argv) > 1 else "vague"

    if prompt_type not in ("vague", "specific"):
        logger.error("Invalid prompt type: %s", prompt_type)
        sys.exit(1)

    vague_vs_specific_prompt_orchestrator(prompt_type)