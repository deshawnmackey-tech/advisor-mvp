from fastapi import FastAPI

from orchestrator.router import route_persona
from schemas import RouteRequest, RouteResponse

app = FastAPI(title="Advisory MVP Orchestrator", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/route", response_model=RouteResponse)
def route(request: RouteRequest) -> RouteResponse:
    result = route_persona(
        {"business": request.business, "requested_persona": request.requested_persona}
    )
    return RouteResponse(
        recommended_persona=result["recommended_persona"],
        routing_reason=result["routing_reason"],
    )