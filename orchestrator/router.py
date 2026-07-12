from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph


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