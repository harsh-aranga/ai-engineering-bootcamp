"""
This script corresponds to Day 5-6->Day 5->Hour 2->Experiment->

Temperature exploration:

Same creative prompt at temperature 0, 0.5, and 1.0
Same factual prompt at temperature 0, 0.5, and 1.0
Note the differences
"""
from openai.types.responses import Response

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

from openai import OpenAI

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key = open_ai_key)

def generate_openai_gpt_response(prompt: str, model: str = "gpt-5.4-mini", temperature: float = 1.0) -> Response | None:
    """
    Takes a prompt, temperature and model. Returns the response
    :param temperature: The temperature the model must use to answer questions
    :param prompt: The prompt that user sends
    :param model: The gpt model that will process the prompt. Defaults to gpt-5.4-mini
    :return: openai.resources.responses.Response
    """

    try:
        response = openai_client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=200,
            temperature=temperature
        )

        if response is not None:
            logger.info("Response created successfully")
            return response
    except Exception as e:
        logger.error("Error %s", e)
        return None


def creative_prompt_manager() -> None:
    """
    Runs creative prompt flow at various temps(0, 0.5, 1.0, 2.0).
    :return: None
    """
    prompt = """Write a short story (150–200 words) about a lighthouse keeper 
    who discovers that the light they maintain does not guide ships, 
    but controls time itself."""

    logger.info(f"Prompt used: {prompt}")

    for temp in [0, 0.5, 1.0, 2.0]:
        answer_object = generate_openai_gpt_response(prompt, "gpt-5.4-mini", temp)
        if answer_object is not None:
            dump_json(answer_object.model_dump(), f"creative at temp {temp}")
            logger.info("Answer for temp %f: %s", temp, answer_object.output_text)
        else:
            logger.error(f"No response returned for temp run at {temp}")

        logger.info("-" * 150)


def factual_prompt_manager() -> None:
    """
    Runs factual prompt flow at various temps(0, 0.5, 1.0, 2.0).
    :return: None
    """
    prompt = """Explain how DNS resolution works when a user enters a URL in a browser. 
    Include the role of recursive resolvers, root servers, 
    TLD servers, and authoritative name servers."""

    logger.info(f"Prompt used: {prompt}")

    for temp in [0, 0.5, 1.0, 2.0]:
        answer_object = generate_openai_gpt_response(prompt, "gpt-5.4-mini", temp)
        if answer_object is not None:
            dump_json(answer_object.model_dump(), f"factual at temp {temp}")
            logger.info("Answer for temp %f: %s", temp, answer_object.output_text)
        else:
            logger.error(f"No response returned for temp run at {temp}")

        logger.info("-" * 150)

def vague_vs_specific_prompt_orchestrator() -> None:
    """
    The orchestrator for this script.
    Executes a fixed flow. First runs creative prompt and then runs a factual prompt.
    :return: None
    """
    logger.info("Executing Creative Prompt Manager")
    creative_prompt_manager()

    logger.info("Executing Factual Prompt Manager")
    factual_prompt_manager()

    logger.info("End of orchestration")

if __name__ == "__main__":
    vague_vs_specific_prompt_orchestrator()