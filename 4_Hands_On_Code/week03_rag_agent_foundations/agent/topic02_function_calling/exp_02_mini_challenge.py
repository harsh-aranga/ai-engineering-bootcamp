"""
This script corresponds to Day 3-4->Day 2->Hour 2->Mini Challenge->
Build a tool_calling_loop() function:
Success Criteria:

Correctly parses function call requests from model response
Executes the right function with correct arguments
Sends tool results back in correct format
Handles multi-step: "What's 2+3, then multiply by 4?" (requires 2 tool calls)
Stops when model gives final response (no tool call)
Respects max_iterations (doesn't loop forever)
Handles tool execution errors gracefully (tool throws exception)
Tested with at least 3 different queries requiring different tools
"""
from datetime import datetime
import json
from typing import Literal, Any, Iterable

from openai import OpenAI, RateLimitError, APIConnectionError, BadRequestError, AuthenticationError, APIError
from openai.types.responses import Response, FunctionToolParam, ResponseFunctionToolCall
from pydantic import BaseModel, Field, ConfigDict
from torchvision.transforms.v2 import query_chw

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")

openai_client = OpenAI(api_key=open_ai_key)

MAX_LLM_ITERATION_LIMIT = 5

class Add(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number_1:int = Field(description="First number in to be added")
    number_2:int = Field(description="Second number to be added")

class Multiply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number_1:int = Field(description="First number in to be multiplied")
    number_2:int = Field(description="Second number to be multiplied")

class GetDateTime(BaseModel):
    model_config = ConfigDict(extra="forbid")

tool_1 = {
    "type": "function",
    "name": "add_two_numbers",
    "description": "Add the two numbers passed to it and return the sum as response",
    "parameters": Add.model_json_schema(),
    "strict": True
}

tool_2 = {
    "type": "function",
    "name": "multiply_two_numbers",
    "description": "Multiply the two numbers passed to it and return the product as response",
    "parameters": Multiply.model_json_schema(),
    "strict": True
}

tool_3 = {
    "type": "function",
    "name": "get_current_date_time",
    "description": "Returns the current date and time formatted to '%B %d, %Y at %I:%M %p'",
    "parameters": GetDateTime.model_json_schema(),
    "strict": True
}

def add_two_numbers(number_1:int, number_2:int) -> str:
    """
    Adds two numbers
    :param number_1:
    :param number_2:
    :return:
    """
    return str(number_1 + number_2)

def multiply_two_numbers(number_1:int, number_2:int) -> str:
    """
    Multiplies two numbers
    :param number_1:
    :param number_2:
    :return:
    """
    return str(number_1 * number_2)

def get_current_date_time() -> str:
    """
    Returns current date and time
    :return:
    """
    return datetime.now().strftime("%B %d, %Y at %I:%M %p")

def generate_openai_gpt_tool_calling(prompt: str | list[dict[str, Any]], tools:Iterable[FunctionToolParam] | None = None,
                                     model: str = "gpt-5.4-mini",
                                     previous_response_id:str | None = None ) -> Response | None:
    """
    Takes a prompt and model. Returns the response
    :param call_id:
    :param previous_response_id:
    :param tools: Tools used
    :param prompt: The prompt that user sends
    :param model: The gpt model that will process the prompt. Defaults to gpt-5.4-mini
    :return: openai.resources.responses.Response
    """

    try:
        response = openai_client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=500,
            temperature=0.5,
            tools=tools if tools else None,
            parallel_tool_calls=False if tools else None,
            tool_choice="auto" if tools else "none",
            previous_response_id=previous_response_id if previous_response_id else None
        )

        if response is not None:
            logger.info("Response created successfully")
            return response

    except RateLimitError as e:
        logger.exception("Rate limit hit")
    except APIConnectionError as e:
        logger.exception("Network/API connection issue")
    except BadRequestError as e:
        logger.exception("Bad request: prompt/model/params issue")
    except AuthenticationError as e:
        logger.exception("Invalid API key")
    except APIError as e:
        logger.exception("OpenAI server/API error")
    except Exception as e:
        logger.exception("Unexpected failure")

    return None

# noinspection PyTypeChecker
def process_function_call(item:ResponseFunctionToolCall) -> str | int:
    try:
        if item.name == "add_two_numbers":
            args = json.loads(item.arguments)
            return add_two_numbers(**args)
        elif item.name == "multiply_two_numbers":
            args = json.loads(item.arguments)
            return multiply_two_numbers(**args)
        elif item.name == "get_current_date_time":
            return get_current_date_time()
        else:
            logger.info("Invalid function name")
            return "This function does not exist. Function calls available ['add_two_numbers', 'multiply_two_numbers', 'get_current_date_time']"
    except Exception as e:
        logger.exception("Error during process function call")
        return f"Error executing {item.name}: {str(e)}"

# noinspection PyTypeChecker
def tool_call_orchestrator(prompt: str, model: str = "gpt-5.4-mini",) -> None:
    """
    Orchestrator for this script
    :param prompt:
    :param model:
    :return:
    """
    tools = [tool_1, tool_2, tool_3]
    org_prompt = prompt
    previous_response_id = None
    count = 0
    should_call_llm = True
    while should_call_llm:
        response = generate_openai_gpt_tool_calling(prompt, tools=tools, previous_response_id=previous_response_id)
        dump_json(response.model_dump(), "Response from LLM")
        count += 1
        logger.info(f"Current iteration: {count}")
        for item in response.output:
            if count > MAX_LLM_ITERATION_LIMIT:
                logger.warning(f"Max iteration limit reached. Total calls to llm exceeds {MAX_LLM_ITERATION_LIMIT}")
                should_call_llm = False
                break
            if item.type == "function_call":
                dump_json(item.model_dump(), f"Function Call Output for Function: {item.name}")
                logger.info(f"LLM proposed a function call for function {item.name}")
                tool_response = process_function_call(item)
                prompt = [
                    {
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": tool_response
                    }
                ]
                previous_response_id = response.id
                logger.info(f"Tool Response: {tool_response}")
                logger.info(f"Prompt: {prompt}")
            elif item.type == "message":
                dump_json(item.model_dump(), "Final response from LLM")
                logger.info(f"Final Response for query {org_prompt}: {response.output_text}")
                should_call_llm = False
                break
            else:
                logger.warning(f"Invalid Output Type from LLM. Printing response object")
                dump_json(response.model_dump(), "Invalid Output Type")
                logger.info(f"Output item: {item.model_dump()}")
                should_call_llm = False
                break

if __name__ == "__main__":
    # tool_call_orchestrator("What is 2 + 2?")

    # tool_call_orchestrator("What is 2 + 2? Also multiply that number with 4 and tell what the product is.")

    tool_call_orchestrator("What is 2 + 2? Also multiply that number with 4 and tell what the product is. Then tell the current datetime too")