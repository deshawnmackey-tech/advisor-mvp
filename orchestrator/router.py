import os
import uuid
from datetime import datetime
from typing import Callable, Dict, Literal, TypedDict

import motor.motor_asyncio
from fastapi import HTTPException
from langgraph.graph import END, StateGraph

from agent.general_agent import GeneralAgent
from agent.investor_agent import InvestorAgent
from agent.loan_agent import LoanAgent
from agent.my_new_agent import MyNewAgent
from agent.sale_agent import SaleAgent


AGENT_REGISTRY: Dict[str, Callable[[str, str], object]] = {
    "sale": lambda client_id, msg: SaleAgent(client_id, msg),
    "loan": lambda client_id, msg: LoanAgent(client_id, msg),
    "investor": lambda client_id, msg: InvestorAgent(client_id, msg),
    "general": lambda client_id, msg: GeneralAgent(client_id, msg),
    "my_new_scenario": lambda client_id, msg: MyNewAgent(client_id, msg),
}

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(
    MONGO_URI,
    serverSelectionTimeoutMS=1000,
    connectTimeoutMS=1000,
    socketTimeoutMS=1000,
)
trace_coll = mongo_client.advisory.agent_traces


async def store_trace(trace_id: str, payload: dict) -> None:
    try:
        await trace_coll.insert_one(
            {
                "_id": trace_id,
                "timestamp": datetime.utcnow(),
                "payload": payload,
            }
        )
    except Exception:
        # Do not block API responses if tracing storage is unavailable.
        return


async def dispatch(
    client_id: str,
    scenario: str,
    user_message: str,
    rehearsal: bool = False,
) -> Dict:
    if scenario not in AGENT_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported scenario '{scenario}'. Choose from {list(AGENT_REGISTRY)}",
        )

    trace_id = str(uuid.uuid4())

    try:
        agent = AGENT_REGISTRY[scenario](client_id, user_message)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to instantiate agent: {exc}",
        ) from exc

    try:
        if rehearsal:
            result = {
                "snapshot": {"score": 75, "strengths": [], "weaknesses": []},
                "actions": [],
                "disclaimer": "This is a rehearsal stub - no real data.",
            }
        else:
            result = await agent.run()
    except Exception as exc:
        await store_trace(
            trace_id,
            {
                "scenario": scenario,
                "client_id": client_id,
                "user_message": user_message,
                "error": str(exc),
                "stage": "agent_execution",
            },
        )
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}") from exc

    await store_trace(
        trace_id,
        {
            "scenario": scenario,
            "client_id": client_id,
            "user_message": user_message,
            "result": result,
            "rehearsal": rehearsal,
        },
    )
    return {"payload": result, "trace_id": trace_id}


Persona = Literal["buyer", "sba_underwriter", "investor", "general"]


class OrchestratorState(TypedDict, total=False):
    business: dict
    requested_persona: Persona
    recommended_persona: Persona
    routing_reason: str


def route_persona(state: OrchestratorState) -> OrchestratorState:
    requested = state.get("requested_persona")
    if requested in {"buyer", "sba_underwriter", "investor", "general"}:
        state["recommended_persona"] = requested
        state["routing_reason"] = f"Explicitly routed to {requested}."
        return state

    business = state.get("business", {})
    documentation_pct = float(business.get("documentation_completeness_pct", 0) or 0)
    recurring_pct = float(business.get("recurring_revenue_pct", 0) or 0)
    revenue = float(business.get("annual_revenue", 0) or 0)

    if documentation_pct < 60:
        state["recommended_persona"] = "sba_underwriter"
        state["routing_reason"] = "Documentation readiness is weak, so underwriting risk should be tested first."
    elif recurring_pct >= 70 and revenue >= 5_000_000:
        state["recommended_persona"] = "investor"
        state["routing_reason"] = "Recurring revenue and scale are strong enough to pressure-test the investor case."
    elif revenue <= 1_000_000:
        state["recommended_persona"] = "general"
        state["routing_reason"] = "Business is still early enough that broad operational advisory is the best first pass."
    else:
        state["recommended_persona"] = "buyer"
        state["routing_reason"] = "Defaulting to buyer diligence as the broadest sale-readiness rehearsal."
    return state


def build_orchestrator_graph():
    graph = StateGraph(OrchestratorState)
    graph.add_node("route_persona", route_persona)
    graph.set_entry_point("route_persona")
    graph.add_edge("route_persona", END)
    return graph.compile()


def create_orchestrator_graph():
    return build_orchestrator_graph()