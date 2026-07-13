from typing import Any, Dict

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


class GeneralAgent(AgentBase):
    name = "General-Assistant"
    description = "Handles non-scenario-specific business-finance questions."

    tools = [
        _tool(
            "retrieve_documents",
            "Search the knowledge base.",
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
            "Compute ratios and health score.",
            {"type": "object", "properties": {}, "required": []},
        ),
        _tool(
            "export_report",
            "Generate a generic advisory PDF.",
            {
                "type": "object",
                "properties": {
                    "include_snapshot": {"type": "boolean"},
                },
                "required": [],
            },
        ),
    ]

    def system_prompt(self) -> str:
        return (
            "You are a knowledgeable business-finance assistant. "
            "Answer using only data you retrieve or compute. "
            "If required data is missing, say 'I don't have that data'. "
            "Return JSON payload with explanation (markdown), evidence (list of source doc IDs), "
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

    async def _dispatch_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name == "retrieve_documents":
            from tools.retriever import DocumentRetriever

            retriever = DocumentRetriever(self.client_id)
            return {"documents": retriever.retrieve(args["query"], int(args.get("k", 5)))}

        if name == "run_financial_engine":
            from tools.financial_engine import FinancialEngine

            engine = FinancialEngine(self.client_id)
            ratios, confidence = engine.compute_ratios()
            return {"ratios": ratios, "confidence": confidence}

        if name == "export_report":
            from tools.exporter import generate_report

            snapshot = args.get("snapshot", {}) if bool(args.get("include_snapshot", True)) else {}
            url = generate_report(self.client_id, snapshot, [])
            return {"download_url": url}

        raise ValueError(f"Unknown tool {name}")


def build_graph(checkpointer=None):
    return build_rehearsal_graph("general", checkpointer=checkpointer)


def create_graph():
    return build_graph()