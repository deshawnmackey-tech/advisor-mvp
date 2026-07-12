from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from agents import llm
from agents.state import Persona, RehearsalState


def _default_persona(state: RehearsalState, persona: Persona) -> RehearsalState:
    if not state.get("persona"):
        state["persona"] = persona
    return state


def pick_finding(state: RehearsalState) -> RehearsalState:
    finding = state["findings"][state["idx"]]
    state["transcript"].append(
        {
            "speaker": "system",
            "text": (
                f"-- Finding {state['idx'] + 1}/{len(state['findings'])}: "
                f"{finding['metric']} ({finding['severity']}) --"
            ),
        }
    )
    return state


def ask_question(state: RehearsalState) -> RehearsalState:
    finding = state["findings"][state["idx"]]
    question = llm.ask_question(state["persona"], finding)
    state["current_question"] = question
    state["transcript"].append({"speaker": "persona", "text": question})
    return state


def get_customer_answer(state: RehearsalState) -> RehearsalState:
    answer = interrupt({"persona": state["persona"], "question": state["current_question"]})
    state["transcript"].append({"speaker": "customer", "text": answer})
    state["last_answer"] = answer
    return state


def evaluate_answer(state: RehearsalState) -> RehearsalState:
    finding = state["findings"][state["idx"]]
    answer = state["last_answer"]
    result = llm.evaluate_answer(state["persona"], finding, answer)

    if not result["resolved"]:
        state["flagged"].append(
            {
                "metric": finding["metric"],
                "note": result["note"],
                "fix": finding["fix_narrative"],
            }
        )
        state["transcript"].append({"speaker": "system", "text": f"FLAGGED: {result['note']}"})
    else:
        state["transcript"].append({"speaker": "system", "text": f"Resolved: {result['note']}"})
    return state


def advance(state: RehearsalState) -> RehearsalState:
    state["idx"] += 1
    state["done"] = state["idx"] >= len(state["findings"])
    return state


def route_after_advance(state: RehearsalState) -> str:
    return END if state["done"] else "pick_finding"


def build_rehearsal_graph(default_persona: Persona, checkpointer=None):
    def initialize_persona(state: RehearsalState) -> RehearsalState:
        return _default_persona(state, default_persona)

    graph = StateGraph(RehearsalState)
    graph.add_node("initialize_persona", initialize_persona)
    graph.add_node("pick_finding", pick_finding)
    graph.add_node("ask_question", ask_question)
    graph.add_node("get_customer_answer", get_customer_answer)
    graph.add_node("evaluate_answer", evaluate_answer)
    graph.add_node("advance", advance)

    graph.set_entry_point("initialize_persona")
    graph.add_edge("initialize_persona", "pick_finding")
    graph.add_edge("pick_finding", "ask_question")
    graph.add_edge("ask_question", "get_customer_answer")
    graph.add_edge("get_customer_answer", "evaluate_answer")
    graph.add_edge("evaluate_answer", "advance")
    graph.add_conditional_edges("advance", route_after_advance, {"pick_finding": "pick_finding", END: END})
    return graph.compile(checkpointer=checkpointer or MemorySaver())