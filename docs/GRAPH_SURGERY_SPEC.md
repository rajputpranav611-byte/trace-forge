# TraceForge Feature Specification: Graph Surgery — Counterfactual Incident Simulator

> **Framing Disclaimer**:
> *"Controlled graph counterfactual under explicit assumptions. Not a real-world causal proof."*

---

## 1. Architectural Overview & Graph Isolation

TraceForge's signature feature, **Graph Surgery**, empowers incident responders and site reliability engineers to simulate counterfactual "what-if" topological interventions against active or historical incidents.

Crucially, **Graph Surgery is never a visual mockup or cosmetic state filter**. Every counterfactual simulation runs the full real TraceForge investigation, topological path traversal, and deterministic hypothesis ranking pipeline against a genuinely modified, isolated FalkorDB graph copy.

```
                           +----------------------------+
                           |  Baseline Graph Store      |
                           |  (FalkorDB: 'traceforge')  |
                           +--------------+-------------+
                                          |
                              graph.copy('traceforge_exp_<id>')
                                          v
                           +----------------------------+
                           |  Isolated Experiment Graph |
                           |  'traceforge_exp_<id>'     |
                           +--------------+-------------+
                                          |
                        Execute Validated Surgical Cypher
                         (e.g. Sever DEPENDS_ON Edge)
                                          v
+----------------------------+            +----------------------------+
| Baseline Investigation Context          | Experiment Investigation Context
| & Deterministic Ranking Engine          | & Deterministic Ranking Engine
+--------------+-------------+            +--------------+-------------+
               \                                        /
                \--> Compute Multi-Dimensional Diff <--/
                     - Hypothesis Rankings & Scores
                     - Downstream Blast Radius Contraction
                     - Severed Causal Dependency Paths
                     - Evidence Corroboration & Runbooks
                                   |
                                   v
             Cleanly Drop Experiment Graph (exp_g.delete())
                [Baseline Graph Remained 100% Untouched]
```

---

## 2. Graph Isolation Mechanism

FalkorDB provides atomic, instant in-memory graph duplication via `base_graph.copy(target_name)`.

1. **Isolation Guarantee**: The experiment graph `traceforge_exp_<uuid>` is created with zero impact on the baseline dataset `traceforge`.
2. **Immutable Baseline**: The baseline graph is queried in read-only mode (`ro_query`) or copied via engine primitives. No `DELETE` or `SET` statements are ever executed against the baseline during an experiment.
3. **Reproducibility**: Each experiment logs its parameters, base incident ID, and the exact sequence of surgical actions.
4. **Automatic Ephemeral Cleanup**: Following counterfactual comparison, `exp_graph.delete()` cleanly deallocates the isolated graph. Guardrails prevent deletion of the baseline graph.

---

## 3. Supported Surgical Actions (Strictly Typed & Validated)

To preserve safety and eliminate security hazards, **arbitrary model-generated Cypher is strictly banned**. All surgery requests are restricted to validated Pydantic schemas:

| Action Type | Parameters | Target Cypher Template | Purpose |
| :--- | :--- | :--- | :--- |
| `remove_dependency` | `source_id`, `target_id`, `relationship_type` | `MATCH (s:Service {id: $s})-[r:DEPENDS_ON]->(t:Service {id: $t}) DELETE r` | Simulate severed network path or circuit-breaker |
| `isolate_service` | `source_id` | `MATCH (s:Service {id: $s})-[r:DEPENDS_ON]-() DELETE r` | Simulate total isolation of a degraded cluster |
| `rollback_deployment` | `source_id` (Deployment ID) | `MATCH (d:Deployment {id: $s})-[r:DEPLOYED_TO]->(s:Service) DELETE r` | Simulate counterfactual rollback of a candidate release |
| `remove_evidence` | `source_id` (Evidence ID) | `MATCH (e:Evidence {id: $s}) DETACH DELETE e` | Test whether an alert was spurious or misleading |

---

## 4. Multi-Dimensional Counterfactual Comparison

When a counterfactual is simulated, TraceForge executes `build_investigation_context` and `rank_hypotheses` on both graphs and computes:

1. **Hypothesis Ranking Shifts**:
   - Compares baseline rank and deterministic score against experiment rank and score.
   - Detects when a #1 root cause drops to a lower rank (e.g. `payment-db-cluster` drops from Rank 1 `0.95` to Rank 2 `0.71` when its dependency from `payment-core` is severed).
2. **Causal Dependency Paths**:
   - Identifies if the topological directed path from the affected incident service to the suspected entity was broken (`causal_path_changed = true`).
3. **Blast Radius Contraction**:
   - Computes multi-hop downstream impact `(dependent)-[:DEPENDS_ON*1..3]->(target)`.
   - Explains which downstream services are unblocked by the topological intervention (e.g., blast radius contracts from 6 services down to 3 services).
4. **Causal Synthesis**:
   - Automatically generates a transparent explanation of the shift:
     > *"Under the counterfactual assumption where REMOVE DEPENDENCY (payment-core -> payment-db-cluster)... Rank 1 shifted from 'Database Connection Pool Starvation & Saturation' (0.95) to 'Uncataloged Dependency or External Transit Degradation' (0.81). Blast radius for 'payment-db-cluster' contracted by 3 downstream services (payment-core, checkout-orchestrator, nexus-api-gateway)."*

---

## 5. Verification & Test Suite

The test suite in [`backend/tests/test_surgery.py`](file:///f:/SessionSmith/backend/tests/test_surgery.py) validates all 4 safety requirements:

1. `test_baseline_remains_unchanged_after_experiment`: Confirms exact node and edge count equality on the baseline graph before and after surgery.
2. `test_relevant_relationship_change_alters_investigation_result`: Confirms that severing `payment-core -> payment-db-cluster` alters the ranking score and contracts the blast radius.
3. `test_unrelated_graph_changes_do_not_arbitrarily_alter_results`: Confirms that severing an unrelated cache edge (`auth-service -> redis-session-store`) preserves the target incident ranking for `INC-2026-9043`.
4. `test_failed_experiment_cannot_corrupt_baseline`: Confirms that malicious or unsupported relationship actions return HTTP 400 and preserve the baseline.
