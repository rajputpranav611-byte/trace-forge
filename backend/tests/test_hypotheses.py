import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.db.seed import seed_graph
from app.schemas.hypotheses import RawHypothesis, LLMHypothesisOutput
from app.db.investigation import build_investigation_context
from app.core.llm.verifier import verify_hypotheses_against_graph

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_seed():
    seed_graph("traceforge")


def test_generate_hypotheses_valid_incident():
    """Tests generating and verifying hypotheses for active incident INC-2026-8821."""
    response = client.post("/api/v1/investigation/hypotheses/INC-2026-8821?max_depth=3")
    assert response.status_code == 200
    data = response.json()

    assert data["incident_id"] == "INC-2026-8821"
    assert len(data["hypotheses"]) >= 1
    assert "disclaimer" in data
    assert "Candidate explanations" in data["disclaimer"]

    # Verify each hypothesis
    for hyp in data["hypotheses"]:
        assert hyp["id"].startswith("HYP-")
        assert 0.0 <= hyp["confidence"] <= 1.0
        assert hyp["verification_status"] in ["verified", "partially_verified", "unverified"]
        # All returned supporting evidence must be valid
        for ev in hyp["supporting_evidence"]:
            assert ev["is_valid"] is True
            assert ev["id"]


def test_reject_unsupported_or_fabricated_evidence():
    """Tests that hallucinated/fabricated evidence IDs are detected, rejected, and counted."""
    context = build_investigation_context("INC-2026-8821")
    assert context is not None

    mock_raw = LLMHypothesisOutput(
        hypotheses=[
            RawHypothesis(
                id="HYP-FAKE",
                title="Fabricated Root Cause",
                statement="Hallucinated service failure based on invented alerts",
                suspected_entity="fake-service",
                confidence=0.9,
                supporting_evidence_ids=["ALT-101", "NON-EXISTENT-ALERT-999", "FAKE-DEP-000"],
                contradicting_evidence_ids=["NON-EXISTENT-METRIC-404"],
            )
        ],
        reasoning_summary="Test model output containing fabricated references",
    )

    verified = verify_hypotheses_against_graph(
        raw_output=mock_raw,
        context=context,
        provider_name="MockProvider",
        model_name="mock-test",
        is_fallback=False,
    )

    hyp = verified.hypotheses[0]
    # The valid evidence ALT-101 should be accepted
    assert any(ev.id == "ALT-101" for ev in hyp.supporting_evidence)

    # The fabricated IDs must be rejected
    assert "NON-EXISTENT-ALERT-999" in hyp.rejected_evidence_ids
    assert "FAKE-DEP-000" in hyp.rejected_evidence_ids
    assert "NON-EXISTENT-METRIC-404" in hyp.rejected_evidence_ids
    assert verified.rejected_evidence_total == 3
    assert hyp.verification_status == "partially_verified"


def test_malformed_model_output_fallback():
    """Tests that malformed or non-compliant model outputs automatically trigger deterministic fallback."""
    from app.core.config import Settings
    mock_settings = Settings(GEMINI_API_KEY="mock-key", LLM_PROVIDER="gemini")
    with patch("app.core.config.get_settings", return_value=mock_settings):
        with patch("app.core.llm.provider.GeminiProvider.generate_hypotheses", side_effect=ValueError("Invalid JSON from LLM")):
            response = client.post("/api/v1/investigation/hypotheses/INC-2026-8821")
            assert response.status_code == 200
            data = response.json()
            assert data["is_fallback"] is True
            assert len(data["hypotheses"]) >= 1


def test_llm_timeout_triggers_fallback():
    """Tests that LLM request timeouts seamlessly revert to deterministic fallback."""
    import httpx
    from app.core.config import Settings
    mock_settings = Settings(GEMINI_API_KEY="mock-key", LLM_PROVIDER="gemini")
    with patch("app.core.config.get_settings", return_value=mock_settings):
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout contacting Gemini API")):
            response = client.post("/api/v1/investigation/hypotheses/INC-2026-8821")
            assert response.status_code == 200
            data = response.json()
            assert data["is_fallback"] is True
            assert len(data["hypotheses"]) >= 1


def test_insufficient_context_honest_representation():
    """Tests that incidents with insufficient observations (e.g. INC-2026-9043)

    honestly flag epistemic uncertainty in missing_evidence_notes.
    """
    response = client.post("/api/v1/investigation/hypotheses/INC-2026-9043")
    assert response.status_code == 200
    data = response.json()
    assert any("uncertainty" in note.lower() or "limited" in note.lower() for note in data["missing_evidence_notes"])
