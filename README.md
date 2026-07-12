# AI advisory MVP scaffold

A minimal, runnable slice of the framework in `AI_Advisory_Framework.docx`:
one lens (sale readiness), a deterministic scoring engine, and a LangGraph
buyer-persona diligence rehearsal built on top of it.

This is Phase 1 from the build plan -- a single-lens MVP meant to validate
the agentic pipeline pattern before expanding to the loan and investor
lenses, the living deal room, and benchmarking.

## What's here

```
scoring/sale_readiness.py   deterministic scoring -- no LLM, fully unit-testable
agents/state.py             LangGraph state schema
agents/llm.py               LLM wrapper with a template/heuristic fallback
agents/graph.py             the rehearsal state graph
data/sample_business.json   a sample business profile to run against
main.py                     CLI entry point
```

## Why the scoring engine has no LLM in it

Every number the customer sees should be traceable to a plain calculation
on their own data -- concentration percentage, owner-dependency count,
recurring revenue share. This is the piece from the framework doc that
must never hallucinate, so it's kept as ordinary, testable Python. The
agent layer only explains and interrogates these numbers; it never
computes them.

## Running it

```
pip install -r requirements.txt
python main.py
```

Works with **no API key** -- `agents/llm.py` falls back to templated
questions and keyword-based evaluation so you can read through the graph
logic and see the full flow end to end before wiring up a real model.

To use real generation, set an API key:

```
export ANTHROPIC_API_KEY=your-key-here
python main.py
```

Try your own business data:

```
python main.py path/to/your_business.json
```

(match the shape in `data/sample_business.json`)

## Importing into watsonx Orchestrate

`agents/graph.py` uses LangGraph's native `interrupt()` / `Command(resume=...)`
pattern for the human-in-the-loop step, rather than a blocking `input()`
call -- which is what makes it importable into watsonx Orchestrate as-is.
`main.py` shows the driving loop: each `interrupt()` pauses the graph and
hands control back to whoever's driving it (a CLI loop here, Orchestrate's
conversation-turn handling once imported).

`agent.yaml` is the import spec. Once the ADK is installed
(`pip install --upgrade ibm-watsonx-orchestrate`):

```
orchestrate agents import -f agent.yaml
```

Two things worth knowing before importing:

- **All graph state must be a declared field in `RehearsalState`**
  (`agents/state.py`). This isn't just tidiness -- undeclared keys don't
  reliably survive an `interrupt()`/resume cycle, because Orchestrate's
  imported-agent runtime only preserves message-shaped state between
  conversation turns. This scaffold hit exactly this bug during
  development (an ad hoc `_last_answer` key silently went missing across
  the pause) before `last_answer` was added to the schema properly --
  worth remembering if you extend the state shape later.
- **Findings are plain dicts, not custom class instances** (see
  `scoring/sale_readiness.py`), for the same reason -- custom objects are
  the wrong thing to put in state that has to survive a serialize/restore
  cycle, on this checkpointer or Orchestrate's.

Verify the exact YAML fields and CLI syntax against IBM's current ADK docs
before importing -- this is a new and fast-moving part of the platform.

## What's deliberately left out (see the framework doc for the full picture)

- **Multi-lens orchestrator** -- this scaffold hard-codes the sale-readiness
  lens and the buyer persona. The loan and investor lenses are new rubric
  functions in `scoring/`, plus new persona prompts in `agents/llm.py`;
  the graph shape doesn't need to change much.
- **Human advisor review checkpoint** -- flagged findings currently print
  straight to the CLI. Before anything is customer-facing, route
  `evaluate_answer`'s output through an approval step.
- **Living deal room / benchmarking** -- both depend on data connectors and
  outcome data this scaffold doesn't have yet. See sections 5.2 and 5.4 of
  the framework doc for the buildout plan.

## Suggested next step

Get the scoring rubric in `scoring/sale_readiness.py` reviewed by someone
who has actually run M&A diligence, before trusting the numbers on real
customer data.
