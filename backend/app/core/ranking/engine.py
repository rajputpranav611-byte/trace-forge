import datetime
from typing import List, Dict, Any, Tuple, Optional
from app.schemas.investigation import InvestigationContextResponse
from app.schemas.hypotheses import VerifiedHypothesis
from app.schemas.ranking import ScoredHypothesis, ScoreFactor, RankedInvestigationResponse


def evaluate_temporal_consistency(
    hypothesis: VerifiedHypothesis,
    context: InvestigationContextResponse,
) -> Tuple[float, str]:
    """Evaluates whether candidate entity events (like deployments) occurred in plausible causal proximity to incident start."""
    inc_time_str = context.incident.started_at
    try:
        inc_dt = datetime.datetime.fromisoformat(inc_time_str.replace("Z", "+00:00"))
    except Exception:
        return 0.0, "Could not parse incident timestamp"

    # Check deployments associated with the suspected entity
    matching_deps = [d for d in context.deployments if d.service_id == hypothesis.suspected_entity or d.id in [e.id for e in hypothesis.supporting_evidence]]

    if matching_deps:
        dep = matching_deps[0]
        try:
            dep_dt = datetime.datetime.fromisoformat(dep.deployed_at.replace("Z", "+00:00"))
            delta_mins = (inc_dt - dep_dt).total_seconds() / 60.0

            if 0.0 <= delta_mins <= 5.0:
                return 0.15, f"Deployment {dep.id} on {dep.service_name} occurred {delta_mins:.1f}m prior to incident (optimal causal window)"
            elif 5.0 < delta_mins <= 30.0:
                return 0.08, f"Deployment {dep.id} occurred {delta_mins:.1f}m prior to incident"
            elif delta_mins < 0:
                return -0.20, f"Deployment {dep.id} occurred {abs(delta_mins):.1f}m AFTER incident started (cannot be root cause)"
            else:
                return -0.05, f"Deployment {dep.id} occurred {delta_mins:.1f}m prior (weak temporal relevance)"
        except Exception:
            pass

    return 0.0, "No temporal deployment events tied to suspected entity"


def find_causal_path(
    suspected_entity: str,
    context: InvestigationContextResponse,
) -> Tuple[bool, List[str]]:
    """Checks if there is a directed path in the traversed subgraph from affected services to the suspected entity."""
    affected_ids = [s.id for s in context.topology.affected_services]
    if suspected_entity in affected_ids:
        return True, [suspected_entity]

    # Inspect traversed paths
    for p in context.topology.traversed_paths:
        if suspected_entity in p.node_ids:
            return True, p.node_ids

    # Inspect edges directly
    for e in context.topology.dependency_edges:
        if e.target == suspected_entity:
            return True, [e.source, e.target]

    return False, []


