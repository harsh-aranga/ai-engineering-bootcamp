"""
This script corresponds to Day 5-6->Day 2->Mini Challenge->
Design and implement 4 tools for a "Personal Assistant" agent:

Calendar tool: Check schedule, add events
Web search tool: Search the web (simulate with a mock)
Note-taking tool: Save and retrieve notes
Calculator tool: Perform calculations
For each tool, provide:

Well-designed function schema (name, description, parameters)
Implementation (can be simple/mocked)
At least 2 test cases showing correct usage
At least 1 test case showing how the model might misuse it and how your design prevents it
Success Criteria:

All 4 tools have clear, specific names (verbs preferred)
Descriptions explain WHAT it does + WHEN to use it + WHAT it returns
Parameters have types, descriptions, and constraints where appropriate
Return values are structured (not just strings) with success/error indicators
Each tool handles at least one error case (e.g., calendar event in the past, note not found)
Tools are testable independently of the agent
Documentation: Someone else could use these tools from the schema alone
"""
from datetime import datetime
import json
import random
from typing import Literal, Any, Iterable, Optional

from openai import OpenAI, RateLimitError, APIConnectionError, BadRequestError, AuthenticationError, APIError
from openai.types.responses import Response, FunctionToolParam, ResponseFunctionToolCall
from pydantic import BaseModel, Field, ConfigDict

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")

openai_client = OpenAI(api_key=open_ai_key)

MAX_LLM_ITERATION_LIMIT = 5

class Calendar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title:str = Field(description="The title for the calendar event. Should be short and descriptive. "
                                  "Cannot be longer than 10 words")
    start_datetime: str = Field(description="Start date and time of the event. "
                                            "Should follow the format strictly: YYYY-MM-DDTHH:MM:SS")
    end_datetime: str = Field(description="End date and time of the event. S"
                                          "hould follow the format strictly: YYYY-MM-DDTHH:MM:SS")

class WebSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search_query:str = Field(description="The query to search the web for. Must not be null or empty")

class NoteTakerSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title:str = Field(description="The title for the note. Should be short and descriptive. "
                                  "Cannot be longer than 10 words. Cannot be empty or null")
    content:str = Field(description="The content of the notes.")

class NoteTakerRetrieve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query:Optional[str] = Field(description="The query based on which the notes will be retrieved. "
                                  "Can contain title or parts of content. If empty, all notes will be retrieved")

class Calculator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    num_1:int = Field(description="The first number on which the operation is to performed")
    num_2: int = Field(description="The second number on which the operation is to performed")
    operator:Literal["add", "sub", "mul", "div"] = Field(description="The mathematical operation to be performed.")

tool_calendar = {
    "type": "function",
    "name": "create_calendar_event",
    "description": "Creates calendar events as requested. Will return success message if event scheduled. "
                   "If conflict, will return conflict message and request a new timing. "
                   "Use it when you are asked to schedule an event or meeting",
    "parameters": Calendar.model_json_schema(),
    "strict": True
}

tool_web_search = {
    "type": "function",
    "name": "web_search",
    "description": "Searches the web for given query and then returns them as json documents. "
                   "Use it when you are asked to search the web or fetch latest data",
    "parameters": WebSearch.model_json_schema(),
    "strict": True
}

tool_note_taker_save = {
    "type": "function",
    "name": "note_taker_save",
    "description": "Saves notes to persistent storage. Returns success message when notes are saved."
                   " Use it when asked to save notes or store notes",
    "parameters": NoteTakerSave.model_json_schema(),
    "strict": True
}

tool_note_taker_retrieve = {
    "type": "function",
    "name": "note_taker_retrieve",
    "description": "Retrieves saved notes from persistent storage. Returns notes that match query."
                   "If no query sent, then returns all notes. Use it when asked to retrieve notes",
    "parameters": NoteTakerRetrieve.model_json_schema(),
    "strict": True
}

tool_calculator = {
    "type": "function",
    "name": "calculator",
    "description": "Performs mathematical operations on the two numbers provided from the allowed set of operations."
                   "Returns the result of the mathematical operation"
                   "Use it when you are asked to perform mathematical calculations of addition, subtraction, multiplication and division",
    "parameters": Calculator.model_json_schema(),
    "strict": True
}


import random

