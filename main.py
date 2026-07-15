"""
AI Advisory MVP — unified entry point.

Usage:
    # Deterministic multi-lens report (no API key required):
    python main.py
    python main.py --goal sale
    python main.py --goal loan
    python main.py --goal investor
    python main.py path/to/business.json --goal all

    # LangGraph buyer-persona diligence rehearsal (ANTHROPIC_API_KEY optional):
    python main.py --goal sale --rehearsal

    # Full OpenAI agent loop via FastAPI (OPENAI_API_KEY + openai>=1.77):
    python main.py --goal sale --agent --client demo_client

    # Start the HTTP API server:
    uvicorn orchestrator.api:app --host 0.0.0.0 --port 8000 --reload
"""

import argparse
import asyncio
import json

from dotenv import load_dotenv

load_dotenv()


# ── helpers ──────────────────────────────────────────────────────────────────

def load_business(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


# ── report path (deterministic, no LLM) ──────────────────────────────────────

def print_report(business: dict, goal: str) -> None:
    from agent.orchestrator import build_report

    report = build_report(business, goal)

    print(f"\n{report.business_name} -- advisory report ({goal})\n")
    for lens_report in report.lens_reports:
        print(f"{lens_report.lens.upper()} READINESS: {lens_report.score}/100")
        print(f"  {lens_report.summary}")
        for finding in lens_report.findings:
            print(f"  [{finding['severity'].upper():6}] {finding['metric']}: {finding['value']}")
        print()

    print("Prioritized actions")
    for idx, finding in enumerate(report.prioritized_actions, start=1):
        print(f"  {idx}. {finding['fix_narrative']}")

    if report.reconciled_risks:
        print("\nReconciled cross-lens risks")
        for risk in report.reconciled_risks:
            print(f"  - {risk}")

    print(f"\nAdvisor review required: {'yes' if report.advisor_review_required else 'no'}")


# ── rehearsal path (LangGraph, Anthropic LLM optional) ───────────────────────

def run_rehearsal(business: dict, goal: str) -> None:
    from scoring import sale_readiness, loan_readiness, investor_readiness
    from langgraph.types import Command

    lens_map = {
        "sale": (sale_readiness.compute_findings, sale_readiness.compute_score, "sale_agent"),
        "loan": (loan_readiness.compute_findings, loan_readiness.compute_score, "loan_agent"),
        "investor": (investor_readiness.compute_findings, investor_readiness.compute_score, "investor_agent"),
    }

    # Default to sale if "all" is requested for the rehearsal path
    target = goal if goal != "all" else "sale"
    compute_findings, compute_score, agent_module = lens_map[target]

    findings = compute_findings(business)
    score = compute_score(findings)

    print(f"\n{business['name']} -- {target} readiness score: {score}/100\n")
    for finding in findings:
        print(f"  [{finding['severity'].upper():6}] {finding['metric']}: {finding['value']}")

    mod = __import__(f"agent.{agent_module}", fromlist=["build_graph"])
    graph = mod.build_graph()

    config = {"configurable": {"thread_id": "rehearsal-1"}}
    initial_state = {
        "business": business,
        "persona": "",
        "findings": findings,
        "idx": 0,
        "transcript": [],
        "current_question": "",
        "last_answer": "",
        "flagged": [],
        "done": False,
    }

    print(f"\nStarting {target} rehearsal on the highest-severity findings...\n")

    result = graph.invoke(initial_state, config=config)

    while isinstance(result, dict) and result.get("__interrupt__"):
        interrupt_data = result["__interrupt__"][0].value
        persona = interrupt_data.get("persona", "advisor")
        question = interrupt_data.get("question", "")
        answer = input(f"\n[{persona}] {question}\n> ")
        result = graph.invoke(Command(resume=answer), config=config)

    print("\n--- Rehearsal summary ---")
    flagged = result.get("flagged", [])
    if flagged:
        for item in flagged:
            print(f"\n  Flagged: {item['metric']}")
            print(f"    {item['note']}")
            print(f"    Fix: {item['fix']}")
    else:
        print("  No findings were flagged -- all answers cited concrete evidence.")


# ── agent path (OpenAI Agents SDK, requires openai>=1.77) ────────────────────

async def run_agent(goal: str, client_id: str) -> None:
    from orchestrator.api import get_agent

    prompts = {
        "sale": "Am I ready to sell my business?",
        "loan": "Can I qualify for an SBA 7(a) loan?",
        "investor": "What should I include in a seed-round pitch deck?",
        "general": "Give me an overview of my business health.",
    }
    goals = ["sale", "loan", "investor"] if goal == "all" else [goal]
    for g in goals:
        agent = get_agent(g, client_id, prompts.get(g, "Advise me."))
        result = await agent.run()
        print(f"\n=== {g.upper()} AGENT RESULT ===")
        print(json.dumps(result, indent=2))


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Advisory MVP — run the orchestrator locally.")
    parser.add_argument("path", nargs="?", default="data/sample_business.json",
                        help="Path to business JSON profile.")
    parser.add_argument("--goal", choices=["sale", "loan", "investor", "all"], default="all",
                        help="Which readiness lens to run (default: all).")
    parser.add_argument("--rehearsal", action="store_true",
                        help="Run the interactive diligence rehearsal (LangGraph path).")
    parser.add_argument("--agent", action="store_true",
                        help="Run via the OpenAI Agents SDK (requires openai>=1.77 and OPENAI_API_KEY).")
    parser.add_argument("--client", default="demo_client",
                        help="Client ID used by the agent path (default: demo_client).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.agent:
        asyncio.run(run_agent(args.goal, args.client))
        return

    business = load_business(args.path)

    print_report(business, args.goal)

    if args.rehearsal:
        run_rehearsal(business, args.goal)


if __name__ == "__main__":
    main()
