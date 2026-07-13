from typing import Any, Dict, List

import openai

from agents.base import AgentBase, build_rehearsal_graph


def _tool(name: str, description: str, schema: dict) -> Any:
    if hasattr(openai, "Tool"):
        return openai.Tool(name=name, description=description, parameters=schema)
    return {
        "name": name,
        "description": description,
        "parameters": schema,
    }


class LoanAgent(AgentBase):
    name = "Loan-Advisor"
    description = "Evaluates loan capacity, DSCR, collateral gaps, and required documentation."

    tools = [
        _tool(
            "retrieve_documents",
            "Search the knowledge base for relevant documents.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        ),
        _tool(
            "run_financial_engine",
            "Compute ratios, DSCR, and health score.",
            {"type": "object", "properties": {}, "required": []},
        ),
        _tool(
            "run_collateral_assessment",
            "Assess existing collateral and compute the gap to meet a target DSCR.",
            {"type": "object", "properties": {}, "required": []},
        ),
        _tool(
            "export_report",
            "Generate a loan-readiness PDF report.",
            {
                "type": "object",
                "properties": {
                    "include_collateral": {"type": "boolean"},
                    "include_actions": {"type": "boolean"},
                },
                "required": [],
            },
        ),
    ]

    def __init__(self, client_id: str, user_message: str):
        super().__init__(client_id=client_id, user_message=user_message)
        self._latest_snapshot: Dict[str, Any] = {}
        self._latest_actions: List[Dict[str, Any]] = []

    def system_prompt(self) -> str:
        return (
            "You are a senior loan-officer advisor.\n"
            "Duties:\n"
            "1) Compute DSCR, cash-flow runway, and working-capital coverage.\n"
            "2) Identify missing SBA 7(a) documentation.\n"
            "3) Use run_collateral_assessment to estimate collateral needed for DSCR 1.25x.\n"
            "4) Return final JSON payload that matches the declared schema.\n"
            "5) Export report on demand.\n"
            "Use only deterministic outputs and retrieved documents."
        )

    def final_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "snapshot": {"type": "object"},
                "actions": {"type": "array"},
                "disclaimer": {"type": "string"},
            },
            "required": ["snapshot", "actions", "disclaimer"],
        }

    async def _dispatch_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name == "retrieve_documents":
            from tools.retriever import DocumentRetriever

            retriever = DocumentRetriever(self.client_id)
            docs = retriever.retrieve(query=args["query"], k=int(args.get("k", 5)))
            return {"documents": docs}

        if name == "run_financial_engine":
            from tools.financial_engine import FinancialEngine

            engine = FinancialEngine(self.client_id)
            ratios, confidence = engine.compute_ratios()
            result = {
                "ratios": ratios,
                "confidence": round(float(confidence), 4),
            }
            self._latest_snapshot = result
            return result

        if name == "run_collateral_assessment":
            from tools.financial_engine import FinancialEngine

            # Placeholder: replace with real collateral register integration.
            engine = FinancialEngine(self.client_id)
            features = engine._load_features()
            ebitda = float(features.get("ebitda_ttm", 0.0))
            debt_service = float(features.get("debt_service", 0.0))
            target_dscr = 1.25
            required_debt = ebitda / target_dscr if target_dscr > 0 else 0.0
            gap = max(0.0, required_debt - debt_service)
            existing = 500_000
            assessment = {
                "existing_collateral_usd": existing,
                "required_debt_capacity_usd": round(required_debt, 2),
                "collateral_gap_usd": round(gap, 2),
            }
            self._latest_snapshot["collateral_assessment"] = assessment
            return assessment

        if name == "export_report":
            from tools.exporter import generate_report

            url = generate_report(
                self.client_id,
                args["snapshot"],
                args.get("actions", []),
            )
            return {"download_url": url}

        raise ValueError(f"Unknown tool {name}")


def build_graph(checkpointer=None):
    return build_rehearsal_graph("sba_underwriter", checkpointer=checkpointer)


def create_graph():
    return build_graph()