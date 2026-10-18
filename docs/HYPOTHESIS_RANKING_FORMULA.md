# TraceForge Deterministic Hypothesis Ranking Specification

TraceForge uses an explicit, additive-penalty scoring function with bounded clamping.
This replaces arbitrary LLM confidence scores with an independently testable, audit-ready engineering metric.

---

## 1. Score Calculation Formula

$$\text{Final Score} = \max\left(0.05, \min\left(0.95, \text{Base} + \sum \text{Factors}\right)\right)$$

Where:
$$\text{Base} = 0.30$$ (neutral prior)

### Scoring Factors & Calibrated Weights

| Factor | Weight Range | Condition / Evaluation Logic |
| :--- | :---: | :--- |
| **`verified_supporting_evidence`** | $+0.12$ per unique item (max $+0.36$) | Deduplicated telemetry (Alerts, Metrics, Deployments) confirmed in FalkorDB. |
| **`contradicting_evidence_penalty`**| $-0.25$ per unique item (max $-0.50$) | Facts directly conflicting with the hypothesis (e.g. error rate isolated elsewhere, metrics normal). |
| **`temporal_consistency`** | $+0.15$ or $-0.20$ | $+0.15$ if deployment/anomaly occurred $0 - 5$ mins prior to incident start; $-0.20$ if event happened after incident began or $>60$ mins prior. |
| **`topological_causal_path`** | $+0.15$ | A directed `DEPENDS_ON` path exists in FalkorDB linking the suspected entity to the affected service. |
| **`historical_precedent`** | $+0.10$ | A past incident on the same entity was successfully resolved with documented mitigation. |
| **`hallucination_penalty`** | $-0.15$ per rejected ID | Referenced evidence IDs that do not exist in the graph database. |
| **`epistemic_abstention_penalty`** | $-0.20$ | Applied if the incident has fewer than 2 total verified observations (incomplete evidence). |

---

## 2. Confidence & Epistemic Verdicts

Scores are **not** treated as Bayesian probabilities. Instead, hypotheses are categorized into qualitative verdicts:

- **`HIGH_CONFIDENCE_ROOT_CAUSE`** ($\ge 0.75$): Strong multi-source graph evidence, causal dependency path confirmed, and zero contradictions.
- **`PLAUSIBLE_CONTRIBUTOR`** ($0.50 - 0.74$): Supporting evidence exists, but path is indirect or historical precedent is missing.
- **`WEAK_OR_MISLEADING`** ($0.25 - 0.49$): Substantial contradicting evidence or misleading temporal correlation.
- **`INCONCLUSIVE_INSUFFICIENT_DATA`** ($< 0.25$ or abstained): Insufficient telemetry to justify a conclusion.

---

## 3. Persistent FalkorDB Schema Updates

Investigations and scored hypotheses are persisted to FalkorDB using:
```cypher
MATCH (inc:Incident {id: $incident_id})
MERGE (inv:Investigation {id: $investigation_id})
ON CREATE SET inv.status = 'completed', inv.ranked_at = $timestamp
MERGE (inv)-[:INVESTIGATES]->(inc)

MERGE (h:Hypothesis {id: $hypothesis_id})
ON CREATE SET h.title = $title,
              h.statement = $statement,
              h.suspected_entity = $entity,
              h.score = $score,
              h.rank = $rank,
              h.verdict = $verdict
MERGE (inv)-[:RANKS_HYPOTHESIS {rank: $rank, score: $score}]->(h)
```
Evidence associations:
```cypher
MATCH (h:Hypothesis {id: $hypothesis_id})
MATCH (e {id: $evidence_id})
MERGE (h)-[:SUPPORTED_BY]->(e)
```
```cypher
MATCH (h:Hypothesis {id: $hypothesis_id})
MATCH (e {id: $evidence_id})
MERGE (h)-[:CONTRADICTED_BY]->(e)
```
