from typing import Literal, TypedDict

# Import Finding from the shared models module, not from a specific lens.
# This keeps state independent of which lens generated the findings.
from scoring.models import Finding  # noqa: F401

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
    last_answer: str  # must be a declared schema field -- see note in README
    flagged: list[dict]  # accumulated risk flags with fix guidance
    done: bool
