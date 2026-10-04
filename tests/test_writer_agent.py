from starlette.testclient import TestClient

from agents.writer.app import app


def test_writer_health_endpoint():
    with TestClient(app) as client:
        response = client.get(
            "/health"
        )

    assert response.status_code == 200

    assert response.json() == {
        "status": "ok",
        "agent": "Writer Agent",
        "version": "0.1.0",
    }


def test_writer_agent_card_endpoint():
    with TestClient(app) as client:
        response = client.get(
            "/.well-known/agent-card.json"
        )

    assert response.status_code == 200

    card = response.json()

    assert card["name"] == (
        "Writer Agent"
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
        "write_explanation"
        in skill_ids
    )
