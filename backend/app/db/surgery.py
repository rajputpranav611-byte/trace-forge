import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional
from app.db.client import db_client
from app.core.config import get_settings
from app.db.investigation import build_investigation_context
from app.db.queries import find_downstream_dependents
from app.core.llm.verifier import execute_hypothesis_generation_workflow
from app.core.ranking.engine import rank_hypotheses
from app.schemas.surgery import (
    CreateExperimentRequest,
    ExperimentStateSummary,
    GraphSurgeryAction,
    HypothesisDiff,
    ScoreFactorDiff,
    BlastRadiusDiff,
    CounterfactualComparisonResponse,
)
from app.schemas.ranking import RankedInvestigationResponse

logger = logging.getLogger("traceforge.surgery")


def create_isolated_experiment(req: CreateExperimentRequest) -> ExperimentStateSummary:
    """Creates a byte-for-byte isolated FalkorDB graph copy from the baseline graph

    and applies strictly validated, parameterized graph surgery operations.
    Never modifies the baseline graph.
    """
    settings = get_settings()
    baseline_graph_name = settings.FALKORDB_GRAPH_NAME
    experiment_id = f"exp_{uuid.uuid4().hex[:8]}"
    experiment_graph_name = f"traceforge_{experiment_id}"

    client = db_client.get_client()
    baseline_graph = client.select_graph(baseline_graph_name)

    logger.info(f"Cloning baseline graph '{baseline_graph_name}' to experiment '{experiment_graph_name}'")
    exp_graph = None
    for attempt in range(3):
        try:
            exp_graph = baseline_graph.copy(experiment_graph_name)
            break
        except Exception as e:
            if "could not fork" in str(e).lower() and attempt < 2:
                import time
                time.sleep(0.5)
                continue
            raise

    modified_elements: List[Dict[str, Any]] = []

    # Execute strictly parameterized surgical actions (NO arbitrary Cypher permitted)
    for action in req.actions:
        if action.action_type == "remove_dependency":
            # Check source and target existence first
            src_check = exp_graph.query("MATCH (s:Service {id: $source_id}) RETURN s.id", {"source_id": action.source_id})
            if not src_check.result_set:
                cleanup_experiment(experiment_id)
                raise ValueError(f"Source service '{action.source_id}' does not exist in graph")

            if not action.target_id:
                cleanup_experiment(experiment_id)
                raise ValueError("target_id is required for action_type 'remove_dependency'")

            tgt_check = exp_graph.query("MATCH (t:Service {id: $target_id}) RETURN t.id", {"target_id": action.target_id})
            if not tgt_check.result_set:
                cleanup_experiment(experiment_id)
                raise ValueError(f"Target service '{action.target_id}' does not exist in graph")

            # Parameterized Cypher to remove specific directed relationship
            rel_type = action.relationship_type or "DEPENDS_ON"
            if rel_type not in ["DEPENDS_ON", "AFFECTS", "PRODUCES_ALERT", "DEPLOYED_TO"]:
                cleanup_experiment(experiment_id)
                raise ValueError(f"Disallowed relationship type for removal: {rel_type}")

            query = f"""
            MATCH (s:Service {{id: $source_id}})-[r:{rel_type}]->(t:Service {{id: $target_id}})
            DELETE r
            RETURN count(r) AS deleted_count
            """
            res = exp_graph.query(query, {"source_id": action.source_id, "target_id": action.target_id})
            deleted = res.result_set[0][0] if res.result_set else 0
            if deleted == 0:
                cleanup_experiment(experiment_id)
                raise ValueError(
                    f"Relationship ({action.source_id})-[:{rel_type}]->({action.target_id}) does not exist in graph"
                )

            modified_elements.append({
                "action": action.action_type,
                "source_id": action.source_id,
                "target_id": action.target_id,
                "relationship_type": rel_type,
                "deleted_count": deleted,
                "justification": action.justification,
            })

        elif action.action_type == "remove_evidence":
            # Check evidence node existence
            ev_check = exp_graph.query("MATCH (e:Evidence {id: $source_id}) RETURN e.id", {"source_id": action.source_id})
            if not ev_check.result_set:
                cleanup_experiment(experiment_id)
                raise ValueError(f"Evidence node '{action.source_id}' does not exist in graph")

            # Sever evidence relationship or delete evidence node from experiment graph
            query = """
            MATCH (e:Evidence {id: $source_id})
            DETACH DELETE e
            RETURN count(e) AS deleted_count
            """
            res = exp_graph.query(query, {"source_id": action.source_id})
            deleted = res.result_set[0][0] if res.result_set else 0
            modified_elements.append({
                "action": action.action_type,
                "evidence_id": action.source_id,
                "deleted_count": deleted,
                "justification": action.justification,
            })

        elif action.action_type == "isolate_service":
            # Check service existence
            svc_check = exp_graph.query("MATCH (s:Service {id: $source_id}) RETURN s.id", {"source_id": action.source_id})
            if not svc_check.result_set:
                cleanup_experiment(experiment_id)
                raise ValueError(f"Service '{action.source_id}' does not exist in graph")

            # Remove all incoming and outgoing DEPENDS_ON relationships for the service
            query = """
            MATCH (s:Service {id: $source_id})-[r:DEPENDS_ON]-()
            DELETE r
            RETURN count(r) AS deleted_count
            """
            res = exp_graph.query(query, {"source_id": action.source_id})
            deleted = res.result_set[0][0] if res.result_set else 0
            modified_elements.append({
                "action": action.action_type,
                "service_id": action.source_id,
                "deleted_count": deleted,
                "justification": action.justification,
            })

        elif action.action_type == "rollback_deployment":
            # Check deployment existence
            dep_check = exp_graph.query("MATCH (d:Deployment {id: $source_id}) RETURN d.id", {"source_id": action.source_id})
            if not dep_check.result_set:
                cleanup_experiment(experiment_id)
                raise ValueError(f"Deployment '{action.source_id}' does not exist in graph")

            # Remove DEPLOYED_TO relationship between deployment and service
            query = """
            MATCH (d:Deployment {id: $source_id})-[r:DEPLOYED_TO]->(s:Service)
            DELETE r
            RETURN count(r) AS deleted_count
            """
            res = exp_graph.query(query, {"source_id": action.source_id})
            deleted = res.result_set[0][0] if res.result_set else 0
            modified_elements.append({
                "action": action.action_type,
                "deployment_id": action.source_id,
                "deleted_count": deleted,
                "justification": action.justification,
            })
        else:
            cleanup_experiment(experiment_id)
            raise ValueError(f"Unsupported surgery action type: {action.action_type}")

    # Inspect experiment graph node and edge counts
    node_count_res = exp_graph.query("MATCH (n) RETURN count(n) AS cnt")
    edge_count_res = exp_graph.query("MATCH ()-[r]->() RETURN count(r) AS cnt")
    total_nodes = node_count_res.result_set[0][0] if node_count_res.result_set else 0
    total_edges = edge_count_res.result_set[0][0] if edge_count_res.result_set else 0

    return ExperimentStateSummary(
        experiment_id=experiment_id,
        experiment_name=req.experiment_name,
        baseline_incident_id=req.baseline_incident_id,
        graph_name=experiment_graph_name,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        applied_actions=req.actions,
        total_nodes=total_nodes,
        total_edges=total_edges,
        modified_elements=modified_elements,
    )


