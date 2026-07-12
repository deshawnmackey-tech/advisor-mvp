from typing import Literal, TypedDict
from scoring.sale_readiness import Finding

Persona = Literal["buyer", "sba_underwriter", "investor", "general"]


class Turn(TypedDict):
    speaker: str  # "persona" | "customer" | "system"
    text: str


class RehearsalState(TypedDict):
    business: dict
    persona: Persona
    findings: list[Finding]
    idx: int
    transcript: list[Turn]
    current_question: str
    last_answer: str  # must be a declared schema field -- see note in graph.py
    flagged: list[dict]  # accumulated risk flags with fix guidance
    done: bool
