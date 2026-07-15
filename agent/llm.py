"""
Thin LLM wrapper.

If ANTHROPIC_API_KEY is set, uses langchain-anthropic for real generation.
Otherwise falls back to plain templates so the whole scaffold runs and can
be smoke-tested with no API key and no network call -- useful for CI and
for a first read-through of the graph logic.
"""

import os

PERSONA_PROMPTS = {
    "general": (
        "You are a senior business advisor. You are practical, direct, and "
        "focused on the single biggest weakness in the finding given to you. "
        "You ask one concise question at a time."
    ),
    "buyer": (
        "You are a private-equity buyer's diligence lead. You are direct, "
        "skeptical, and unimpressed by reassurance without documentation. "
        "You ask one pointed question at a time about the finding given to you."
    ),
    "sba_underwriter": (
        "You are an SBA loan underwriter. You care about debt service coverage, "
        "documentation, and repayment risk. You ask one precise question at a time."
    ),
    "investor": (
        "You are a Series A investor evaluating this company. You care about "
        "growth, scalability, and key-person risk. You ask one sharp question at a time."
    ),
}

PERSONA_FALLBACK_QUESTIONS = {
    "general": {
        "customer_concentration": "{value}. What is your concrete plan to reduce this risk?",
        "owner_dependency": "{value}. What can be delegated and documented first?",
        "recurring_revenue": "{value}. What can you convert into predictable revenue next?",
        "documentation_completeness": "{value}. What is missing and who owns fixing it?",
    },
    "buyer": {
        "customer_concentration": "{value}. What happens to this business if they leave?",
        "owner_dependency": "{value}. Who runs this if you're out for three months?",
        "recurring_revenue": "{value}. How much of the rest is one-off, unpredictable work?",
        "documentation_completeness": "{value}. When can I see the rest?",
    },
    "sba_underwriter": {
        "customer_concentration": "{value}. What signed agreement protects cash flow if this customer leaves?",
        "owner_dependency": "{value}. Who is trained today to keep operations and debt payments on track without you?",
        "recurring_revenue": "{value}. What contracted revenue supports repayment consistency month to month?",
        "documentation_completeness": "{value}. Which missing documents would delay underwriting right now?",
    },
    "investor": {
        "customer_concentration": "{value}. How do you scale without one account controlling the story?",
        "owner_dependency": "{value}. What leadership depth exists beyond the founder?",
        "recurring_revenue": "{value}. What makes revenue durable and compounding here?",
        "documentation_completeness": "{value}. What reporting discipline supports investor confidence today?",
    },
}

PERSONA_EVALUATION_NOTES = {
    "general": "Answer does not show a concrete operating plan or supporting evidence.",
    "buyer": "Answer does not reduce transfer risk with concrete evidence.",
    "sba_underwriter": "Answer does not show documented repayment support or operating controls.",
    "investor": "Answer does not show durable scale, leverage, or documented execution depth.",
}


def _get_chat_model():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-sonnet-4-6", max_tokens=300)
    except ImportError:
        return None


def ask_question(persona: str, finding) -> str:
    """Generate the persona's question about a single finding."""
    model = _get_chat_model()
    if model is None:
        templates = PERSONA_FALLBACK_QUESTIONS.get(persona, PERSONA_FALLBACK_QUESTIONS["buyer"])
        template = templates.get(finding["metric"], "Tell me more about: {value}")
        return template.format(value=finding["value"])

    system = PERSONA_PROMPTS[persona]
    prompt = (
        f"Finding: {finding["narrative"]}\n"
        f"Severity: {finding["severity"]}\n\n"
        "Ask the business owner one direct, specific question about this finding. "
        "Do not soften it. Return only the question."
    )
    response = model.invoke([("system", system), ("human", prompt)])
    return response.content.strip()


def evaluate_answer(persona: str, finding, answer: str) -> dict:
    """
    Decide whether the customer's answer resolves the risk or confirms it.
    Returns {"resolved": bool, "note": str}.
    """
    model = _get_chat_model()
    if model is None:
        # Heuristic fallback: look for evidence keywords relevant to the metric.
        answer_lower = answer.lower()
        evidence_by_metric = {
            "customer_concentration": ["contract", "signed", "multi-year", "agreement"],
            "owner_dependency": ["documented", "sop", "trained", "manager", "process"],
            "recurring_revenue": ["contract", "subscription", "recurring"],
            "documentation_completeness": ["organized", "ready", "complete", "uploaded"],
        }
        keywords = evidence_by_metric.get(finding["metric"], [])
        resolved = any(k in answer_lower for k in keywords)
        note = (
            "Answer references concrete evidence for this finding."
            if resolved
            else PERSONA_EVALUATION_NOTES.get(
                persona,
                "Answer does not cite documentation or evidence -- risk stands as flagged.",
            )
        )
        return {"resolved": resolved, "note": note}

    system = PERSONA_PROMPTS[persona]
    prompt = (
        f"Finding: {finding["narrative"]}\n"
        f"Owner's answer: {answer}\n\n"
        "Does this answer resolve the underlying risk with concrete evidence "
        "(a contract, a documented process, a specific number), or is it "
        "reassurance without evidence? Reply with 'RESOLVED: <one line>' or "
        "'FLAGGED: <one line>'."
    )
    response = model.invoke([("system", system), ("human", prompt)]).content.strip()
    resolved = response.upper().startswith("RESOLVED")
    note = response.split(":", 1)[-1].strip() if ":" in response else response
    return {"resolved": resolved, "note": note}