def cleanup_experiment(experiment_id: str) -> bool:
    """Safely drops the isolated experiment graph from FalkorDB.

    Ensures baseline graph is never deleted.
    """
    settings = get_settings()
    baseline = settings.FALKORDB_GRAPH_NAME
    graph_name = f"traceforge_{experiment_id}" if not experiment_id.startswith("traceforge_") else experiment_id

    if graph_name == baseline:
        raise ValueError("CRITICAL: Cannot delete baseline graph!")

    client = db_client.get_client()
    try:
        exp_graph = client.select_graph(graph_name)
        exp_graph.delete()
        logger.info(f"Cleaned up experiment graph '{graph_name}'")
        return True
    except Exception as exc:
        logger.warning(f"Failed or already deleted experiment graph '{graph_name}': {exc}")
        return False


async def run_investigation_on_graph(
    incident_id: str,
    graph_name: Optional[str] = None,
) -> RankedInvestigationResponse:
    """Executes the full real investigation pipeline (context extraction + hypothesis verification + ranking)

    against a specific graph (baseline or experiment).
    """
    context = build_investigation_context(incident_id=incident_id, graph_name=graph_name)
    if not context:
        raise ValueError(f"Incident '{incident_id}' not found in graph '{graph_name or 'baseline'}'")

    verified_resp = await execute_hypothesis_generation_workflow(context)
    ranked_list, abstained, unresolved = rank_hypotheses(verified_resp.hypotheses, context)

    top_hyp = ranked_list[0] if ranked_list else None
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    explanation = (
        f"Evaluated {len(ranked_list)} competing hypotheses on graph '{graph_name or 'baseline'}'. "
        f"Top candidate '{top_hyp.id if top_hyp else 'None'}' scored {top_hyp.deterministic_score if top_hyp else 0.0}."
    )

    return RankedInvestigationResponse(
        investigation_id=f"SURG-{incident_id}-{uuid.uuid4().hex[:6].upper()}",
        incident_id=incident_id,
        ranked_at=now_iso,
        abstained=abstained,
        top_hypothesis=top_hyp,
        hypotheses=ranked_list,
        unresolved_questions=unresolved,
        graph_persistence_status="ephemeral",
        explanation=explanation,
    )


