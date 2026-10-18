import logging
import datetime
from typing import List, Optional
from app.db.client import db_client
from app.schemas.ranking import ScoredHypothesis, RankedInvestigationResponse

logger = logging.getLogger("traceforge.persistence")


def persist_ranked_investigation(
    investigation_id: str,
    incident_id: str,
    scored_hypotheses: List[ScoredHypothesis],
    abstained: bool,
    unresolved_questions: List[str],
    graph_name: Optional[str] = None,
) -> bool:
    """Persists investigation ranking results and evidence links directly into FalkorDB."""
    try:
        graph = db_client.get_graph(graph_name)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 1. Upsert Investigation Node linked to Incident
        inv_query = """
        MATCH (inc:Incident {id: $incident_id})
        MERGE (inv:Investigation {id: $inv_id})
        ON CREATE SET inv.status = 'ranked',
                      inv.ranked_at = $ranked_at,
                      inv.abstained = $abstained
        ON MATCH SET  inv.status = 'ranked',
                      inv.ranked_at = $ranked_at,
                      inv.abstained = $abstained
        MERGE (inv)-[:INVESTIGATES]->(inc)
        """
        graph.query(inv_query, {
            "incident_id": incident_id,
            "inv_id": investigation_id,
            "ranked_at": now_iso,
            "abstained": abstained,
        })

        # 2. Upsert Scored Hypotheses and Relationships
        for hyp in scored_hypotheses:
            hyp_query = """
            MATCH (inv:Investigation {id: $inv_id})
            MERGE (h:Hypothesis {id: $hyp_id})
            ON CREATE SET h.title = $title,
                          h.statement = $statement,
                          h.suspected_entity = $entity,
                          h.score = $score,
                          h.rank = $rank,
                          h.verdict = $verdict
            ON MATCH SET  h.title = $title,
                          h.statement = $statement,
                          h.suspected_entity = $entity,
                          h.score = $score,
                          h.rank = $rank,
                          h.verdict = $verdict
            MERGE (inv)-[r:RANKS_HYPOTHESIS]->(h)
            ON CREATE SET r.rank = $rank, r.score = $score
            ON MATCH SET  r.rank = $rank, r.score = $score
            """
            graph.query(hyp_query, {
                "inv_id": investigation_id,
                "hyp_id": f"{investigation_id}-{hyp.id}",
                "title": hyp.title,
                "statement": hyp.statement,
                "entity": hyp.suspected_entity,
                "score": hyp.deterministic_score,
                "rank": hyp.rank,
                "verdict": hyp.verdict,
            })

            # Link supporting evidence
            for eid in hyp.supporting_evidence_ids:
                supp_query = """
                MATCH (h:Hypothesis {id: $hyp_id})
                MATCH (e {id: $eid})
                MERGE (h)-[:SUPPORTED_BY]->(e)
                """
                graph.query(supp_query, {
                    "hyp_id": f"{investigation_id}-{hyp.id}",
                    "eid": eid,
                })

            # Link contradicting evidence
            for eid in hyp.contradicting_evidence_ids:
                contra_query = """
                MATCH (h:Hypothesis {id: $hyp_id})
                MATCH (e {id: $eid})
                MERGE (h)-[:CONTRADICTED_BY]->(e)
                """
                graph.query(contra_query, {
                    "hyp_id": f"{investigation_id}-{hyp.id}",
                    "eid": eid,
                })

        logger.info(f"Persisted investigation {investigation_id} with {len(scored_hypotheses)} hypotheses to FalkorDB.")
        return True
    except Exception as exc:
        logger.error(f"Failed to persist ranked investigation to FalkorDB: {exc}")
        return False
