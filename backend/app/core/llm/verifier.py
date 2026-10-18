import logging
from typing import Dict, Any, List, Set, Tuple
from app.schemas.investigation import InvestigationContextResponse
from app.schemas.hypotheses import (
    LLMHypothesisOutput,
    VerifiedHypothesis,
    VerifiedEvidence,
    HypothesisGenerationResponse,
)
from app.core.llm.provider import get_llm_provider
from app.core.llm.fallback import generate_deterministic_fallback_hypotheses

logger = logging.getLogger("traceforge.verifier")


def build_evidence_registry(context: InvestigationContextResponse) -> Dict[str, VerifiedEvidence]:
    """Indexes all verifiable graph records by ID to enable strict ground-truth validation."""
    registry: Dict[str, VerifiedEvidence] = {}

    for a in context.alerts:
        registry[a.id] = VerifiedEvidence(
            id=a.id,
            type="alert",
            description=f"Alert {a.name} on {a.service_name} ({a.severity}): {a.description}",
        )

    for m in context.metrics:
        registry[m.id] = VerifiedEvidence(
            id=m.id,
            type="metric",
            description=f"Anomaly on {m.metric_name}: observed {m.value}{m.unit} (+{m.deviation_sigma}σ from base {m.baseline})",
        )

    for d in context.deployments:
        registry[d.id] = VerifiedEvidence(
            id=d.id,
            type="deployment",
            description=f"Deployment {d.version} ({d.commit_sha}) on {d.service_name} at {d.deployed_at}",
        )

    for s in context.topology.affected_services:
        registry[s.id] = VerifiedEvidence(
            id=s.id,
            type="service",
            description=f"Service {s.name} (Tier {s.tier}, status: {s.status})",
        )

    for s in context.topology.traversed_services:
        registry[s.id] = VerifiedEvidence(
            id=s.id,
            type="service",
            description=f"Traversed dependency {s.name} (status: {s.status})",
        )

    for r in context.runbooks:
        registry[r.id] = VerifiedEvidence(
            id=r.id,
            type="runbook",
            description=f"Runbook {r.title} for {r.service_name}",
        )

    return registry


def verify_hypotheses_against_graph(
    raw_output: LLMHypothesisOutput,
    context: InvestigationContextResponse,
    provider_name: str,
    model_name: str,
    is_fallback: bool,
) -> HypothesisGenerationResponse:
    """Verifies all evidence IDs referenced in hypotheses against actual backend records.

    Rejects fabricated or unknown IDs and marks verification status accordingly.
    """
    registry = build_evidence_registry(context)
    total_rejected = 0
    verified_hypotheses: List[VerifiedHypothesis] = []

    for raw in raw_output.hypotheses:
        supporting: List[VerifiedEvidence] = []
        contradicting: List[VerifiedEvidence] = []
        rejected: List[str] = []

        # Validate supporting evidence
        for eid in raw.supporting_evidence_ids:
            if eid in registry:
                supporting.append(registry[eid])
            else:
                rejected.append(eid)
                total_rejected += 1

        # Validate contradicting evidence
        for eid in raw.contradicting_evidence_ids:
            if eid in registry:
                contradicting.append(registry[eid])
            else:
                rejected.append(eid)
                total_rejected += 1

        # Verification classification
        if not rejected and len(supporting) > 0:
            status = "verified"
        elif len(supporting) > 0 and len(rejected) > 0:
            status = "partially_verified"
        else:
            status = "unverified"

        verified_hypotheses.append(
            VerifiedHypothesis(
                id=raw.id,
                title=raw.title,
                statement=raw.statement,
                suspected_entity=raw.suspected_entity,
                confidence=raw.confidence,
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                rejected_evidence_ids=rejected,
                recommended_action=raw.recommended_action,
                verification_status=status,
            )
        )

    # Compile missing evidence warnings
    missing_notes = []
    if not context.evidence_summary.get("is_sufficient_evidence", True):
        missing_notes.append("Incident exhibits limited statistical observations; hypotheses carry high epistemic uncertainty.")
    if context.topology.missing_relationships_detected:
        missing_notes.extend(context.topology.missing_relationships_detected)

    return HypothesisGenerationResponse(
        incident_id=context.incident.id,
        provider=provider_name,
        model_name=model_name,
        is_fallback=is_fallback,
        hypotheses=verified_hypotheses,
        rejected_evidence_total=total_rejected,
        missing_evidence_notes=missing_notes,
        reasoning_summary=raw_output.reasoning_summary,
    )


async def execute_hypothesis_generation_workflow(
    context: InvestigationContextResponse,
) -> HypothesisGenerationResponse:
    """Executes the full LLM hypothesis generation and verification pipeline with automatic fallback."""
    provider = get_llm_provider()
    provider_name = provider.__class__.__name__

    try:
        raw_output, model_name, is_fallback = await provider.generate_hypotheses(context)
    except Exception as exc:
        logger.warning(f"Primary LLM provider {provider_name} failed: {exc}. Falling back to deterministic rules.")
        raw_output = generate_deterministic_fallback_hypotheses(context)
        model_name = "deterministic-fallback-v1"
        is_fallback = True

    return verify_hypotheses_against_graph(
        raw_output=raw_output,
        context=context,
        provider_name=provider_name,
        model_name=model_name,
        is_fallback=is_fallback,
    )
