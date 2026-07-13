import argparse
import asyncio
import json
from orchestrator import get_agent


def parse_args():
    parser = argparse.ArgumentParser(description="Run advisory agents locally")
    parser.add_argument(
        "--goal",
        choices=["sale", "loan", "investor", "all"],
        required=True,
        help="Which scenario to run",
    )
    parser.add_argument("--client", default="demo_client", help="Client ID")
    parser.add_argument(
        "--rehearsal",
        action="store_true",
        help="Run in rehearsal mode (placeholder flag)",
    )
    return parser.parse_args()


async def run_one(goal, client_id):
    prompts = {
        "sale": "Am I ready to sell my business?",
        "loan": "Can I qualify for an SBA 7(a) loan?",
        "investor": "What should I include in a seed-round pitch deck?",
    }
    agent = get_agent(goal, client_id, prompts[goal])
    result = await agent.run()
    print(f"\n=== {goal.upper()} RESULT ===")
    print(json.dumps(result, indent=2))


async def main():
    args = parse_args()
    if args.rehearsal:
        print("Rehearsal flag is set; running standard agent flow for now.")

    if args.goal == "all":
        for goal in ["sale", "loan", "investor"]:
            await run_one(goal, args.client)
    else:
        await run_one(args.goal, args.client)


if __name__ == "__main__":
    asyncio.run(main())
