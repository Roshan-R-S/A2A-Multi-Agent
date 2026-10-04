import json

import pytest
from starlette.testclient import TestClient

from agents.verifier.app import app
from agents.verifier.executor import VerifierAgent


def test_verifier_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200

    assert response.json() == {
        "status": "ok",
        "agent": "Verifier Agent",
        "version": "0.1.0",
    }


def test_verifier_agent_card_endpoint():
    with TestClient(app) as client:
        response = client.get(
            "/.well-known/agent-card.json"
        )

    assert response.status_code == 200

    card = response.json()

    assert card["name"] == "Verifier Agent"

    assert (
        card["supportedInterfaces"][0]["protocolBinding"]
        == "JSONRPC"
    )

    skill_ids = {
        skill["id"]
        for skill in card["skills"]
    }

    assert "verify_answer" in skill_ids


def test_verifier_accepts_valid_pass_json():
    raw = '''
    {
        "verdict": "PASS",
        "issues": [],
        "feedback": ""
    }
    '''

    result = VerifierAgent._validate_result(raw)

    data = json.loads(result)

    assert data["verdict"] == "PASS"
    assert data["issues"] == []
    assert data["feedback"] == ""


def test_verifier_accepts_valid_fail_json():
    raw = '''
    {
        "verdict": "FAIL",
        "issues": [
            "Unsupported claim."
        ],
        "feedback": "Remove the claim."
    }
    '''

    result = VerifierAgent._validate_result(raw)

    data = json.loads(result)

    assert data["verdict"] == "FAIL"
    assert data["issues"] == [
        "Unsupported claim."
    ]
    assert data["feedback"] == (
        "Remove the claim."
    )


def test_verifier_handles_markdown_json_fence():
    raw = '''
```json
{
    "verdict": "PASS",
    "issues": [],
    "feedback": ""
}
```
    '''

    result = VerifierAgent._validate_result(raw)

    data = json.loads(result)

    assert data["verdict"] == "PASS"
    assert data["issues"] == []
    assert data["feedback"] == ""


def test_verifier_rejects_invalid_json():
    with pytest.raises(
        RuntimeError,
        match="invalid JSON",
    ):
        VerifierAgent._validate_result(
            "This is not JSON."
        )


def test_verifier_rejects_invalid_verdict():
    raw = '''
    {
        "verdict": "MAYBE",
        "issues": [],
        "feedback": ""
    }
    '''

    with pytest.raises(
        RuntimeError,
        match="PASS or FAIL",
    ):
        VerifierAgent._validate_result(raw)
