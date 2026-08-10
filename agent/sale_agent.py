from typing import Any, Dict, List

from agent.base import AgentBase, build_rehearsal_graph


class SaleAgent(AgentBase):
    name = "Sale-Advisor"
    description = "Advises owners on sale readiness, valuation drivers, and buyer concerns."

    def __init__(self, client_id: str, user_message: str):
        super().__init__(client_id=client_id, user_message=user_message)
        self._latest_snapshot: Dict[str, Any] = {}

    def system_prompt(self) -> str:
        return (
            "You are a senior M&A advisor.\n"
            "IMPORTANT: You MUST call run_financial_engine first before answering. "
            "Do not answer from general knowledge — only use numbers returned by tools.\n"
            "Workflow:\n"
            "1) Call run_financial_engine to get DSCR, concentration, doc completeness, revenue, and EBITDA.\n"
            "2) Call run_valuation to get enterprise value range.\n"
            "3) Identify top-3 valuation drivers and top-3 buyer concerns from the actual data.\n"
            "4) Return a final JSON payload matching the declared schema.\n"
            "Use only tool outputs. Never fabricate numbers."
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

    def _make_tools(self) -> List[Any]:
        from agent.base import _import_sdk
        _, _, function_tool, _ = _import_sdk()

        client_id = self.client_id

        @function_tool
        def retrieve_documents(query: str, k: int = 5) -> dict:
            """Search the knowledge base for documents relevant to the user query."""
            from tools.retriever import DocumentRetriever
            retriever = DocumentRetriever(client_id)
            return {"documents": retriever.retrieve(query=query, k=k)}

        @function_tool
        def run_financial_engine() -> dict:
            """Compute deterministic ratios, health score and cash-flow forecast."""
            from tools.financial_engine import FinancialEngine
            engine = FinancialEngine(client_id)
            ratios, health = engine.compute_ratios()
            forecast_df, confidence = engine.forecast_cashflow(months=12)
            return {
                "ratios": ratios,
                "confidence": round(float(health), 4),
                "forecast": [{"date": str(r["date"]), "fcff": round(float(r["fcff"]), 2)}
                             for _, r in forecast_df.iterrows()],
                "forecast_confidence": round(float(confidence), 4),
            }

        @function_tool
        def run_valuation() -> dict:
            """Run a 5-year Monte-Carlo DCF valuation using EBITDA and growth."""
            from tools.financial_engine import FinancialEngine
            from tools.valuation import run_valuation as _run
            engine = FinancialEngine(client_id)
            features = engine._load_features()
            return {"valuation": _run(float(features.get("ebitda_ttm", 0.0)),
                                      float(features.get("revenue_growth_yoy", 0.0))),
                    "confidence": 0.9}

        @function_tool
        def export_report(include_valuation: bool = True, include_actions: bool = True) -> dict:
            """Generate a PDF advisory report."""
            from tools.exporter import generate_report
            return {"download_url": generate_report(client_id, {}, [])}

        return [retrieve_documents, run_financial_engine, run_valuation, export_report]


def build_graph(checkpointer=None):
    from agent.base import get_checkpointer
    return build_rehearsal_graph("buyer", checkpointer=checkpointer or get_checkpointer())


def create_graph():
    return build_graph()