async def execute_counterfactual_comparison(
    req: CreateExperimentRequest,
) -> CounterfactualComparisonResponse:
    """1. Runs baseline investigation.

    2. Instantiates isolated FalkorDB graph copy.
    3. Applies validated graph surgery.
    4. Runs identical investigation on experiment graph.
    5. Computes structured diffs: ranks, scores, causal paths, blast radius, evidence.
    6. Produces causal explanation and cleans up or preserves experiment state.
    """
    # 1. Baseline investigation
    baseline_inv = await run_investigation_on_graph(req.baseline_incident_id, graph_name=None)

    # 2. Setup experiment graph & apply surgery
    exp_summary = create_isolated_experiment(req)
    exp_graph_name = exp_summary.graph_name

    try:
        # 3. Experiment investigation on genuinely modified graph
        exp_inv = await run_investigation_on_graph(req.baseline_incident_id, graph_name=exp_graph_name)

        # 4. Compare hypothesis rankings and score contributions
        baseline_map = {h.id: h for h in baseline_inv.hypotheses}
        experiment_map = {h.id: h for h in exp_inv.hypotheses}

        hypothesis_diffs: List[HypothesisDiff] = []
        all_ids = list(dict.fromkeys(list(baseline_map.keys()) + list(experiment_map.keys())))

        for hid in all_ids:
            b_hyp = baseline_map.get(hid)
            e_hyp = experiment_map.get(hid)

            b_rank = b_hyp.rank if b_hyp else None
            e_rank = e_hyp.rank if e_hyp else None
            b_score = b_hyp.deterministic_score if b_hyp else None
            e_score = e_hyp.deterministic_score if e_hyp else None
            score_delta = round((e_score or 0.0) - (b_score or 0.0), 4)

            causal_path_changed = False
            if b_hyp and e_hyp:
                causal_path_changed = (b_hyp.causal_path != e_hyp.causal_path) or (b_hyp.causal_path_found != e_hyp.causal_path_found)

            # Evidence diff summary
            b_supp = set(b_hyp.supporting_evidence_ids) if b_hyp else set()
            e_supp = set(e_hyp.supporting_evidence_ids) if e_hyp else set()
            newly_missing = b_supp - e_supp
            newly_added = e_supp - b_supp

            diff_parts = []
            if newly_missing:
                diff_parts.append(f"Severed evidence: {', '.join(newly_missing)}")
            if newly_added:
                diff_parts.append(f"Newly correlated evidence: {', '.join(newly_added)}")
            if not diff_parts:
                diff_parts.append("Evidence relationships identical")

            # Factor diffs breakdown
            b_factors = {f.name: f for f in (b_hyp.score_factors if b_hyp else [])}
            e_factors = {f.name: f for f in (e_hyp.score_factors if e_hyp else [])}
            all_factor_names = list(dict.fromkeys(list(b_factors.keys()) + list(e_factors.keys())))

            factor_diffs: List[ScoreFactorDiff] = []
            delta_reasons: List[str] = []

            for fname in all_factor_names:
                bf = b_factors.get(fname)
                ef = e_factors.get(fname)
                b_contrib = bf.contribution if bf else 0.0
                e_contrib = ef.contribution if ef else 0.0
                f_delta = round(e_contrib - b_contrib, 4)

                b_reason = bf.reason if bf else "Factor not present in baseline"
                e_reason = ef.reason if ef else "Factor not present in experiment"

                if abs(f_delta) > 0.001 or b_reason != e_reason:
                    factor_diffs.append(ScoreFactorDiff(
                        factor_name=fname,
                        baseline_contribution=b_contrib,
                        experiment_contribution=e_contrib,
                        contribution_delta=f_delta,
                        baseline_reason=b_reason,
                        experiment_reason=e_reason,
                    ))

                if abs(f_delta) > 0.001:
                    delta_reasons.append(
                        f"{fname.replace('_', ' ').title()} shifted by {f_delta:+.2f} ({e_reason})"
                    )

            if not delta_reasons:
                if score_delta == 0.0:
                    score_delta_explanation = "Deterministic score factors remained identical under this graph intervention."
                else:
                    score_delta_explanation = f"Score delta of {score_delta:+.2f} reflects clamping adjustments."
            else:
                score_delta_explanation = "; ".join(delta_reasons)

            hypothesis_diffs.append(HypothesisDiff(
                hypothesis_id=hid,
                title=b_hyp.title if b_hyp else (e_hyp.title if e_hyp else hid),
                baseline_rank=b_rank,
                experiment_rank=e_rank,
                baseline_score=b_score,
                experiment_score=e_score,
                score_delta=score_delta,
                baseline_verdict=b_hyp.verdict if b_hyp else None,
                experiment_verdict=e_hyp.verdict if e_hyp else None,
                causal_path_changed=causal_path_changed,
                evidence_diff_summary="; ".join(diff_parts),
                score_delta_explanation=score_delta_explanation,
                factor_diffs=factor_diffs,
            ))

        # 5. Blast-radius comparison on the target/suspected service
        target_service = req.actions[0].source_id
        if req.actions[0].target_id and req.actions[0].action_type == "remove_dependency":
            target_service = req.actions[0].target_id

        baseline_blast = find_downstream_dependents(target_service, max_depth=3, graph_name=None)
        exp_blast = find_downstream_dependents(target_service, max_depth=3, graph_name=exp_graph_name)

        b_nodes = {n["id"] for n in baseline_blast.get("nodes", [])}
        e_nodes = {n["id"] for n in exp_blast.get("nodes", [])}
        severed = list(b_nodes - e_nodes)
        added = list(e_nodes - b_nodes)

        blast_diff = BlastRadiusDiff(
            service_id=target_service,
            baseline_downstream_count=len(b_nodes),
            experiment_downstream_count=len(e_nodes),
            severed_services=severed,
            added_services=added,
        )

        # 6. Synthesize causal explanation of differences
        action_descriptions = [
            f"{a.action_type.replace('_', ' ').upper()} ({a.source_id} -> {a.target_id or ''}): '{a.justification}'"
            for a in req.actions
        ]

        top_shift = ""
        b_top = baseline_inv.top_hypothesis
        e_top = exp_inv.top_hypothesis
        if b_top and e_top:
            if b_top.id != e_top.id:
                top_shift = f"Rank 1 shifted from '{b_top.title}' (score {b_top.deterministic_score}) to '{e_top.title}' (score {e_top.deterministic_score}). "
            else:
                top_shift = f"Rank 1 remained '{b_top.title}', with score delta {round(e_top.deterministic_score - b_top.deterministic_score, 4)}. "

        blast_shift = f"Blast radius for '{target_service}' contracted by {len(severed)} downstream services ({', '.join(severed) if severed else 'none'})."

        causal_explanation = (
            f"Under the counterfactual assumption where {'; '.join(action_descriptions)}, the graph topology was isolated and re-analyzed. "
            f"{top_shift}{blast_shift} "
            f"This validates how topological dependency paths propagate failure modes through the operational graph."
        )

        return CounterfactualComparisonResponse(
            experiment_id=exp_summary.experiment_id,
            experiment_name=req.experiment_name,
            baseline_incident_id=req.baseline_incident_id,
            created_at=exp_summary.created_at,
            actions_applied=req.actions,
            causal_change_explanation=causal_explanation,
            hypothesis_diffs=hypothesis_diffs,
            blast_radius_diff=blast_diff,
            baseline_investigation=baseline_inv,
            experiment_investigation=exp_inv,
            disclaimer="Controlled graph counterfactual under explicit assumptions. Not a real-world causal proof.",
        )
    finally:
        # Note: clean up experiment graph after run, or caller can retain
        cleanup_experiment(exp_summary.experiment_id)
