import pytest

from orchestrator import get_agent


@pytest.mark.asyncio
async def test_sale_agent():
    agent = get_agent("sale", "demo_client", "Am I ready to sell?")
    result = await agent.run()
    assert "snapshot" in result
    assert "actions" in result
    assert result["disclaimer"].startswith("This is educational")


@pytest.mark.asyncio
async def test_loan_agent():
    agent = get_agent("loan", "demo_client", "Can I get an SBA loan?")
    result = await agent.run()
    snap = result["snapshot"]
    assert "dscr" in snap
    assert snap["dscr"] > 0


@pytest.mark.asyncio
async def test_investor_agent():
    agent = get_agent("investor", "demo_client", "What should I include in a seed pitch?")
    result = await agent.run()
    snap = result["snapshot"]
    assert "projected_revenue_12m" in snap
    assert snap["confidence"] >= 0.7