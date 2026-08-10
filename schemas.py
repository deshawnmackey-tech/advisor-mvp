from typing import Literal

from pydantic import BaseModel


Persona = Literal["buyer", "sba_underwriter", "investor", "general"]


class RouteRequest(BaseModel):
    business: dict
    requested_persona: Persona | None = None


class RouteResponse(BaseModel):
    recommended_persona: Persona
    routing_reason: str