"""
AgentBase using the OpenAI Agents SDK (openai-agents package).

The SDK pattern:
  - Tools are decorated with @function_tool
  - An Agent is constructed with name, instructions, tools, and model
  - Runner.run(agent, messages) executes the tool loop
  - The loop runs until the agent emits a final text response

Each concrete agent subclass provides:
  - system_prompt()     — the agent's instructions
  - final_schema()      — JSON schema the response must match
  - _make_tools()       — returns a list of @function_tool decorated callables
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

# Import from our local sub-modules (not the openai-agents SDK)
from agent import llm
from agent.state import Persona, RehearsalState


# No collision: project package is 'agent/', SDK package is 'agents'. Direct import.
def _import_sdk():
    """Return (Agent, Runner, function_tool, set_default_openai_key) from the openai-agents SDK."""
    from agents import Agent, Runner, function_tool, set_default_openai_key
    return Agent, Runner, function_tool, set_default_openai_key


def get_checkpointer(thread_id: str | None = None):
    """
    Return a LangGraph checkpointer.

    If POSTGRES_DSN is set in the environment, returns a Postgres-backed
    checkpointer so rehearsal state survives across sessions and API restarts.
    Falls back to MemorySaver (in-process, lost on restart) when no DSN is set.

    Usage:
        checkpointer = get_checkpointer()
        graph = build_rehearsal_graph("buyer", checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id or str(uuid.uuid4())}}
    """
    dsn = os.environ.get("POSTGRES_DSN", "")
    if dsn:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            import psycopg
            conn = psycopg.connect(dsn, autocommit=True)
            saver = PostgresSaver(conn)
            saver.setup()   # creates checkpoint tables if they don't exist
            return saver
        except Exception as exc:
            import logging
            logging.getLogger("advisory").warning(
                "Postgres checkpointer unavailable (%s) — falling back to MemorySaver", exc
            )
    return MemorySaver()



# ── LangGraph rehearsal graph (shared by all agents) ─────────────────────────

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


# ── AgentBase using the OpenAI Agents SDK ─────────────────────────────────────

class AgentBase(ABC):
    """
    Base class for specialist agents using the openai-agents SDK.

    The SDK pattern:
        agent = Agent(name=..., instructions=..., tools=[...], model=...)
        result = await Runner.run(agent, messages)

    If the SDK is not available (no OPENAI_API_KEY or import fails),
    _fallback_response() returns a schema-compatible deterministic payload.
    """

    name: str
    description: str

    def __init__(self, client_id: str, user_message: str):
        self.client_id = client_id
        self.user_message = user_message

    @abstractmethod
    def system_prompt(self) -> str:
        """Each concrete agent provides its own system prompt."""

    @abstractmethod
    def final_schema(self) -> Dict[str, Any]:
        """JSON schema the final response must match."""

    @abstractmethod
    def _make_tools(self) -> List[Any]:
        """Return a list of @function_tool decorated callables for this agent."""

    def _fallback_response(self) -> Dict[str, Any]:
        """Schema-compatible deterministic payload when the Agents SDK is unavailable."""
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
                        "title": "Set OPENAI_API_KEY",
                        "detail": (
                            "Add a valid OPENAI_API_KEY to your .env file to enable "
                            "the full agent loop."
                        ),
                    }
                ],
                "disclaimer": "This is educational guidance, not financial advice.",
            }

        if {"explanation", "evidence", "confidence", "disclaimer"}.issubset(props.keys()):
            return {
                "explanation": (
                    "Running in compatibility fallback mode. "
                    "Set OPENAI_API_KEY in .env to enable full advisory reasoning."
                ),
                "evidence": [],
                "confidence": 0.25,
                "disclaimer": "This is educational guidance, not financial advice.",
            }

        return {k: None for k in schema.get("required", [])}

    async def run(self) -> Dict[str, Any]:
        """Run the agent loop, returning a validated response dict."""
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key or "YOUR_KEY" in api_key:
            return self._fallback_response()

        try:
            Agent, Runner, function_tool, set_default_openai_key = _import_sdk()
            set_default_openai_key(api_key)
        except Exception:
            return self._fallback_response()

        tools = self._make_tools()
        agent = Agent(
            name=self.name,
            instructions=(
                self.system_prompt()
                + "\n\nReturn your final answer as a JSON object matching this schema:\n"
                + json.dumps(self.final_schema(), indent=2)
            ),
            tools=tools,
            model="gpt-4o-mini",
        )

        try:
            result = await Runner.run(agent, self.user_message)
            text = result.final_output
            if isinstance(text, str):
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end > start:
                    return json.loads(text[start:end])
            if isinstance(text, dict):
                return text
            # Model responded but didn't return JSON — return raw text wrapped
            return {"snapshot": {"response": str(text)}, "actions": [], "disclaimer": "This is educational guidance, not financial advice."}
        except Exception as exc:
            import logging
            logging.getLogger("advisory").error("Runner.run failed: %s", exc, exc_info=True)
            raise
