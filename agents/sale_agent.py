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


class SaleAgent(AgentBase):
    name = "Sale-Advisor"
    description = "Advises owners on sale readiness, valuation drivers, and buyer concerns."

    tools = [
        _tool(
            "retrieve_documents",
            "Search the knowledge base for documents relevant to the user query.",
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
            "Compute deterministic ratios, health score and cash-flow forecast.",
            {"type": "object", "properties": {}, "required": []},
        ),
        _tool(
            "run_valuation",
            "Run a 5-year Monte-Carlo DCF valuation using EBITDA and growth.",
            {"type": "object", "properties": {}, "required": []},
        ),
        _tool(
            "export_report",
            "Generate a PDF advisory report.",
            {
                "type": "object",
                "properties": {
                    "include_valuation": {"type": "boolean"},
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
            "You are a senior M&A advisor.\n"
            "Workflow:\n"
            "1) Explain current financial health from run_financial_engine.\n"
            "2) Identify top-3 valuation drivers and top-3 buyer concerns.\n"
            "3) Quantify driver impact on enterprise value using run_valuation baseline.\n"
            "4) Return a final JSON payload matching the declared schema.\n"
            "5) If asked for a report, call export_report.\n"
            "Use only deterministic outputs and retrieved documents. Never fabricate numbers."
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
            ratios, health = engine.compute_ratios()
            forecast_df, confidence = engine.forecast_cashflow(months=12)
            forecast = [
                {
                    "date": str(r["date"]),
                    "fcff": round(float(r["fcff"]), 2),
                }
                for _, r in forecast_df.iterrows()
            ]
            result = {
                "ratios": ratios,
                "confidence": round(float(health), 4),
                "forecast": forecast,
                "forecast_confidence": round(float(confidence), 4),
            }
            self._latest_snapshot = result
            return result

        if name == "run_valuation":
            from tools.financial_engine import FinancialEngine
            from tools.valuation import run_valuation

            engine = FinancialEngine(self.client_id)
            features = engine._load_features()
            valuation = run_valuation(
                float(features.get("ebitda_ttm", 0.0)),
                float(features.get("revenue_growth_yoy", 0.0)),
            )
            return {"valuation": valuation, "confidence": 0.9}

        if name == "export_report":
            from tools.exporter import generate_report

            url = generate_report(
                self.client_id,
                args["snapshot"],
                args.get("actions", []),
            )
            return {"download_url": url}

        return {"error": f"Unknown tool: {name}"}


def build_graph(checkpointer=None):
    return build_rehearsal_graph("buyer", checkpointer=checkpointer)


def create_graph():
    return build_graph()