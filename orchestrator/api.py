from dotenv import load_dotenv
load_dotenv()

from datetime import datetime

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from orchestrator.router import AGENT_REGISTRY, dispatch

app = FastAPI(
    title="AI Advisory Orchestrator",
    description="Single HTTP entry point that routes to the appropriate specialist agent.",
    version="1.0.0",
)


class AdviseRequest(BaseModel):
    client_id: str = Field(..., description="Unique identifier for the customer")
    scenario: str = Field(..., description="One of: sale | loan | investor | general")
    message: str = Field(..., description="User's natural-language query")
    rehearsal: bool = Field(
        False,
        description="If true, run in rehearsal mode (no OpenAI API calls).",
    )


class AdviseResponse(BaseModel):
    payload: dict
    trace_id: str


def get_agent(scenario: str, client_id: str, user_msg: str):
    agent_cls = AGENT_REGISTRY.get(scenario.lower())
    if not agent_cls:
        raise ValueError(f"Unsupported scenario '{scenario}'.")
    return agent_cls(client_id, user_msg)


@app.post("/v1/advise", response_model=AdviseResponse)
async def advise_endpoint(req: AdviseRequest, background_tasks: BackgroundTasks):
    del background_tasks
    try:
        result = await dispatch(
            client_id=req.client_id,
            scenario=req.scenario,
            user_message=req.message,
            rehearsal=req.rehearsal,
        )
    except HTTPException as http_err:
        raise http_err
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return AdviseResponse(**result)


@app.post("/v1/advise/sale", response_model=AdviseResponse)
async def advise_sale(client_id: str = "demo_client", message: str = "Am I ready to sell my business?"):
    result = await dispatch(client_id=client_id, scenario="sale", user_message=message)
    return AdviseResponse(**result)


@app.post("/v1/advise/loan", response_model=AdviseResponse)
async def advise_loan(client_id: str = "demo_client", message: str = "Can I qualify for an SBA 7(a) loan?"):
    result = await dispatch(client_id=client_id, scenario="loan", user_message=message)
    return AdviseResponse(**result)


@app.post("/v1/advise/investor", response_model=AdviseResponse)
async def advise_investor(client_id: str = "demo_client", message: str = "Am I ready for a seed round?"):
    result = await dispatch(client_id=client_id, scenario="investor", user_message=message)
    return AdviseResponse(**result)


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/metrics")
def metrics():
    return {"message": "Metrics endpoint placeholder"}