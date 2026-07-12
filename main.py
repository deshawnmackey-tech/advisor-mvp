"""
Run the sale-readiness scoring engine, then a buyer-persona rehearsal
against the top findings.

Usage:
    python main.py                       # uses data/sample_business.json
    python main.py path/to/business.json # your own business profile

This loop drives the graph one interrupt at a time -- the same shape
watsonx Orchestrate uses internally once the agent is imported: each
interrupt is one conversation turn, and resuming is handing back the
customer's reply. Swapping input() for a web/chat front end here (instead
of importing to Orchestrate) requires no changes to agents/graph.py.
"""

import json
import sys
import uuid

from langgraph.types import Command

from scoring.sale_readiness import compute_findings, compute_score
from agents.sale_agent import build_graph


def load_business(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/sample_business.json"
    business = load_business(path)

    findings = compute_findings(business)
    score = compute_score(findings)

    print(f"\n{business['name']} -- sale readiness score: {score}/100\n")
    for f in findings:
        print(f"  [{f['severity'].upper():6}] {f['metric']}: {f['value']}")

    print("\nStarting buyer rehearsal on the highest-severity findings...\n")

    graph = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    initial_state = {
        "business": business,
        "persona": "buyer",
        "findings": findings,
        "idx": 0,
        "transcript": [],
        "current_question": "",
        "last_answer": "",
        "flagged": [],
        "done": False,
    }
    result = graph.invoke(initial_state, config=config)

    # Each iteration is one turn: the graph pauses at interrupt(), we collect
    # the customer's answer, and resume with it via Command(resume=...).
    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        answer = input(f"\n[{payload['persona']}] {payload['question']}\n> ")
        result = graph.invoke(Command(resume=answer), config=config)

    final_state = result

    print("\n--- Rehearsal summary ---")
    if final_state["flagged"]:
        for item in final_state["flagged"]:
            print(f"\n  Flagged: {item['metric']}")
            print(f"    {item['note']}")
            print(f"    Fix: {item['fix']}")
    else:
        print("  No findings were flagged -- all answers cited concrete evidence.")


if __name__ == "__main__":
    main()
