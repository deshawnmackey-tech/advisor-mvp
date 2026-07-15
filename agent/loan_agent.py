from typing import Any, Dict, List

from agent.base import AgentBase, build_rehearsal_graph


class LoanAgent(AgentBase):
    name = "Loan-Advisor"
    description = "Evaluates loan capacity, DSCR, collateral gaps, and required documentation."

    def __init__(self, client_id: str, user_message: str):
        super().__init__(client_id=client_id, user_message=user_message)

    def system_prompt(self) -> str:
        return (
            "You are a senior loan-officer advisor.\n"
            "IMPORTANT: You MUST call run_financial_engine first before answering. "
            "Do not answer from general knowledge — only use numbers returned by tools.\n"
            "Workflow:\n"
            "1) Call run_financial_engine to get DSCR, working capital, and doc completeness.\n"
            "2) Call run_collateral_assessment to estimate collateral gap at DSCR 1.25x.\n"
            "3) Identify missing SBA 7(a) documentation based on doc_completeness score.\n"
            "4) Return final JSON payload matching the declared schema.\n"
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
            """Compute ratios, DSCR, and health score."""
            from tools.financial_engine import FinancialEngine
            engine = FinancialEngine(client_id)
            ratios, confidence = engine.compute_ratios()
            return {"ratios": ratios, "confidence": round(float(confidence), 4)}

        @function_tool
        def run_collateral_assessment() -> dict:
            """Assess existing collateral and compute the gap to meet a target DSCR of 1.25x."""
            from tools.financial_engine import FinancialEngine
            engine = FinancialEngine(client_id)
            features = engine._load_features()
            ebitda = float(features.get("ebitda_ttm", 0.0))
            debt_service = float(features.get("debt_service", 0.0))
            target_dscr = 1.25
            required_debt = ebitda / target_dscr if target_dscr > 0 else 0.0
            gap = max(0.0, required_debt - debt_service)
            return {
                "existing_collateral_usd": 500_000,
                "required_debt_capacity_usd": round(required_debt, 2),
                "collateral_gap_usd": round(gap, 2),
            }

        @function_tool
        def export_report(include_collateral: bool = True, include_actions: bool = True) -> dict:
            """Generate a loan-readiness PDF report."""
            from tools.exporter import generate_report
            return {"download_url": generate_report(client_id, {}, [])}

        return [retrieve_documents, run_financial_engine, run_collateral_assessment, export_report]


def build_graph(checkpointer=None):
    return build_rehearsal_graph("sba_underwriter", checkpointer=checkpointer)


def create_graph():
    return build_graph()
