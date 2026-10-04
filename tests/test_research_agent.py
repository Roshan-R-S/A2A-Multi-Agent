from starlette.testclient import TestClient

from agents.research.app import app


def test_research_health_endpoint():
    with TestClient(app) as client:
        response = client.get(
            "/health"
        )

    assert response.status_code == 200

    assert response.json() == {
        "status": "ok",
        "agent": "Research Agent",
        "version": "0.1.0",
    }


def test_research_agent_card_endpoint():
    with TestClient(app) as client:
        response = client.get(
            "/.well-known/agent-card.json"
        )

    assert response.status_code == 200

    card = response.json()

    assert card["name"] == (
        "Research Agent"
    )

    assert (
        card["supportedInterfaces"][0]
        ["protocolBinding"]
        == "JSONRPC"
    )

    skill_ids = {
        skill["id"]
        for skill in card["skills"]
    }

    assert (
        "research_topic"
        in skill_ids
    )
