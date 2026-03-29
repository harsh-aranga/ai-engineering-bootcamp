"""
This script corresponds to Day 1-2->Day 1->Hour 2->Experiment->
Force an error: send invalid model name, exceed max_tokens, send empty messages — see what errors look like
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
            max_output_tokens=300,
            temperature=0.5
        )

        if response is not None:
            logger.info("Response created successfully")
            return response
    except Exception as e:
        logger.error("Error %s", e)
        return None

def llm_response_inspector(llm_response: Response) -> None:
    """
    Inspects llm response object from openai gpt response api.
    :param llm_response: OpenAI Response object.
    :return: None
    """
    logger.info("++++++++Printing Metadata of Response Object++++++++")
    logger.info(f"Response created at: {llm_response.created_at}")
    logger.info(f"Response id: {llm_response.id}")
    logger.info(f"Model used: {llm_response.model}")
    logger.info(f"Response temperature: {llm_response.temperature}")
    logger.info("-" * 150)

    logger.info("++++++++Printing Completion Details++++++++")
    logger.info(f"Status of run: {llm_response.status}")
    logger.info(f"Reason for status: {llm_response.incomplete_details.reason if llm_response.incomplete_details else None}")
    logger.info("-" * 150)

    logger.info("++++++++Printing Usage Details++++++++")
    logger.info(f"Input Tokens: {llm_response.usage.input_tokens}")
    logger.info(f"Output Tokens: {llm_response.usage.output_tokens}")
    logger.info(f"Cached Tokens: {llm_response.usage.input_tokens_details.cached_tokens}")
    logger.info(f"Total Tokens: {llm_response.usage.total_tokens}")
    logger.info("-" * 150)

    logger.info("++++++++Printing Output Details++++++++")
    logger.info(f"Total outputs for run: {len(llm_response.output)}")
    logger.info(f"Output Id: {llm_response.output[0].id}")
    logger.info(f"Output phase: {llm_response.output[0].phase}")
    logger.info(f"Output role: {llm_response.output[0].role}")
    logger.info(f"Output status: {llm_response.output[0].status}")
    logger.info(f"Output type: {llm_response.output[0].type}")
    logger.info("-" * 150)

    logger.info("++++++++Printing Content Details++++++++")
    logger.info(f"Type of Content: {llm_response.output[0].content[0].type}")
    logger.info(f"Content as text: {llm_response.output[0].content[0].text}")
    logger.info("-" * 150)

def llm_response_orchestrator() -> None:
    """
    Runs a simple prompt and then prints the answer. Then calls inspector to inspect response object
    :return: None
    """
    # # Wrong model Sent
    # answer_object = generate_openai_gpt_response("Write about climate change", model="random-model-go-5.2")
    #
    # if answer_object is not None:
    #     dump_json(answer_object.model_dump(), "Wrong model")
    #     llm_response_inspector(answer_object)
    # else:
    #     logger.error("No response returned")

    # # Empty Prompt
    # answer_object = generate_openai_gpt_response("")
    #
    # if answer_object is not None:
    #     dump_json(answer_object.model_dump(), "Empty prompt")
    #     llm_response_inspector(answer_object)
    # else:
    #     logger.error("No response returned")

    # # Wrong API Key
    # global openai_client
    # openai_client = OpenAI(api_key="wrong_key")
    # answer_object = generate_openai_gpt_response("")
    #
    # if answer_object is not None:
    #     dump_json(answer_object.model_dump(), "Empty prompt")
    #     llm_response_inspector(answer_object)
    # else:
    #     logger.error("No response returned")

    # # Missing API Key
    # global openai_client
    # try:
    #     openai_client = OpenAI(api_key=None)
    # except Exception:
    #     logger.exception("Exception raised: \n")
    # answer_object = generate_openai_gpt_response("")
    #
    # if answer_object is not None:
    #     dump_json(answer_object.model_dump(), "Empty prompt")
    #     llm_response_inspector(answer_object)
    # else:
    #     logger.error("No response returned")

    # # Invalid parameter type
    # try:
    #     response = openai_client.responses.create(
    #         model="gpt-5.4-mini",
    #         input="Explain global warming",
    #         max_output_tokens="200",
    #         temperature=0.5
    #     )
    #
    #     if response is not None:
    #         logger.info("Response created successfully")
    #         dump_json(response.model_dump(), "Invalid parameter type")
    # except Exception as e:
    #     logger.error("Error %s", e)
    #     return None

    # # Invalid Enum Type
    # try:
    #     response = openai_client.responses.create(
    #         model="gpt-5.4-mini",
    #         input="Explain global warming",
    #         max_output_tokens=200,
    #         temperature=33.5
    #     )
    #
    #     if response is not None:
    #         logger.info("Response created successfully")
    #         dump_json(response.model_dump(), "Invalid enum type")
    # except Exception as e:
    #     logger.error("Error %s", e)
    #     return None

    # # Context Window Exceeded
    # try:
    #     input = "hello " * 220000
    #     response = openai_client.responses.create(
    #         model="gpt-5.4-mini",
    #         input=input,
    #         max_output_tokens=200,
    #         temperature=1
    #     )
    #
    #     if response is not None:
    #         logger.info(f"Response created successfully: {response.output_text}")
    #         dump_json(response.model_dump(), "Context window exceeded")
    # except Exception as e:
    #     logger.error("Error %s", e)
    #     return None

    # Invalid input format
    try:
        input = {"text": "hello"}
        response = openai_client.responses.create(
            model="gpt-5.4-mini",
            input=input,
            max_output_tokens=200,
            temperature=1
        )

        if response is not None:
            logger.info(f"Response created successfully: {response.output_text}")
            dump_json(response.model_dump(), "Invalid input format")
    except Exception as e:
        logger.error("Error %s", e)
        return None


if __name__ == "__main__":
    llm_response_orchestrator()