def create_calendar_event(title: str, start_datetime: str, end_datetime: str) -> dict:
    """Mock calendar event creation."""
    roll = random.random()
    if roll > 0.8:
        return {"status": "error", "message": f"Cannot schedule event in the past: {start_datetime}"}
    if roll > 0.6:
        return {"status": "conflict", "message": f"Conflict at {start_datetime}. Suggested time: 2026-04-08T14:00:00"}
    return {"status": "success", "event_id": f"evt_{random.randint(1000,9999)}", "message": f"'{title}' scheduled"}


def web_search(search_query: str) -> dict:
    """Mock web search."""
    if random.random() > 0.85:
        return {"status": "error", "message": "Search service temporarily unavailable. Try again later."}
    return {
        "status": "success",
        "results": [
            {"title": f"Result 1 for '{search_query}'", "url": "https://example.com/1", "snippet": "Lorem ipsum..."},
            {"title": f"Result 2 for '{search_query}'", "url": "https://example.com/2", "snippet": "Dolor sit amet..."},
        ]
    }


def note_taker_save(title: str, content: str) -> dict:
    """Mock note saving."""
    if random.random() > 0.85:
        return {"status": "error", "message": "Storage quota exceeded. Delete old notes and try again."}
    return {"status": "success", "note_id": f"note_{random.randint(1000,9999)}", "message": f"Note '{title}' saved"}


def note_taker_retrieve(query: Optional[str] = None) -> dict:
    """Mock note retrieval."""
    if random.random() > 0.85:
        return {"status": "error", "message": f"No notes found matching '{query}'"}
    if not query:
        return {"status": "success", "notes": [{"title": "Meeting notes", "content": "Discussed Q2 plans"}]}
    return {"status": "success", "notes": [{"title": f"Note matching '{query}'", "content": "Sample content..."}]}


def calculator(num_1: int, num_2: int, operator: str) -> dict:
    """Mock calculator."""
    if operator == "div" and num_2 == 0:
        return {"status": "error", "message": "Division by zero is not allowed"}
    ops = {"add": num_1 + num_2, "sub": num_1 - num_2, "mul": num_1 * num_2, "div": num_1 / num_2}
    return {"status": "success", "result": ops[operator]}

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
def process_function_call(item:ResponseFunctionToolCall) -> dict | str:
    try:
        if item.name == "create_calendar_event":
            args = json.loads(item.arguments)
            return create_calendar_event(**args)
        elif item.name == "web_search":
            args = json.loads(item.arguments)
            return web_search(**args)
        elif item.name == "note_taker_save":
            args = json.loads(item.arguments)
            return note_taker_save(**args)
        elif item.name == "note_taker_retrieve":
            args = json.loads(item.arguments)
            return note_taker_retrieve(**args)
        elif item.name == "calculator":
            args = json.loads(item.arguments)
            return calculator(**args)
        else:
            logger.info("Invalid function name")
            return "This function does not exist."
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
    tools = [tool_calendar, tool_web_search, tool_calculator, tool_note_taker_save, tool_note_taker_retrieve]
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
                        "output": json.dumps(tool_response)
                    }
                ]
                previous_response_id = response.id
                logger.info(f"Tool Response: {tool_response}")
                logger.info(f"Prompt: {prompt}")
            elif item.type == "message":
                dump_json(item.model_dump(), "Final response from LLM")
                logger.info(f"Final Response for query <<{org_prompt}>>: {response.output_text}")
                should_call_llm = False
                break
            else:
                logger.warning(f"Invalid Output Type from LLM. Printing response object")
                dump_json(response.model_dump(), "Invalid Output Type")
                logger.info(f"Output item: {item.model_dump()}")
                should_call_llm = False
                break

if __name__ == "__main__":
    # tool_call_orchestrator("what is 2 + 2?")
    # tool_call_orchestrator("Schedule an event 'Buy groceries' on 26th of April, 2026, 3:00 PM to 4:00 PM")
    # tool_call_orchestrator("Search the latest data for langchain docs")
    # tool_call_orchestrator("Save notes for Title: To do list for Sunday, Content: Buy vegetables, clean house, fight crimes, save gotham city")
    # tool_call_orchestrator("Retrieve notes")
    # tool_call_orchestrator("what is 2 div 0")
    # tool_call_orchestrator("What a sunny day it is? Check the tools which fetch me what the temp is and fetch it")
    tool_call_orchestrator("Send an email to john@example.com")