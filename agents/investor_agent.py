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


class InvestorAgent(AgentBase):
    name = "Investor-Advisor"
    description = "Creates a growth narrative, unit economics, TAM/SAM/SOM, and capital-use plan."

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
            "Compute ratios, health score, and basic unit economics.",
            {"type": "object", "properties": {}, "required": []},
        ),
        _tool(
            "run_tam_sam_som",
            "Calculate market size estimates (TAM/SAM/SOM).",
            {"type": "object", "properties": {}, "required": []},
        ),
        _tool(
            "run_growth_projection",
            "Generate a 12-month revenue forecast using Prophet.",
            {"type": "object", "properties": {}, "required": []},
        ),
        _tool(
            "export_report",
            "Generate an investor-ready PDF report.",
            {
                "type": "object",
                "properties": {
                    "include_projection": {"type": "boolean"},
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
            "You are a venture-capital and growth-capital advisor.\n"
            "Responsibilities:\n"
            "1) Explain unit economics and cash-flow runway.\n"
            "2) Use run_tam_sam_som when market assumptions are provided.\n"
            "3) Use run_growth_projection when a forward view is requested.\n"
            "4) Return final JSON payload matching the declared schema.\n"
            "5) Export report on request.\n"
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
            metrics = {
                "lifetime_value": 15000,
                "customer_acquisition_cost": 2500,
                "churn_rate": 0.07,
            }
            result = {
                "ratios": ratios,
                "metrics": metrics,
                "confidence": round(float(confidence), 4),
            }
            self._latest_snapshot.update(result)
            return result

        if name == "run_tam_sam_som":
            market = {
                "tam": 2_500_000_000,
                "sam": 500_000_000,
                "som": 80_000_000,
                "confidence": 0.85,
            }
            self._latest_snapshot["tam_sam_som"] = market
            return market

        if name == "run_growth_projection":
            from tools.growth_projection import run_growth_projection

            projection = run_growth_projection(self.client_id)
            self._latest_snapshot["growth_projection"] = projection
            return projection

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
    return build_rehearsal_graph("investor", checkpointer=checkpointer)


def create_graph():
    return build_graph()