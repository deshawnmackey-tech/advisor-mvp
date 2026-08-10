from typing import Any, Dict, List

from agent.base import AgentBase, build_rehearsal_graph


class GeneralAgent(AgentBase):
    name = "General-Assistant"
    description = "Handles non-scenario-specific business-finance questions."

    def system_prompt(self) -> str:
        return (
            "You are a knowledgeable business-finance assistant. "
            "Answer using only data you retrieve or compute. "
            "If required data is missing, say 'I don't have that data'. "
            "Return JSON with explanation (markdown), evidence (list of source doc IDs), "
            "confidence (0-1), and disclaimer. "
            "Do not include actionable recommendations in generic mode."
        )

    def final_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "explanation": {"type": "string"},
                "evidence": {"type": "array"},
                "confidence": {"type": "number"},
                "disclaimer": {"type": "string"},
            },
            "required": ["explanation", "evidence", "confidence", "disclaimer"],
        }

    def _make_tools(self) -> List[Any]:
        from agent.base import _import_sdk
        _, _, function_tool, _ = _import_sdk()

        client_id = self.client_id

        @function_tool
        def retrieve_documents(query: str, k: int = 5) -> dict:
            """Search the knowledge base."""
            from tools.retriever import DocumentRetriever
            retriever = DocumentRetriever(client_id)
            return {"documents": retriever.retrieve(query, int(k))}

        @function_tool
        def run_financial_engine() -> dict:
            """Compute ratios and health score."""
            from tools.financial_engine import FinancialEngine
            engine = FinancialEngine(client_id)
            ratios, confidence = engine.compute_ratios()
            return {"ratios": ratios, "confidence": confidence}

        @function_tool
        def export_report(include_snapshot: bool = True) -> dict:
            """Generate a generic advisory PDF."""
            from tools.exporter import generate_report
            return {"download_url": generate_report(client_id, {}, [])}

        return [retrieve_documents, run_financial_engine, export_report]


def build_graph(checkpointer=None):
    return build_rehearsal_graph("general", checkpointer=checkpointer)


def create_graph():
    return build_graph()
