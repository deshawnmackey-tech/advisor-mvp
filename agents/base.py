import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import openai
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


class AgentBase(ABC):
    """Common logic for specialist agents using the OpenAI agent loop."""

    name: str
    description: str
    tools: List[Any]

    def __init__(self, client_id: str, user_message: str):
        self.client_id = client_id
        self.user_message = user_message
        self.history: List[Dict[str, Any]] = []
        self.agent = self._build_agent()

    @abstractmethod
    def system_prompt(self) -> str:
        """Each concrete agent provides its own system prompt."""

    @abstractmethod
    def final_schema(self) -> Dict[str, Any]:
        """JSON schema the LLM must obey for its final answer."""

    def _build_agent(self):
        if not hasattr(openai, "Agent"):
            return None
        return openai.Agent(
            name=self.name,
            description=self.description,
            instructions=self.system_prompt(),
            tools=self.tools,
            model="gpt-4o-mini",
            temperature=0.0,
        )

    def _fallback_response(self) -> Dict[str, Any]:
        """Return a schema-compatible deterministic payload when Agent API is unavailable."""
        schema = self.final_schema()
        props = schema.get("properties", {})

        if {"snapshot", "actions", "disclaimer"}.issubset(props.keys()):
            return {
                "snapshot": {
                    "mode": "compatibility_fallback",
                    "client_id": self.client_id,
                    "message": self.user_message,
                },
                "actions": [
                    {
                        "priority": "high",
                        "title": "Upgrade OpenAI SDK runtime",
                        "detail": "Install or pin an SDK/runtime that supports openai.Agent, or use rehearsal mode.",
                    }
                ],
                "disclaimer": (
                    "Returned by deterministic fallback because the installed openai package does not expose Agent API."
                ),
            }

        if {"explanation", "evidence", "confidence", "disclaimer"}.issubset(props.keys()):
            return {
                "explanation": (
                    "A deterministic compatibility fallback was used because the installed OpenAI SDK "
                    "does not expose Agent API in this environment."
                ),
                "evidence": [],
                "confidence": 0.25,
                "disclaimer": "Enable Agent API support to run full tool-driven advisory reasoning.",
            }

        required = schema.get("required", [])
        payload: Dict[str, Any] = {}
        for key in required:
            payload[key] = None
        return payload

    async def run(self) -> Dict[str, Any]:
        """Run until the agent emits a payload with type='final'."""
        if self.agent is None:
            return self._fallback_response()

        self.history.append({"role": "user", "content": self.user_message})

        while True:
            resp = await self.agent.run(messages=self.history, functions=self.tools)

            if resp.get("type") == "final":
                from pydantic import ValidationError, create_model

                schema = self.final_schema()
                model = create_model(
                    "TmpModel",
                    **{k: (Any, ...) for k in schema.get("properties", {}).keys()},
                )

                try:
                    validated = model(**resp["payload"])
                except ValidationError as e:
                    raise RuntimeError(f"Output validation error: {e}") from e

                return validated.model_dump()

            tool_name = resp["name"]
            tool_args = resp["arguments"]
            tool_result = await self._dispatch_tool(tool_name, tool_args)

            self.history.append(
                {
                    "role": "assistant",
                    "name": tool_name,
                    "content": json.dumps(tool_result),
                }
            )
            self.history.append({"role": "assistant", "content": "Tool result attached."})

    @abstractmethod
    async def _dispatch_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Map tool name to concrete implementation."""