"""
This script corresponds to Day 3-4->Experiments->
***************Day 3***************
Take your Week 3 tools (calculator, notes, time, etc.)
Define them as LangChain tools (using @tool decorator or Tool class)
Create a simple agent graph with: agent node → tool node → back to agent
Run a query that requires a tool — verify the loop works
***************Day 4***************
Rebuild your Week 3 agent in LangGraph:
Success Criteria:

Graph structure: agent node → conditional → tool node → agent node (loop)
Correctly identifies when to end (no more tool calls)
All 4 tools from Week 3 work
Multi-step tasks work (requires multiple tool calls)
Messages state tracks full conversation (human + AI + tool results)
Can visualize the graph (use graph.get_graph().draw_mermaid())
Handles tool errors gracefully
Compared: Is behavior identical to your Week 3 raw agent?
"""

import json
import random
from typing import Literal, Any, Iterable, Optional

from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field, ConfigDict, SecretStr

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")

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
    num_1:float = Field(description="The first number on which the operation is to performed")
    num_2: float = Field(description="The second number on which the operation is to performed")
    operator:Literal["add", "sub", "mul", "div"] = Field(description="The mathematical operation to be performed.")


@tool(args_schema=Calendar)
def create_calendar_event(title: str, start_datetime: str, end_datetime: str) -> dict:
    """Mock calendar event creation."""
    roll = random.random()
    if roll > 0.8:
        return {"status": "error", "message": f"Cannot schedule event in the past: {start_datetime}"}
    if roll > 0.6:
        return {"status": "conflict", "message": f"Conflict at {start_datetime}. Suggested time: 2026-04-08T14:00:00"}
    return {"status": "success", "event_id": f"evt_{random.randint(1000,9999)}", "message": f"'{title}' scheduled"}


@tool(args_schema=WebSearch)
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


@tool(args_schema=NoteTakerSave)
def note_taker_save(title: str, content: str) -> dict:
    """Mock note saving."""
    if random.random() > 0.85:
        return {"status": "error", "message": "Storage quota exceeded. Delete old notes and try again."}
    return {"status": "success", "note_id": f"note_{random.randint(1000,9999)}", "message": f"Note '{title}' saved"}


@tool(args_schema=NoteTakerRetrieve)
def note_taker_retrieve(query: Optional[str] = None) -> dict:
    """Mock note retrieval."""
    if random.random() > 0.85:
        return {"status": "error", "message": f"No notes found matching '{query}'"}
    if not query:
        return {"status": "success", "notes": [{"title": "Meeting notes", "content": "Discussed Q2 plans"}]}
    return {"status": "success", "notes": [{"title": f"Note matching '{query}'", "content": "Sample content..."}]}


@tool(args_schema=Calculator)
def calculator(num_1: float, num_2: float, operator: str) -> dict:
    """Mock calculator."""
    if operator == "div" and num_2 == 0:
        return {"status": "error", "message": "Division by zero is not allowed"}
    ops = {"add": num_1 + num_2, "sub": num_1 - num_2, "mul": num_1 * num_2, "div": num_1 / num_2}
    return {"status": "success", "result": ops[operator]}


def create_agent_graph(tools: list) -> CompiledStateGraph:
    """
    Creates a LangGraph agent with:
    - Agent node (LLM with tool access)
    - Tool execution node
    - Conditional edge: if tool call → tool node, else → end
    - Loop back from tool node to agent node

    Returns compiled graph.
    """

    llm = ChatOpenAI(api_key=SecretStr(open_ai_key), model="gpt-5.4-mini")
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: MessagesState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    builder = StateGraph(MessagesState)

    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools=tools, handle_tool_errors=True))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")

    graph = builder.compile()

    return graph


tools = [calculator, create_calendar_event, note_taker_save, note_taker_retrieve, web_search]
graph = create_agent_graph(tools)

logger.info(graph.get_graph().draw_mermaid())

result = graph.invoke({
    "messages": [HumanMessage(content="What's 15% of 230? Once that result is obtained, "
                                      "create a note titled 'My Calculations' and save note with the math operation result'."
                                      "Once the save is successful, create a calendar event 'Check Notes' on 23rd April, 2026 from 5PM to 6PM."
                                      "Finally make a web search on eval python function and give me the results")]
})

for msg in result["messages"]:
    logger.info(f"{msg}")