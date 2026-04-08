"""
This script corresponds to Day 1-2->Day 1->Experiments->
Install: pip install langgraph langchain-openai
Create the simplest possible graph: one node that just returns "Hello"
Add a second node, connect them sequentially
Run the graph, see output
Add state: pass a message through both nodes, modify it in each
"""
from operator import add

from langgraph.graph import StateGraph, START, END
from typing import TypedDict

from typing_extensions import Annotated

from common.logger import get_logger

logger = get_logger(__file__)

class State(TypedDict):
    message: str
    steps: Annotated[list[str], add]


def step_one(state: State) -> State:
    return {
        "message": state["message"] + " Hello",
        "steps": ["In Graph One"]
    }


def step_two(state: State) -> State:
    return {
        "message": state["message"] + " World!",
        "steps": ["In Graph Two"]
    }


# noinspection PyTypeChecker
graph = StateGraph(state_schema=State)
graph.add_node("step_one", step_one)
graph.add_node("step_two", step_two)

graph.add_edge(START, "step_one")
graph.add_edge("step_one", "step_two")
graph.add_edge("step_two", END)

app = graph.compile()
result = app.invoke({"message": "", "steps":[]})

logger.info(result)