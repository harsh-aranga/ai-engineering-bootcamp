"""
This script corresponds to Day 1-2->Day 2->Experiments->
Create a graph with branching: Node A → (if condition) → Node B or Node C
Use state to track which branch was taken
Try: Input determines the branch (e.g., "positive" goes to B, "negative" goes to C)
Visualize your graph (LangGraph has built-in visualization)
"""
from operator import add

from langgraph.graph import StateGraph, START, END
from typing import TypedDict

from typing_extensions import Annotated

from common.logger import get_logger

logger = get_logger(__file__)


class State(TypedDict):
    answer: str
    message: str
    steps: Annotated[list[str], add]



def node_1(state: State) -> dict:
    logger.info("ENTERING NODE 1")
    answer = input("How do you want to greet the guest? Available Options: ['positive', 'negative'] => ")
    logger.info("EXITING NODE 1")
    return {
        "answer": answer,
        "steps": ["Reached Node 1"]
    }


def node_2(state: State) -> dict:
    logger.info("ENTERING NODE 2")
    logger.info("EXITING NODE 2")
    return {
        "message": "Welcome to my home, guest",
        "steps": ["Reached Node 2"]
    }


def node_3(state: State) -> dict:
    logger.info("ENTERING NODE 3")
    logger.info("EXITING NODE 3")
    return {
        "message": "Get going before I call the cops, guest",
        "steps": ["Reached Node 3"]
    }


def node_4(state: State) -> dict:
    logger.info("ENTERING NODE 4")
    logger.info("EXITING NODE 4")
    return {
        "message": "I have no idea what to do with you guest.",
        "steps": ["Reached Node 4"]
    }


def router(state: State) -> str:
    logger.info("ENTERING ROUTER")
    logger.info("EXITING ROUTER")
    if state["answer"] == "positive":
        return "node_2"
    elif state["answer"] == "negative":
        return "node_3"
    else:
        return "node_4"

graph = StateGraph(state_schema=State)
graph.add_node("node_1", node_1)
graph.add_node("node_2", node_2)
graph.add_node("node_3", node_3)
graph.add_node("node_4", node_4)

graph.add_edge(START, "node_1")
graph.add_conditional_edges(
    "node_1",
    router,
    {
        "node_2": "node_2",
        "node_3": "node_3",
        "node_4": "node_4"
    }
)
graph.add_edge("node_2", END)
graph.add_edge("node_3", END)
graph.add_edge("node_4", END)

app = graph.compile()
logger.info("\n" + app.get_graph().draw_mermaid())

result = app.invoke({"answer": "", "message": "", "steps":[]})

logger.info(f"Final result: {result}")