def score_hypothesis(
    hyp: VerifiedHypothesis,
    context: InvestigationContextResponse,
) -> ScoredHypothesis:
    """Calculates deterministic score and builds factor explanation breakdown."""
    factors: List[ScoreFactor] = []
    base_score = 0.30

    # 1. Deduplicated Verified Supporting Evidence
    unique_supp = {e.id: e for e in hyp.supporting_evidence}
    supp_count = len(unique_supp)
    supp_bonus = min(0.36, supp_count * 0.12)
    factors.append(ScoreFactor(
        name="verified_supporting_evidence",
        contribution=round(supp_bonus, 2),
        reason=f"Found {supp_count} verified graph evidence item(s): {', '.join(unique_supp.keys()) or 'None'}",
    ))

    # 2. Contradicting Evidence Penalty
    unique_contra = {e.id: e for e in hyp.contradicting_evidence}
    contra_count = len(unique_contra)
    contra_penalty = -min(0.50, contra_count * 0.25)
    factors.append(ScoreFactor(
        name="contradicting_evidence",
        contribution=round(contra_penalty, 2),
        reason=f"Found {contra_count} contradicting fact(s): {', '.join(unique_contra.keys()) or 'None'}",
    ))

    # 3. Temporal Consistency
    temporal_contrib, temporal_reason = evaluate_temporal_consistency(hyp, context)
    factors.append(ScoreFactor(
        name="temporal_consistency",
        contribution=round(temporal_contrib, 2),
        reason=temporal_reason,
    ))

    # 4. Topological Causal Path
    path_found, path_nodes = find_causal_path(hyp.suspected_entity, context)
    path_contrib = 0.15 if path_found else -0.10
    factors.append(ScoreFactor(
        name="topological_causal_path",
        contribution=round(path_contrib, 2),
        reason=f"Directed dependency path {'confirmed: ' + ' -> '.join(path_nodes) if path_found else 'NOT found in service graph'}",
    ))

    # 5. Historical Incident Precedent
    hist_match = [h for h in context.historical_incidents if h.service_id == hyp.suspected_entity]
    hist_contrib = 0.10 if hist_match else 0.0
    factors.append(ScoreFactor(
        name="historical_precedent",
        contribution=round(hist_contrib, 2),
        reason=f"{'Matching historical precedent ' + hist_match[0].id + ' found' if hist_match else 'No matching historical incident'}",
    ))

    # 6. Hallucination / Unknown Evidence Penalty
    rej_count = len(hyp.rejected_evidence_ids)
    rej_penalty = -round(rej_count * 0.15, 2)
    factors.append(ScoreFactor(
        name="hallucination_penalty",
        contribution=rej_penalty,
        reason=f"{rej_count} unverifiable evidence ID(s) rejected: {', '.join(hyp.rejected_evidence_ids) or 'None'}",
    ))

    # 7. Epistemic Abstention Penalty (Sparse/incomplete telemetry)
    is_sufficient = context.evidence_summary.get("is_sufficient_evidence", True)
    abstain_penalty = -0.20 if not is_sufficient else 0.0
    factors.append(ScoreFactor(
        name="epistemic_abstention_penalty",
        contribution=abstain_penalty,
        reason="Incident observations are sparse/insufficient to support confident causal attribution" if not is_sufficient else "Telemetry observation coverage is sufficient",
    ))

    # Calculate clamped final score
    raw_total = base_score + sum(f.contribution for f in factors)
    deterministic_score = round(max(0.05, min(0.95, raw_total)), 2)

    # Determine qualitative verdict
    if not is_sufficient:
        verdict = "INCONCLUSIVE_INSUFFICIENT_DATA"
    elif contra_count > 0 or deterministic_score < 0.50:
        verdict = "WEAK_OR_MISLEADING"
    elif deterministic_score >= 0.75:
        verdict = "HIGH_CONFIDENCE_ROOT_CAUSE"
    else:
        verdict = "PLAUSIBLE_CONTRIBUTOR"

    # Identify unresolved questions
    unresolved: List[str] = []
    if contra_count > 0:
        unresolved.append(f"How can {hyp.title} be reconciled with contradicting observations ({', '.join(unique_contra.keys())})?")
    if not path_found:
        unresolved.append(f"Is there an uncataloged runtime dependency linking affected services to {hyp.suspected_entity}?")
    if not is_sufficient:
        unresolved.append("Telemetry observation window is too short or missing key service metric monitors.")

    return ScoredHypothesis(
        rank=1,  # updated during sorting
        id=hyp.id,
        title=hyp.title,
        statement=hyp.statement,
        suspected_entity=hyp.suspected_entity,
        raw_confidence=hyp.confidence,
        deterministic_score=deterministic_score,
        verdict=verdict,
        score_factors=factors,
        supporting_evidence_ids=list(unique_supp.keys()),
        contradicting_evidence_ids=list(unique_contra.keys()),
        rejected_evidence_ids=hyp.rejected_evidence_ids,
        causal_path_found=path_found,
        causal_path=path_nodes,
        unresolved_questions=unresolved,
        recommended_action=hyp.recommended_action,
    )


def rank_hypotheses(
    hypotheses: List[VerifiedHypothesis],
    context: InvestigationContextResponse,
) -> Tuple[List[ScoredHypothesis], bool, List[str]]:
    """Scores all candidate hypotheses, sorts by deterministic score, and generates investigation questions."""
    scored: List[ScoredHypothesis] = []
    is_sparse = not context.evidence_summary.get("is_sufficient_evidence", True)

    for h in hypotheses:
        scored.append(score_hypothesis(h, context))

    # Sort descending by deterministic score
    scored.sort(key=lambda x: x.deterministic_score, reverse=True)

    # Assign 1-indexed ranks
    for idx, s in enumerate(scored):
        s.rank = idx + 1

    # Global unresolved investigation questions
    global_questions: List[str] = []
    if is_sparse:
        global_questions.append("Incident contains limited telemetry. Are additional trace spans or logs available?")
    if len(scored) >= 2 and abs(scored[0].deterministic_score - scored[1].deterministic_score) < 0.15:
        global_questions.append(f"Top candidates '{scored[0].id}' and '{scored[1].id}' are closely ranked. Run diagnostic step from runbook to differentiate.")
    if context.topology.missing_relationships_detected:
        global_questions.append("Uncataloged dependency detected. Verify runtime traces for undocumented HTTP/gRPC calls.")

    return scored, is_sparse, global_questions
