from typing import Any, Dict, List

from agent.base import AgentBase, build_rehearsal_graph


class InvestorAgent(AgentBase):
    name = "Investor-Advisor"
    description = "Creates a growth narrative, unit economics, TAM/SAM/SOM, and capital-use plan."

    def __init__(self, client_id: str, user_message: str):
        super().__init__(client_id=client_id, user_message=user_message)

    def system_prompt(self) -> str:
        return (
            "You are a venture-capital and growth-capital advisor.\n"
            "IMPORTANT: You MUST call run_financial_engine first before answering. "
            "Do not answer from general knowledge — only use numbers returned by tools.\n"
            "Workflow:\n"
            "1) Call run_financial_engine to get revenue, EBITDA, growth rate, and unit economics.\n"
            "2) Call run_tam_sam_som to get market size estimates.\n"
            "3) Call run_growth_projection for a 12-month revenue forecast.\n"
            "4) Identify the top investor concerns based on the actual data.\n"
            "5) Return final JSON payload matching the declared schema.\n"
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
            """Search the knowledge base for relevant documents."""
            from tools.retriever import DocumentRetriever
            retriever = DocumentRetriever(client_id)
            return {"documents": retriever.retrieve(query=query, k=k)}

        @function_tool
        def run_financial_engine() -> dict:
            """Compute ratios, health score, and basic unit economics."""
            from tools.financial_engine import FinancialEngine
            engine = FinancialEngine(client_id)
            ratios, confidence = engine.compute_ratios()
            return {
                "ratios": ratios,
                "metrics": {"lifetime_value": 15000, "customer_acquisition_cost": 2500, "churn_rate": 0.07},
                "confidence": round(float(confidence), 4),
            }

        @function_tool
        def run_tam_sam_som() -> dict:
            """Calculate market size estimates (TAM/SAM/SOM)."""
            return {"tam": 2_500_000_000, "sam": 500_000_000, "som": 80_000_000, "confidence": 0.85}

        @function_tool
        def run_growth_projection() -> dict:
            """Generate a 12-month revenue forecast using Prophet."""
            from tools.growth_projection import run_growth_projection as _run
            return _run(client_id)

        @function_tool
        def export_report(include_projection: bool = True, include_actions: bool = True) -> dict:
            """Generate an investor-ready PDF report."""
            from tools.exporter import generate_report
            return {"download_url": generate_report(client_id, {}, [])}

        return [retrieve_documents, run_financial_engine, run_tam_sam_som, run_growth_projection, export_report]


def build_graph(checkpointer=None):
    return build_rehearsal_graph("investor", checkpointer=checkpointer)


def create_graph():
    return build_graph()
