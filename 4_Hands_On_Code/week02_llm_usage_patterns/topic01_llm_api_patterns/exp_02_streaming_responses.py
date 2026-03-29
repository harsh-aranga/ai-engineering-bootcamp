"""
This script corresponds to Day 1-2->Day 1->Hour 2->Experiment->
Implement basic streaming — print chunks as they arrive
"""

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

from openai import OpenAI

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key = open_ai_key)

def stream_openai_gpt_response(prompt: str, model: str = "gpt-5.4-mini") -> None:
    """
    Takes a prompt and model. Streams the response
    :param prompt: The prompt that user sends
    :param model: The gpt model that will process the prompt. Defaults to gpt-5.4-mini
    :return: None
    """

    try:
        stream = openai_client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=300,
            temperature=0.5,
            stream=True
        )

        if stream is not None:
            count = 0
            for event in stream:
                count += 1
                dump_json(event.model_dump(), f"{event.type} {count}")
                if event.type == "response.output_text.delta":
                    logger.info("%s", event.delta)
                    # print(event.delta, end="")
                elif event.type == "response.incomplete":
                    logger.info(f"Reason for exit: {event.response.incomplete_details.reason}")
    except Exception:
        logger.exception("Error during streaming response")
        return None

def llm_response_streaming_orchestrator() -> None:
    """
    Calls llm response streamer.
    :return: None
    """
    stream_openai_gpt_response("Write about climate change")

if __name__ == "__main__":
    llm_response_streaming_orchestrator()