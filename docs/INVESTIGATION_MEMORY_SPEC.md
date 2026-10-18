# TraceForge Persistent Investigation Memory Architecture

## Overview

TraceForge implements persistent investigation memory backed natively by FalkorDB. The memory system stores past incident analyses, ranked hypotheses, supporting evidence, simulated actions, and operational resolutions.

When investigating an active incident, TraceForge retrieves historical operational context through graph relationships to assist operators, while strictly enforcing **epistemic guardrails** to prevent unverified claims or simulated actions from contaminating ground truth.

---

## 1. Graph Data Model & Storage

Investigations, hypotheses, and provenance are represented as directed relationships in FalkorDB:

```mermaid
graph TD
    IncCurrent((:Incident {current})) -.->|TOPOLOGICAL DEPENDENCIES| Svc((:Service))
    Svc <-.-|AFFECTS| IncHistorical((:Incident {historical}))
    IncHistorical -->|RESOLVED_BY| RecAction((:RecoveryAction))
    IncHistorical -->|HAS_RECOVERY_PROPOSAL| Proposal((:RecoveryProposal))
    Proposal -->|RESULTED_IN| SimResult((:SimulationResult))
    Inv((:Investigation)) -->|INVESTIGATES| IncHistorical
    Inv -->|RANKS_HYPOTHESIS| Hyp((:Hypothesis))
    Hyp -->|SUPPORTED_BY| Evi((:Evidence))
```

### Node Attributes & Provenance
- **`(:Investigation)`**: `id`, `status`, `ranked_at`, `abstained`, `lead_agent`.
- **`(:Hypothesis)`**: `id`, `title`, `statement`, `score`, `rank`, `verdict`.
- **`(:RecoveryAction)`**: `id`, `action_type`, `status` (`completed`), `executed_at`.
- **`(:RecoveryProposal)`**: `id`, `action_type`, `state` (`SUCCEEDED`, `APPROVED`).
- **`(:SimulationResult)`**: `id`, `success`, `executed_at`, `simulated_effects`.

---

## 2. Investigation Memory Workflow

When an operator investigates an active incident (e.g. `INC-2026-8821`):

1. **Graph-Guided Precedent Retrieval**:
   - Traverses multi-hop topology to find historical incidents linked to affected or traversed services.
   - For example: `INC-2026-8821` $\rightarrow$ `payment-core` $\rightarrow$ `event-stream-kafka` $\leftarrow$ `INC-2026-7104`.
2. **Deterministic Evidence Comparison**:
   - Identifies concrete **similarities** (e.g., overlapping service nodes, matching alert categories, correlated metrics).
   - Identifies concrete **differences** (e.g., uniquely impacted services, distinct failure symptoms).
3. **Relevance Scoring & Attribution**:
   - Computes a deterministic relevance score $[0.0, 1.0]$.
   - Generates human-readable explanation of why a case is relevant (or why an unrelated case is not).
4. **Resolution Outcome Retrieval**:
   - Distinguishes **verified operational actions** (e.g. `scale_workers` on `INC-2026-7104`) from **unverified proposals**.
5. **Runbook Prerequisite Verification**:
   - Automatically cross-checks whether active incident telemetry satisfies prerequisite steps defined in linked runbooks.

---

## 3. Epistemic Guardrails (Safety Invariants)

> [!IMPORTANT]
> **Cognitive Integrity Rules**:
> 1. **No LLM Output as Ground Truth**: Model-generated hypotheses are stamped as `UNVERIFIED_CLAIM` or `REJECTED_HYPOTHESIS`. They are never stored or presented as factual evidence without independent verification.
> 2. **Simulations $\neq$ Operational Reality**: A `SUCCEEDED` status on a simulated recovery proposal is stamped `SIMULATED_DRY_RUN`. It proves model validity in the graph, but is never assumed to be real-world production success.
> 3. **Verified Ground Truth Requirement**: Only real-world completed actions (`:RecoveryAction {status: 'completed'}`) or deterministic telemetry observations are classified as `VERIFIED_OBSERVATION`.

---

## 4. UI Interfaces

1. **Related Incidents Memory Panel**:
   - Interactive comparison cards displaying relevance score, explanation, shared topology, key differences, and runbook prerequisite status.
2. **Investigation History Archive**:
   - Full chronological audit log of all investigations recorded in FalkorDB, showing ranked hypotheses, deterministic scores, and provenance tags.
   - Preserves state across browser sessions and backend restarts.
