"""Pydantic schemas for the agentic investigation orchestrator and execution trace.

Enforces strict typing, epistemic status, validated inputs, and structured result events.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class OrchestrationStepTrace(BaseModel):
    """Structured record of an individual tool call executed by the investigation agent."""
    step_number: int = Field(..., description="1-indexed execution sequence number")
    timestamp: str = Field(..., description="ISO timestamp when step executed")
    tool_name: Literal[
        "inspect_incident_evidence",
        "trace_dependency_path",
        "get_blast_radius",
        "compare_hypotheses",
        "simulate_graph_intervention",
    ]
    selection_rationale: str = Field(..., description="Why the agent selected this tool based on current graph evidence")
    validated_parameters: Dict[str, Any] = Field(default_factory=dict, description="Validated arguments passed to tool with secrets masked")
    status: Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "SKIPPED"] = "SUCCEEDED"
    duration_ms: float = Field(default=0.0, description="Execution latency in milliseconds")
    result_summary: str = Field(..., description="Human and machine readable synthesis of the tool result")
    raw_result: Optional[Dict[str, Any]] = Field(default=None, description="Full structured output returned from tool")
    epistemic_status: Literal["OBSERVED", "INFERRED", "HISTORICAL", "SYNTHETIC", "SIMULATED"] = "OBSERVED"
    associated_entities: List[str] = Field(default_factory=list, description="Service, alert, or incident IDs surfaced in this step")
    next_investigation_goal: Optional[str] = Field(None, description="What the agent decided to investigate next")
    decision_source: Literal["llm_tool_selection", "deterministic_policy"] = "deterministic_policy"
    error_details: Optional[str] = None


class InvestigationOrchestrationResponse(BaseModel):
    """Complete response returned by the investigation orchestrator."""
    incident_id: str
    incident_title: str
    severity: str
    execution_mode: Literal["llm_tool_selection", "deterministic_policy"]
    total_steps: int
    started_at: str
    completed_at: str
    duration_ms: float
    steps: List[OrchestrationStepTrace]
    final_verdict: str
    top_hypothesis_id: Optional[str] = None
    top_hypothesis_title: Optional[str] = None
    top_hypothesis_score: Optional[float] = None
    confidence_level: Literal["HIGH_CONFIDENCE_ROOT_CAUSE", "PLAUSIBLE_CONTRIBUTOR", "WEAK_OR_MISLEADING", "INCONCLUSIVE_INSUFFICIENT_DATA"]
    supporting_evidence_count: int
    contradicting_evidence_count: int
    unresolved_questions: List[str] = Field(default_factory=list)
    intervention_simulated: bool = False
    simulation_experiment_id: Optional[str] = None
    simulation_blast_reduction: Optional[int] = None
    narrative_summary: str
    persisted_to_memory: bool = False
