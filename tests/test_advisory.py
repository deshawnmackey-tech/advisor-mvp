from orchestrator.router import route_persona


def test_router_prefers_underwriter_for_weak_documentation():
    result = route_persona(
        {
            "business": {
                "documentation_completeness_pct": 40,
                "recurring_revenue_pct": 80,
                "annual_revenue": 6000000,
            }
        }
    )
    assert result["recommended_persona"] == "sba_underwriter"


def test_router_honors_explicit_persona():
    result = route_persona({"business": {}, "requested_persona": "investor"})
    assert result["recommended_persona"] == "investor"