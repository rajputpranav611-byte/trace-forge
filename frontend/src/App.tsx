import React, { useCallback, useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  XCircle,
  Database,
  Server,
  RefreshCw,
  AlertTriangle,
  Network,
  Clock,
  ExternalLink,
  Search,
  BookOpen,
  ShieldAlert,
  ArrowRight,
  History,
  Terminal,
  Award,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Scissors,
  Zap,
  Split,
  Bot,
  Play,
  RotateCcw,
  FileQuestion,
  Check,
  Lock,
  ShieldCheck,
  ThumbsUp,
  ThumbsDown,
  CheckSquare,
  AlertCircle,
  BookmarkCheck,
  Scale,
  Layers,
  Cpu,
  Radio,
  FileText,
  Sliders,
  Info,
} from "lucide-react";
import { InteractiveTopologyGraph } from "./InteractiveTopologyGraph";
import { MetricTelemetryCharts } from "./MetricTelemetryCharts";
import { motion, AnimatePresence } from "framer-motion";

interface OrchestrationStepTrace {
  step_number: number;
  timestamp: string;
  tool_name: "inspect_incident_evidence" | "trace_dependency_path" | "get_blast_radius" | "compare_hypotheses" | "simulate_graph_intervention";
  selection_rationale: string;
  validated_parameters: Record<string, any>;
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "SKIPPED";
  duration_ms: number;
  result_summary: string;
  raw_result?: Record<string, any>;
  epistemic_status: "OBSERVED" | "INFERRED" | "HISTORICAL" | "SYNTHETIC" | "SIMULATED";
  associated_entities: string[];
  next_investigation_goal?: string;
  decision_source: "llm_tool_selection" | "deterministic_policy";
  error_details?: string;
}

interface InvestigationOrchestrationResponse {
  incident_id: string;
  incident_title: string;
  severity: string;
  execution_mode: "llm_tool_selection" | "deterministic_policy";
  total_steps: number;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  steps: OrchestrationStepTrace[];
  final_verdict: string;
  top_hypothesis_id?: string;
  top_hypothesis_title?: string;
  top_hypothesis_score?: number;
  confidence_level: string;
  supporting_evidence_count: number;
  contradicting_evidence_count: number;
  unresolved_questions: string[];
  intervention_simulated: boolean;
  simulation_experiment_id?: string;
  simulation_blast_reduction?: number;
  narrative_summary: string;
  persisted_to_memory: boolean;
}

interface ServiceHealth {
  status: string;
  service: string;
  environment: string;
}

interface DatabaseHealth {
  status: string;
  details: {
    connected: boolean;
    host?: string;
    port?: number;
    graph?: string;
    query_response?: string;
    error?: string;
  };
}

interface IncidentSummary {
  id: string;
  title: string;
  severity: string;
  status: string;
  started_at: string;
  resolved_at: string;
  summary: string;
  affected_services: string[];
}

interface ScoreFactor {
  name: string;
  contribution: number;
  reason: string;
}

interface ScoredHypothesis {
  rank: number;
  id: string;
  title: string;
  statement: string;
  suspected_entity: string;
  raw_confidence: number;
  deterministic_score: number;
  verdict: "HIGH_CONFIDENCE_ROOT_CAUSE" | "PLAUSIBLE_CONTRIBUTOR" | "WEAK_OR_MISLEADING" | "INCONCLUSIVE_INSUFFICIENT_DATA";
  score_factors: ScoreFactor[];
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  rejected_evidence_ids: string[];
  causal_path_found: boolean;
  causal_path: string[];
  unresolved_questions: string[];
  recommended_action?: string;
}

interface RankedInvestigationResponse {
  investigation_id: string;
  incident_id: string;
  ranked_at: string;
  abstained: boolean;
  top_hypothesis?: ScoredHypothesis;
  hypotheses: ScoredHypothesis[];
  unresolved_questions: string[];
  graph_persistence_status: string;
  explanation: string;
}

interface GraphSurgeryAction {
  action_type: "remove_dependency" | "remove_evidence" | "isolate_service" | "rollback_deployment";
  source_id: string;
  target_id?: string;
  relationship_type?: string;
  justification: string;
}

interface ScoreFactorDiff {
  factor_name: string;
  baseline_contribution: number;
  experiment_contribution: number;
  contribution_delta: number;
  baseline_reason: string;
  experiment_reason: string;
}

interface HypothesisDiff {
  hypothesis_id: string;
  title: string;
  baseline_rank: number | null;
  experiment_rank: number | null;
  baseline_score: number | null;
  experiment_score: number | null;
  score_delta: number;
  baseline_verdict: string | null;
  experiment_verdict: string | null;
  causal_path_changed: boolean;
  evidence_diff_summary: string;
  score_delta_explanation?: string;
  factor_diffs?: ScoreFactorDiff[];
}

interface BlastRadiusDiff {
  service_id: string;
  baseline_downstream_count: number;
  experiment_downstream_count: number;
  severed_services: string[];
  added_services?: string[];
}

interface CounterfactualComparisonResponse {
  experiment_id: string;
  experiment_name: string;
  baseline_incident_id: string;
  created_at: string;
  actions_applied: GraphSurgeryAction[];
  causal_change_explanation: string;
  hypothesis_diffs: HypothesisDiff[];
  blast_radius_diff: BlastRadiusDiff;
  baseline_investigation: RankedInvestigationResponse;
  experiment_investigation: RankedInvestigationResponse;
  disclaimer: string;
}

interface EvidenceDebtGap {
  id: string;
  title: string;
  category: string;
  severity: "BLOCKING" | "WARNING" | "INFORMATIONAL";
  affected_incident_id: string;
  affected_hypotheses: string[];
  affected_entities: string[];
  why_it_matters: string;
  resolving_evidence: string;
  status: "ACTIVE" | "RESOLVED";
  provenance: string;
}

interface EvidenceDebtSummary {
  total_gaps: number;
  blocking_count: number;
  warning_count: number;
  informational_count: number;
  active_count: number;
  resolved_count: number;
  has_blocking_debt: boolean;
  priority_rule_explanation: string;
}

interface EvidenceDebtReport {
  incident_id: string;
  evaluated_at: string;
  summary: EvidenceDebtSummary;
  gaps: EvidenceDebtGap[];
  blocked_recovery_actions: string[];
}

interface PolicyVerificationResult {
  policy_name: string;
  passed: boolean;
  details: string;
}

interface ProposedRecoveryAction {
  action_id: string;
  incident_id: string;
  action_type: string;
  target_service_id: string;
  runbook_id?: string;
  step_id?: string;
  parameters: Record<string, any>;
  justification: string;
  required_evidence_ids: string[];
  state: "PROPOSED" | "VALIDATED" | "AWAITING_APPROVAL" | "APPROVED" | "REJECTED" | "EXECUTING_SIMULATION" | "SUCCEEDED" | "FAILED" | "CANCELLED";
  proposal_hash: string;
  created_at: string;
  updated_at: string;
  idempotency_key: string;
  validation_results: PolicyVerificationResult[];
  approval_id?: string;
  approver?: string;
  approval_status?: "APPROVED" | "REJECTED";
  approval_decided_at?: string;
  approval_notes?: string;
  simulation_executed_at?: string;
  simulation_output?: Record<string, any>;
  audit_trail: Array<Record<string, any>>;
}

interface EpistemicProvenance {
  source_type: string;
  source_id: string;
  verified: boolean;
  epistemic_status: "VERIFIED_OBSERVATION" | "UNVERIFIED_CLAIM" | "SIMULATED_DRY_RUN" | "REJECTED_HYPOTHESIS";
  notes?: string;
}

interface HistoricalInvestigationRecord {
  investigation_id: string;
  incident_id: string;
  incident_title: string;
  incident_severity: string;
  incident_status: string;
  started_at: string;
  ranked_at?: string;
  abstained: boolean;
  top_hypothesis_title?: string;
  top_hypothesis_score?: number;
  top_hypothesis_verdict?: string;
  hypotheses_count: number;
  supporting_evidence_ids: string[];
  unresolved_questions: string[];
  verified_recovery_actions: Array<Record<string, any>>;
  simulated_outcomes: Array<Record<string, any>>;
  evidence_gaps: string[];
  provenance: EpistemicProvenance;
}

interface RunbookPrerequisiteMatch {
  runbook_id: string;
  runbook_title: string;
  service_id: string;
  required_step_id: string;
  required_action: string;
  is_satisfied: boolean;
  reason: string;
}

interface HistoricalComparison {
  historical_incident_id: string;
  historical_title: string;
  historical_investigation_id?: string;
  is_relevant: boolean;
  relevance_score: number;
  relevance_explanation: string;
  common_affected_services: string[];
  evidence_similarities: string[];
  evidence_differences: string[];
  verified_recovery_outcomes: Array<Record<string, any>>;
  simulated_outcomes_summary: Array<Record<string, any>>;
  runbook_prerequisite_checks: RunbookPrerequisiteMatch[];
  unresolved_questions_carried_over: string[];
  epistemic_disclaimer: string;
}

interface InvestigationMemoryResponse {
  current_incident_id: string;
  current_affected_services: string[];
  retrieved_at: string;
  historical_comparisons: HistoricalComparison[];
  total_relevant_found: number;
}

interface TopologyService {
  id: string;
  name: string;
  tier: number;
  team: string;
  status: string;
}

interface InvestigationContext {
  incident: {
    id: string;
    title: string;
    severity: string;
    status: string;
    started_at: string;
    resolved_at: string;
    summary: string;
  };
  alerts: Array<{
    id: string;
    service_id: string;
    service_name: string;
    name: string;
    severity: string;
    source: string;
    timestamp: string;
    description: string;
    metric_name?: string;
    value?: number;
  }>;
  metrics: Array<{
    id: string;
    alert_id: string;
    metric_name: string;
    timestamp: string;
    value: number;
    baseline: number;
    deviation_sigma: number;
    unit: string;
  }>;
  topology: {
    affected_services: TopologyService[];
    traversed_services: TopologyService[];
    dependency_edges: Array<{
      source: string;
      target: string;
      type: string;
      protocol?: string;
      critical?: boolean;
    }>;
    traversed_paths: Array<{
      length: number;
      node_ids: string[];
      relationship_types: string[];
    }>;
    missing_relationships_detected: string[];
  };
  deployments: Array<{
    id: string;
    service_id: string;
    service_name: string;
    version: string;
    commit_sha: string;
    deployed_at: string;
    author: string;
    status: string;
    environment: string;
    strategy?: string;
  }>;
  historical_incidents: Array<{
    id: string;
    service_id: string;
    service_name: string;
    title: string;
    severity: string;
    status: string;
    started_at: string;
    resolved_at: string;
    summary: string;
    recovery_actions: Array<any>;
  }>;
  runbooks: Array<{
    id: string;
    service_id: string;
    service_name: string;
    title: string;
    version: string;
    url: string;
    steps: Array<{
      id: string;
      step_number: number;
      action: string;
      command: string;
      estimated_time_mins: number;
    }>;
  }>;
  evidence_summary: {
    source_incident_id: string;
    affected_service_count: number;
    alert_count: number;
    metric_anomalies_count: number;
    total_traversed_nodes: number;
    dependency_edge_count: number;
    deployment_candidate_count: number;
    historical_precedent_count: number;
    runbook_count: number;
    is_sufficient_evidence: boolean;
  };
}

// 7 Core Views including Autonomous Agent Trace
type CommandCenterView =
  | "command_center"
  | "agent_trace"
  | "dependency_explorer"
  | "hypothesis_lab"
  | "graph_surgery"
  | "recovery_console"
  | "memory_debt";

// Helper badge component for Epistemic provenance
function EpistemicBadge({
  kind,
  label,
  source,
}: {
  kind: "OBSERVED" | "INFERRED" | "SYNTHETIC" | "HYPOTHETICAL" | "SIMULATED" | "HISTORICAL";
  label?: string;
  source?: string;
}) {
  const configs = {
    OBSERVED: {
      bg: "bg-[#72C6A0]/10",
      text: "text-[#72C6A0]",
      border: "border-[#72C6A0]/30",
      defaultLabel: "OBSERVED TELEMETRY",
    },
    INFERRED: {
      bg: "bg-[#89B8D9]/10",
      text: "text-[#89B8D9]",
      border: "border-[#89B8D9]/30",
      defaultLabel: "INFERRED GRAPH PATH",
    },
    SYNTHETIC: {
      bg: "bg-[#DDAA60]/10",
      text: "text-[#DDAA60]",
      border: "border-[#DDAA60]/30",
      defaultLabel: "SYNTHETIC EXPERIMENT",
    },
    HYPOTHETICAL: {
      bg: "bg-[#EF7777]/10",
      text: "text-[#EF7777]",
      border: "border-[#EF7777]/30",
      defaultLabel: "HYPOTHETICAL CLAIM",
    },
    SIMULATED: {
      bg: "bg-[#A78BFA]/10",
      text: "text-[#A78BFA]",
      border: "border-[#A78BFA]/30",
      defaultLabel: "SIMULATED INTERVENTION",
    },
    HISTORICAL: {
      bg: "bg-[#9AA69C]/10",
      text: "text-[#9AA69C]",
      border: "border-[#9AA69C]/30",
      defaultLabel: "HISTORICAL PRECEDENT",
    },
  };

  const c = configs[kind] || configs.OBSERVED;

  return (
    <span
      title={source ? `Provenance source: ${source}` : undefined}
      className={`inline-flex items-center gap-1.5 text-[9px] uppercase font-mono font-semibold tracking-wider px-2 py-0.5 rounded-sm border ${c.bg} ${c.text} ${c.border}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-75" />
      {label || c.defaultLabel}
    </span>
  );
}

export function App() {
  const [serviceHealth, setServiceHealth] = useState<ServiceHealth | null>(null);
  const [dbHealth, setDbHealth] = useState<DatabaseHealth | null>(null);
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>("INC-2026-8821");
  const [investigation, setInvestigation] = useState<InvestigationContext | null>(null);
  const [rankedData, setRankedData] = useState<RankedInvestigationResponse | null>(null);
  const [expandedHypId, setExpandedHypId] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [investigating, setInvestigating] = useState<boolean>(false);
  const [rankingInProgress, setRankingInProgress] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string>("");

  // Primary Command Center Active View (6 core views)
  const [activeView, setActiveView] = useState<CommandCenterView>("command_center");

  // Interactive Inspector States
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEvidenceFilter, setSelectedEvidenceFilter] = useState<string | null>(null);
  const [activeMemoryTab, setActiveMemoryTab] = useState<"comparisons" | "debt_registry" | "investigation_archive">("comparisons");

  // Persistent Investigation Memory & Historical Incidents State
  const [memoryComparison, setMemoryComparison] = useState<InvestigationMemoryResponse | null>(null);
  const [historicalInvestigations, setHistoricalInvestigations] = useState<HistoricalInvestigationRecord[]>([]);
  const [memoryLoading, setMemoryLoading] = useState<boolean>(false);

  // Graph Surgery Simulator State
  const [surgeryActionType, setSurgeryActionType] = useState<"remove_dependency" | "remove_evidence" | "isolate_service" | "rollback_deployment">("remove_dependency");
  const [surgerySourceId, setSurgerySourceId] = useState<string>("payment-core");
  const [surgeryTargetId, setSurgeryTargetId] = useState<string>("payment-db-cluster");
  const [surgeryRelType, setSurgeryRelType] = useState<string>("DEPENDS_ON");
  const [surgeryJustification, setSurgeryJustification] = useState<string>("Test if isolating payment-db-cluster shifts root cause hypothesis");
  const [surgeryComparison, setSurgeryComparison] = useState<CounterfactualComparisonResponse | null>(null);
  const [expandedHypothesisDiff, setExpandedHypothesisDiff] = useState<string | null>(null);
  const [surgeryInProgress, setSurgeryInProgress] = useState<boolean>(false);
  const [surgeryError, setSurgeryError] = useState<string | null>(null);

  // Evidence Debt State
  const [debtReport, setDebtReport] = useState<EvidenceDebtReport | null>(null);
  const [debtLoading, setDebtLoading] = useState<boolean>(false);
  const [debtResolutionNote, setDebtResolutionNote] = useState<string>("");
  const [selectedDebtGapId, setSelectedDebtGapId] = useState<string | null>(null);

  // Safe Simulated Recovery State
  const [recoveryProposals, setRecoveryProposals] = useState<ProposedRecoveryAction[]>([]);
  const [recoveryLoading, setRecoveryLoading] = useState<boolean>(false);
  const [approverName, setApproverName] = useState<string>("staff-sre@nexuspay.io");
  const [approverRole, setApproverRole] = useState<string>("Staff SRE");
  const [approvalNotes, setApprovalNotes] = useState<string>("Verified root cause diagnosis; authorized canary rollback.");
  const [newActionType, setNewActionType] = useState<string>("rollback_deployment");
  const [newTargetService, setNewTargetService] = useState<string>("payment-core");
  const [newRunbookId, setNewRunbookId] = useState<string>("RBK-PAY-01");
  const [newStepId, setNewStepId] = useState<string>("STP-02");
  const [newRevision, setNewRevision] = useState<string>("DEP-4010");
  const [newJustification, setNewJustification] = useState<string>("Rollback recent canary release DEP-4012 on payment-core");
  const [recoveryError, setRecoveryError] = useState<string | null>(null);

  // MCP Autonomous Agent Orchestration Trace State
  const [agentTrace, setAgentTrace] = useState<InvestigationOrchestrationResponse | null>(null);
  const [agentLoading, setAgentLoading] = useState<boolean>(false);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [expandedStepNumber, setExpandedStepNumber] = useState<number | null>(1);

  const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

  const fetchStatusAndIncidents = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [svcRes, dbRes, incRes] = await Promise.all([
        fetch(`${apiBase}/api/v1/health`).catch(() => null),
        fetch(`${apiBase}/api/v1/health/db`).catch(() => null),
        fetch(`${apiBase}/api/v1/graph/incidents`).catch(() => null),
      ]);

      if (svcRes && svcRes.ok) setServiceHealth(await svcRes.json());
      if (dbRes && dbRes.ok) setDbHealth(await dbRes.json());
      if (incRes && incRes.ok) {
        const list = await incRes.json();
        setIncidents(list);
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to query system status");
    } finally {
      setLoading(false);
      setLastChecked(new Date().toLocaleTimeString());
    }
  }, [apiBase]);

  const triggerRanking = useCallback(async (incidentId: string) => {
    setRankingInProgress(true);
    try {
      const res = await fetch(`${apiBase}/api/v1/investigation/rank/${incidentId}?max_depth=3`, {
        method: "POST",
      });
      if (res.ok) {
        const data: RankedInvestigationResponse = await res.json();
        setRankedData(data);
        if (data.hypotheses.length > 0) {
          setExpandedHypId(data.hypotheses[0].id);
        }
      }
    } catch (e) {
      console.error("Hypothesis ranking error:", e);
    } finally {
      setRankingInProgress(false);
    }
  }, [apiBase]);

  const runAgentInvestigation = useCallback(async (incidentId: string) => {
    setAgentLoading(true);
    setAgentError(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/investigation/orchestrate/${incidentId}`, {
        method: "POST",
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Agent orchestration returned HTTP ${res.status}`);
      }
      const data: InvestigationOrchestrationResponse = await res.json();
      setAgentTrace(data);
      if (data.steps.length > 0) {
        setExpandedStepNumber(data.steps[0].step_number);
      }
    } catch (err: any) {
      setAgentError(err.message || "Failed to execute autonomous agent investigation");
    } finally {
      setAgentLoading(false);
    }
  }, [apiBase]);

  const runInvestigation = useCallback(async (incidentId: string) => {
    setInvestigating(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/investigation/context/${incidentId}?max_depth=3`);
      if (!res.ok) {
        throw new Error(`Investigation query failed with status: ${res.status}`);
      }
      const data: InvestigationContext = await res.json();
      setInvestigation(data);

      // Auto-trigger ranking and persistence
      triggerRanking(incidentId);

      // Auto-trigger autonomous agent investigation
      runAgentInvestigation(incidentId);
    } catch (err: any) {
      setErrorMsg(err?.message || "Investigation failed to execute");
      setInvestigation(null);
    } finally {
      setInvestigating(false);
    }
  }, [apiBase, triggerRanking, runAgentInvestigation]);

  const executeSurgerySimulation = async () => {
    setSurgeryInProgress(true);
    setSurgeryError(null);
    try {
      const payload = {
        baseline_incident_id: selectedIncidentId,
        experiment_name: `Counterfactual: ${surgeryActionType} on ${surgerySourceId}`,
        actions: [
          {
            action_type: surgeryActionType,
            source_id: surgerySourceId,
            target_id: surgeryActionType === "remove_dependency" ? surgeryTargetId : undefined,
            relationship_type: surgeryActionType === "remove_dependency" ? surgeryRelType : undefined,
            justification: surgeryJustification || "Surgical graph intervention test",
          },
        ],
      };

      const res = await fetch(`${apiBase}/api/v1/surgery/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Simulation failed with HTTP ${res.status}`);
      }

      const data: CounterfactualComparisonResponse = await res.json();
      setSurgeryComparison(data);
    } catch (err: any) {
      setSurgeryError(err.message || "Failed to execute counterfactual simulation");
    } finally {
      setSurgeryInProgress(false);
    }
  };

  const fetchDebtReport = useCallback(async (incidentId: string) => {
    setDebtLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/v1/debt/report/${incidentId}`);
      if (res.ok) {
        const data: EvidenceDebtReport = await res.json();
        setDebtReport(data);
      }
    } catch (e) {
      console.error("Evidence Debt fetch error:", e);
    } finally {
      setDebtLoading(false);
    }
  }, [apiBase]);

  const resolveDebtGap = async (gapId: string) => {
    try {
      const stamp = Date.now().toString().slice(-4);
      const res = await fetch(`${apiBase}/api/v1/debt/resolve/${selectedIncidentId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          gap_id: gapId,
          resolution_evidence_id: `VERIF-${stamp}`,
          notes: debtResolutionNote || "Audited and verified by on-call engineer in FalkorDB",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.updated_report) {
          setDebtReport(data.updated_report);
          setSelectedDebtGapId(null);
          setDebtResolutionNote("");
        }
      }
    } catch (e) {
      console.error("Evidence Debt resolution error:", e);
    }
  };

  const fetchRecoveryProposals = useCallback(async (incidentId: string) => {
    setRecoveryLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/v1/recovery/incident/${incidentId}`);
      if (res.ok) {
        const list: ProposedRecoveryAction[] = await res.json();
        setRecoveryProposals(list);
      }
    } catch (e) {
      console.error("Recovery proposals fetch error:", e);
    } finally {
      setRecoveryLoading(false);
    }
  }, [apiBase]);

  const submitRecoveryProposal = async () => {
    setRecoveryError(null);
    try {
      const stamp = Date.now().toString();
      const rand = Math.random().toString(36).substring(2, 7);
      const payload = {
        incident_id: selectedIncidentId,
        action_type: newActionType,
        target_service_id: newTargetService,
        runbook_id: newRunbookId || undefined,
        step_id: newStepId || undefined,
        parameters: newActionType === "rollback_deployment" ? { revision: newRevision } : {},
        justification: newJustification,
        idempotency_key: `idemp-${stamp}-${rand}`,
      };
      const res = await fetch(`${apiBase}/api/v1/recovery/propose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Proposal submission rejected");
      }
      await fetchRecoveryProposals(selectedIncidentId);
    } catch (err: any) {
      setRecoveryError(err.message || "Failed to submit recovery proposal");
    }
  };

  const decideRecoveryProposal = async (actionId: string, decision: "APPROVED" | "REJECTED", proposalHash: string) => {
    setRecoveryError(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/recovery/${actionId}/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approver: approverName,
          role: approverRole,
          decision: decision,
          notes: approvalNotes,
          proposal_hash: proposalHash,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Approval decision rejected");
      }
      await fetchRecoveryProposals(selectedIncidentId);
    } catch (err: any) {
      setRecoveryError(err.message || "Failed to record approval decision");
    }
  };

  const simulateRecoveryProposal = async (actionId: string, approver: string, proposalHash: string) => {
    setRecoveryError(null);
    try {
      const stamp = Date.now().toString();
      const res = await fetch(`${apiBase}/api/v1/recovery/${actionId}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approver: approver,
          idempotency_key: `exec-${stamp}`,
          proposal_hash: proposalHash,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Simulation execution rejected");
      }
      await fetchRecoveryProposals(selectedIncidentId);
    } catch (err: any) {
      setRecoveryError(err.message || "Failed to execute simulation");
    }
  };

  const fetchInvestigationMemory = useCallback(async (incidentId: string) => {
    setMemoryLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/v1/memory/compare/${incidentId}?max_depth=3`);
      if (res.ok) {
        const data = await res.json();
        setMemoryComparison(data);
      }
    } catch (e) {
      console.error("Memory comparison fetch error:", e);
    } finally {
      setMemoryLoading(false);
    }
  }, [apiBase]);

  const fetchHistoricalInvestigations = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/memory/investigations?limit=25`);
      if (res.ok) {
        const list = await res.json();
        setHistoricalInvestigations(list);
      }
    } catch (e) {
      console.error("Historical investigations fetch error:", e);
    }
  }, [apiBase]);

  useEffect(() => {
    fetchStatusAndIncidents();
    fetchHistoricalInvestigations();
  }, [fetchStatusAndIncidents, fetchHistoricalInvestigations]);

  useEffect(() => {
    if (selectedIncidentId) {
      runInvestigation(selectedIncidentId);
      fetchDebtReport(selectedIncidentId);
      fetchRecoveryProposals(selectedIncidentId);
      fetchInvestigationMemory(selectedIncidentId);
    }
  }, [selectedIncidentId, runInvestigation, fetchDebtReport, fetchRecoveryProposals, fetchInvestigationMemory]);

  const isBackendHealthy = serviceHealth?.status === "healthy";
  const isDbHealthy = dbHealth?.status === "healthy" && dbHealth.details?.connected;

  // Selected Service details lookup
  const selectedNodeDetails = selectedNodeId && investigation
    ? investigation.topology.traversed_services.find((s) => s.id === selectedNodeId) ||
      investigation.topology.affected_services.find((s) => s.id === selectedNodeId)
    : null;

  return (
    <div className="min-h-screen bg-[#0B0E0D] text-[#E9EDE5] flex flex-col justify-between selection:bg-[#C8F169] selection:text-[#0B0E0D]">
      {/* Subtle organic ambient accent */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden -z-10">
        <div className="absolute -top-40 -left-40 w-80 h-80 bg-[#72C6A0]/5 rounded-full blur-3xl" />
        <div className="absolute top-1/2 -right-40 w-96 h-96 bg-[#C8F169]/3 rounded-full blur-3xl" />
      </div>

      {/* Top Professional Mission Navbar */}
      <header className="border-b border-[#232B26] bg-[#0E1210]/95 backdrop-blur-md px-6 py-2.5 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded bg-[#171D19] border border-[#232B26] flex items-center justify-center">
            <Activity className="h-4 w-4 text-[#C8F169]" />
          </div>
          <div>
            <h1 className="text-xs font-semibold tracking-tight text-[#E9EDE5] flex items-center gap-2">
              <span className="font-bold tracking-normal font-sans">TraceForge</span>
              <span className="text-[9px] uppercase font-mono font-medium tracking-wider px-1.5 py-0.2 rounded bg-[#171D19] text-[#72C6A0] border border-[#232B26]">
                Topology & Incident Lab
              </span>
            </h1>
            <p className="text-[10px] text-[#9AA69C] font-mono tracking-tight">
              Deterministic Graph Investigation & Counterfactual Incident Sandbox
            </p>
          </div>
        </div>

        {/* Operational Status Indicators & Tools */}
        <div className="flex items-center flex-wrap gap-2">
          {/* Engine & DB telemetry capsules */}
          <div className="flex items-center gap-2 text-xs font-mono">
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#111614] border border-[#232B26] text-[#9AA69C] text-[11px]">
              <Server className="h-3 w-3 text-[#72C6A0]" />
              <span>FastAPI:</span>
              <span className={isBackendHealthy ? "text-[#C8F169] font-semibold" : "text-[#EF7777] font-semibold"}>
                {isBackendHealthy ? "ONLINE" : "ERR"}
              </span>
            </div>
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#111614] border border-[#232B26] text-[#9AA69C] text-[11px]">
              <Database className="h-3 w-3 text-[#72C6A0]" />
              <span>FalkorDB:</span>
              <span className={isDbHealthy ? "text-[#C8F169] font-semibold" : "text-[#EF7777] font-semibold"}>
                {isDbHealthy ? "CONNECTED" : "ERR"}
              </span>
            </div>
          </div>

          {lastChecked && (
            <span className="text-[10px] text-[#647067] hidden md:inline font-mono">
              Sync: {lastChecked}
            </span>
          )}

          <a
            href="http://localhost:3000"
            target="_blank"
            rel="noreferrer"
            className="hidden sm:flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono bg-[#111614] border border-[#232B26] hover:border-[#344039] text-[#9AA69C] hover:text-[#E9EDE5] transition-colors"
          >
            <Database className="h-3 w-3 text-[#72C6A0]" />
            <span>FalkorDB :3000</span>
            <ExternalLink className="h-2.5 w-2.5 opacity-60" />
          </a>

          <button
            onClick={() => {
              fetchStatusAndIncidents();
              if (selectedIncidentId) runInvestigation(selectedIncidentId);
            }}
            disabled={loading || investigating}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-[#171D19] border border-[#232B26] hover:border-[#C8F169]/50 text-[#E9EDE5] hover:text-[#C8F169] transition-all disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`h-3 w-3 text-[#C8F169] ${loading || investigating ? "animate-spin" : ""}`} />
            {investigating || rankingInProgress ? "Investigating..." : "Refresh Graph"}
          </button>
        </div>
      </header>

      {/* 7 Primary Operational Navigation Tabs */}
      <nav aria-label="Incident Response Views" className="bg-[#0B0E0D] border-b border-[#232B26] px-4 md:px-6 py-1.5 sticky top-[49px] z-20 overflow-x-auto scrollbar-thin scrollbar-thumb-[#232B26]">
        <div className="max-w-7xl mx-auto flex items-center gap-1.5 min-w-max">
          {/* 1. Incident Command Center */}
          <button
            onClick={() => setActiveView("command_center")}
            className={`px-3 py-1.5 rounded text-xs font-medium flex items-center gap-2 transition-all cursor-pointer shrink-0 ${
              activeView === "command_center"
                ? "bg-[#171D19] border border-[#C8F169]/60 text-[#C8F169] shadow-sm"
                : "text-[#9AA69C] hover:text-[#E9EDE5] hover:bg-[#111614]"
            }`}
          >
            <Radio className="h-3.5 w-3.5" />
            <span>1. Command Center</span>
          </button>

          {/* 2. Autonomous MCP Agent Trace */}
          <button
            onClick={() => setActiveView("agent_trace")}
            className={`px-3 py-1.5 rounded text-xs font-medium flex items-center gap-2 transition-all cursor-pointer shrink-0 ${
              activeView === "agent_trace"
                ? "bg-[#171D19] border border-[#A78BFA]/60 text-[#A78BFA] shadow-sm"
                : "text-[#9AA69C] hover:text-[#E9EDE5] hover:bg-[#111614]"
            }`}
          >
            <Bot className="h-3.5 w-3.5 text-[#A78BFA]" />
            <span>2. Agent Trace (MCP)</span>
            {agentTrace && (
              <span className="font-mono text-[9px] px-1.5 py-0.2 rounded bg-[#111614] border border-[#A78BFA]/30 text-[#A78BFA]">
                {agentTrace.steps.length} Steps
              </span>
            )}
            {agentLoading && (
              <RefreshCw className="h-2.5 w-2.5 animate-spin text-[#A78BFA]" />
            )}
          </button>

          {/* 3. Interactive Dependency Explorer */}
          <button
            onClick={() => setActiveView("dependency_explorer")}
            className={`px-3 py-1.5 rounded text-xs font-medium flex items-center gap-2 transition-all cursor-pointer shrink-0 ${
              activeView === "dependency_explorer"
                ? "bg-[#171D19] border border-[#72C6A0]/60 text-[#72C6A0] shadow-sm"
                : "text-[#9AA69C] hover:text-[#E9EDE5] hover:bg-[#111614]"
            }`}
          >
            <Network className="h-3.5 w-3.5" />
            <span>3. Dependency Explorer</span>
            {investigation && (
              <span className="font-mono text-[9px] px-1.5 py-0.2 rounded bg-[#111614] border border-[#232B26] text-[#9AA69C]">
                {investigation.topology.traversed_paths.length}
              </span>
            )}
          </button>

          {/* 4. Hypothesis and Evidence Lab */}
          <button
            onClick={() => setActiveView("hypothesis_lab")}
            className={`px-3 py-1.5 rounded text-xs font-medium flex items-center gap-2 transition-all cursor-pointer shrink-0 ${
              activeView === "hypothesis_lab"
                ? "bg-[#171D19] border border-[#DDAA60]/60 text-[#DDAA60] shadow-sm"
                : "text-[#9AA69C] hover:text-[#E9EDE5] hover:bg-[#111614]"
            }`}
          >
            <Award className="h-3.5 w-3.5" />
            <span>4. Hypothesis Lab</span>
            {rankedData && rankedData.hypotheses.length > 0 && (
              <span className="font-mono text-[9px] px-1.5 py-0.2 rounded bg-[#111614] border border-[#232B26] text-[#9AA69C]">
                {rankedData.hypotheses.length}
              </span>
            )}
          </button>

          {/* 5. Graph Surgery Experiment Workspace */}
          <button
            onClick={() => setActiveView("graph_surgery")}
            className={`px-3 py-1.5 rounded text-xs font-medium flex items-center gap-2 transition-all cursor-pointer shrink-0 ${
              activeView === "graph_surgery"
                ? "bg-[#171D19] border border-[#EF7777]/60 text-[#EF7777] shadow-sm"
                : "text-[#9AA69C] hover:text-[#E9EDE5] hover:bg-[#111614]"
            }`}
          >
            <Scissors className="h-3.5 w-3.5" />
            <span>5. Graph Surgery</span>
            {surgeryComparison && (
              <span className="w-1.5 h-1.5 rounded-full bg-[#EF7777]" />
            )}
          </button>

          {/* 6. Safe Recovery Console */}
          <button
            onClick={() => setActiveView("recovery_console")}
            className={`px-3 py-1.5 rounded text-xs font-medium flex items-center gap-2 transition-all cursor-pointer shrink-0 ${
              activeView === "recovery_console"
                ? "bg-[#171D19] border border-[#72C6A0]/60 text-[#72C6A0] shadow-sm"
                : "text-[#9AA69C] hover:text-[#E9EDE5] hover:bg-[#111614]"
            }`}
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>6. Safe Recovery</span>
            {recoveryProposals.filter((p) => p.state === "AWAITING_APPROVAL").length > 0 && (
              <span className="font-mono text-[9px] px-1.5 py-0.2 rounded bg-[#DDAA60]/20 text-[#DDAA60] border border-[#DDAA60]/30 font-semibold">
                {recoveryProposals.filter((p) => p.state === "AWAITING_APPROVAL").length}
              </span>
            )}
          </button>

          {/* 7. Historical Memory and Evidence Debt */}
          <button
            onClick={() => setActiveView("memory_debt")}
            className={`px-3 py-1.5 rounded text-xs font-medium flex items-center gap-2 transition-all cursor-pointer shrink-0 ${
              activeView === "memory_debt"
                ? "bg-[#171D19] border border-[#89B8D9]/60 text-[#89B8D9] shadow-sm"
                : "text-[#9AA69C] hover:text-[#E9EDE5] hover:bg-[#111614]"
            }`}
          >
            <Scale className="h-3.5 w-3.5" />
            <span>7. Memory & Debt</span>
            {debtReport && debtReport.summary.blocking_count > 0 && (
              <span className="font-mono text-[9px] px-1.5 py-0.2 rounded bg-[#EF7777]/20 text-[#EF7777] border border-[#EF7777]/30 font-semibold">
                {debtReport.summary.blocking_count}
              </span>
            )}
          </button>
        </div>
      </nav>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto w-full px-6 py-6 flex-1 space-y-6">
        {errorMsg && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-950/20 p-4 text-xs text-rose-300 flex items-start gap-2.5">
            <XCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-rose-200">System Alert</p>
              <p className="mt-0.5 text-rose-300/80">{errorMsg}</p>
            </div>
          </div>
        )}

        {/* Global Active Scenario Selector Bar */}
        <section className="rounded-md border border-[#232B26] bg-[#111614] p-3.5 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded bg-[#171D19] border border-[#232B26] text-[#72C6A0]">
              <Layers className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] uppercase font-mono tracking-wider text-[#9AA69C]">Active Scenario:</span>
                <span className="font-mono font-semibold text-[#E9EDE5] text-xs">{selectedIncidentId}</span>
                {investigation && (
                  <span
                    className={`text-[9px] uppercase font-mono font-semibold px-2 py-0.2 rounded-sm border ${
                      investigation.incident.severity === "SEV1"
                        ? "bg-[#EF7777]/15 text-[#EF7777] border-[#EF7777]/30"
                        : "bg-[#DDAA60]/15 text-[#DDAA60] border-[#DDAA60]/30"
                    }`}
                  >
                    {investigation.incident.severity}
                  </span>
                )}
                <EpistemicBadge kind="OBSERVED" label="LIVE GRAPH INCIDENT" />
              </div>
              <p className="text-xs text-[#9AA69C] mt-0.5 font-sans">
                {investigation ? investigation.incident.title : "Loading incident context from FalkorDB..."}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 w-full md:w-auto">
            <span className="text-xs text-[#9AA69C] hidden sm:inline font-mono">Switch Incident:</span>
            <select
              value={selectedIncidentId}
              onChange={(e) => setSelectedIncidentId(e.target.value)}
              className="bg-[#171D19] border border-[#232B26] rounded px-2.5 py-1 text-xs font-mono text-[#E9EDE5] focus:outline-none focus:border-[#C8F169]/50 w-full md:w-auto cursor-pointer"
            >
              {incidents.map((inc) => (
                <option key={inc.id} value={inc.id}>
                  {inc.id} — {inc.title.slice(0, 36)}... ({inc.severity})
                </option>
              ))}
            </select>
          </div>
        </section>

        {/* AnimatePresence for restrained view transitions */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeView}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
          >
            {/* =========================================================================
                VIEW 1: INCIDENT COMMAND CENTER
                ========================================================================= */}
            {activeView === "command_center" && investigation && (
              <div className="space-y-5">
            {/* Quick Metrics Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3.5 rounded-md bg-[#111614] border border-[#232B26]">
                <div className="flex items-center justify-between text-[#9AA69C]">
                  <span className="text-[10px] uppercase font-mono font-medium">Correlated Alerts</span>
                  <EpistemicBadge kind="OBSERVED" label="OBSERVED" />
                </div>
                <p className="mt-2 text-xl font-semibold font-mono text-[#E9EDE5]">
                  {investigation.evidence_summary.alert_count}
                </p>
                <span className="text-[11px] text-[#647067] font-mono">Active telemetry triggers</span>
              </div>

              <div className="p-3.5 rounded-md bg-[#111614] border border-[#232B26]">
                <div className="flex items-center justify-between text-[#9AA69C]">
                  <span className="text-[10px] uppercase font-mono font-medium">Traversed Services</span>
                  <EpistemicBadge kind="INFERRED" label="INFERRED" />
                </div>
                <p className="mt-2 text-xl font-semibold font-mono text-[#72C6A0]">
                  {investigation.evidence_summary.total_traversed_nodes}
                </p>
                <span className="text-[11px] text-[#647067] font-mono">Within 3-hop topological blast</span>
              </div>

              <div className="p-3.5 rounded-md bg-[#111614] border border-[#232B26]">
                <div className="flex items-center justify-between text-[#9AA69C]">
                  <span className="text-[10px] uppercase font-mono font-medium">Candidate Deployments</span>
                  <EpistemicBadge kind="OBSERVED" label="OBSERVED" />
                </div>
                <p className="mt-2 text-xl font-semibold font-mono text-[#89B8D9]">
                  {investigation.evidence_summary.deployment_candidate_count}
                </p>
                <span className="text-[11px] text-[#647067] font-mono">Temporal window matches</span>
              </div>

              <div className="p-3.5 rounded-md bg-[#111614] border border-[#232B26]">
                <div className="flex items-center justify-between text-[#9AA69C]">
                  <span className="text-[10px] uppercase font-mono font-medium">Ranked Root Cause</span>
                  <EpistemicBadge kind="HYPOTHETICAL" label="DETERMINISTIC" />
                </div>
                <p className="mt-2 text-xl font-semibold font-mono text-[#C8F169]">
                  {rankedData?.top_hypothesis ? `#1 (${rankedData.top_hypothesis.deterministic_score.toFixed(2)})` : "Scoring..."}
                </p>
                <span className="text-[11px] text-[#9AA69C] truncate block font-mono">
                  {rankedData?.top_hypothesis?.suspected_entity || "Evaluating..."}
                </span>
              </div>
            </div>

            {/* Incident Summary Card & Affected Services Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              {/* Left Column: Triage Details (7 cols) */}
              <div className="lg:col-span-7 rounded-md border border-[#232B26] bg-[#111614] p-5 space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#1E2622]">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-[#72C6A0]" />
                    <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E9EDE5]">
                      Incident Triage Brief & Timeline
                    </h3>
                  </div>
                  <span className="text-xs font-mono text-[#9AA69C] flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-[#647067]" />
                    {new Date(investigation.incident.started_at).toLocaleString()}
                  </span>
                </div>

                <div className="p-4 rounded border border-[#232B26] bg-[#0B0E0D] space-y-2">
                  <h4 className="text-sm font-semibold text-[#E9EDE5] font-sans">{investigation.incident.title}</h4>
                  <p className="text-xs text-[#9AA69C] leading-relaxed font-sans">
                    {investigation.incident.summary}
                  </p>
                </div>

                {/* Direct Alerts associated with incident */}
                <div className="space-y-2.5 pt-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-mono font-medium uppercase tracking-wider text-[#9AA69C] flex items-center gap-1.5">
                      <AlertTriangle className="h-3.5 w-3.5 text-[#EF7777]" />
                      Active P1/P2 Alerts ({investigation.alerts.length})
                    </span>
                    <EpistemicBadge kind="OBSERVED" />
                  </div>

                  <div className="space-y-2">
                    {investigation.alerts.map((alt) => (
                      <div
                        key={alt.id}
                        className="p-3 rounded border border-[#232B26] bg-[#141A17] text-xs flex items-start justify-between gap-3"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 font-mono">
                            <span className="font-bold text-[#C8F169]">{alt.id}</span>
                            <span className="text-[#647067]">·</span>
                            <span className="text-[#E9EDE5] font-sans font-medium">{alt.name}</span>
                          </div>
                          <p className="text-[11px] text-[#9AA69C] font-sans">{alt.description}</p>
                          <div className="text-[10px] text-[#647067] font-mono">
                            Service: <span className="text-[#E9EDE5]">{alt.service_name}</span> ({alt.service_id}) · Source: {alt.source}
                          </div>
                        </div>
                        <span
                          className={`text-[9px] uppercase font-bold px-2 py-0.5 rounded shrink-0 font-mono ${
                            alt.severity === "critical"
                              ? "bg-[#EF7777]/15 text-[#EF7777] border border-[#EF7777]/30"
                              : "bg-[#DDAA60]/15 text-[#DDAA60] border border-[#DDAA60]/30"
                          }`}
                        >
                          {alt.severity}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right Column: Affected Services Matrix & Candidate Runbooks (5 cols) */}
              <div className="lg:col-span-5 space-y-4">
                {/* Affected Services Matrix */}
                <div className="rounded-md border border-[#232B26] bg-[#111614] p-5 space-y-3">
                  <div className="flex items-center justify-between pb-2.5 border-b border-[#1E2622]">
                    <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E9EDE5] flex items-center gap-1.5">
                      <Cpu className="h-4 w-4 text-[#72C6A0]" />
                      Impacted Service Matrix ({investigation.topology.affected_services.length})
                    </h3>
                    <EpistemicBadge kind="OBSERVED" />
                  </div>

                  <div className="space-y-2">
                    {investigation.topology.affected_services.map((svc) => (
                      <div
                        key={svc.id}
                        onClick={() => {
                          setSelectedNodeId(svc.id);
                          setActiveView("dependency_explorer");
                        }}
                        className="p-3 rounded border border-[#232B26] bg-[#141A17] hover:border-[#72C6A0]/50 hover:bg-[#171E1A] transition-colors cursor-pointer flex items-center justify-between group"
                      >
                        <div>
                          <div className="font-mono font-bold text-xs text-[#E9EDE5] flex items-center gap-2">
                            {svc.name}
                            <span className="text-[10px] font-normal text-[#647067]">Tier-{svc.tier}</span>
                          </div>
                          <div className="text-[11px] text-[#9AA69C] font-mono mt-0.5">
                            Team: {svc.team} · ID: {svc.id}
                          </div>
                        </div>
                        <span className="text-[10px] uppercase font-bold font-mono px-2 py-0.5 rounded bg-[#EF7777]/15 text-[#EF7777] border border-[#EF7777]/30">
                          {svc.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Candidate Runbooks Card */}
                <div className="rounded-md border border-[#232B26] bg-[#111614] p-5 space-y-3">
                  <div className="flex items-center justify-between pb-2.5 border-b border-[#1E2622]">
                    <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E9EDE5] flex items-center gap-1.5">
                      <BookOpen className="h-4 w-4 text-[#89B8D9]" />
                      Associated Runbooks ({investigation.runbooks.length})
                    </h3>
                    <EpistemicBadge kind="INFERRED" label="CATALOG MATCH" />
                  </div>

                  {investigation.runbooks.map((rb) => (
                    <div key={rb.id} className="p-3 rounded border border-[#232B26] bg-[#141A17] text-xs space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-[#72C6A0]">{rb.id}</span>
                        <span className="text-[10px] font-mono text-[#647067]">v{rb.version}</span>
                      </div>
                      <p className="font-medium text-[#E9EDE5] font-sans">{rb.title}</p>
                      <div className="text-[11px] text-[#9AA69C] font-mono">
                        {rb.steps.length} sequential steps defined for {rb.service_name}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Real Telemetry Observation Visualizations */}
            <div className="pt-2">
              <MetricTelemetryCharts metrics={investigation.metrics} />
            </div>
          </div>
        )}

        {/* =========================================================================
            VIEW 2: AUTONOMOUS MCP AGENT TRACE (Agents That Act On Connected Data)
            ========================================================================= */}
        {activeView === "agent_trace" && (
          <div className="space-y-6">
            {/* Header & Controls Card */}
            <div className="rounded-md border border-[#232B26] bg-[#111614] p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <Bot className="h-5 w-5 text-[#A78BFA]" />
                  <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E9EDE5]">
                    Autonomous MCP Investigation Agent · Live Execution Trace
                  </h3>
                  {agentTrace && (
                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-[#A78BFA]/10 text-[#A78BFA] border border-[#A78BFA]/30">
                      {agentTrace.execution_mode}
                    </span>
                  )}
                </div>
                <p className="text-xs text-[#9AA69C] mt-1 font-sans">
                  Real graph-grounded agent executing autonomous multi-hop reasoning over FalkorDB via official Model Context Protocol tools.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => runAgentInvestigation(selectedIncidentId)}
                  disabled={agentLoading}
                  className="px-3.5 py-1.5 rounded bg-[#A78BFA]/20 hover:bg-[#A78BFA]/30 text-[#A78BFA] border border-[#A78BFA]/40 text-xs font-mono font-semibold flex items-center gap-2 cursor-pointer transition-all disabled:opacity-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${agentLoading ? "animate-spin" : ""}`} />
                  {agentLoading ? "Executing Investigation..." : "Rerun Autonomous Agent"}
                </button>
              </div>
            </div>

            {agentError && (
              <div className="p-4 rounded-md border border-[#EF7777]/30 bg-[#EF7777]/10 text-xs text-[#EF7777] font-mono flex items-center gap-2">
                <XCircle className="h-4 w-4 shrink-0" />
                <span>Agent execution error: {agentError}</span>
              </div>
            )}

            {agentTrace && (
              <>
                {/* Synthesis Banner */}
                <div className="p-4 rounded-md border border-[#232B26] bg-[#141A17] space-y-3">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-[#C8F169] font-bold">Investigation Complete</span>
                      <span className="text-[#647067]">·</span>
                      <span className="text-xs font-mono text-[#9AA69C]">{agentTrace.total_steps} MCP Tool Calls</span>
                      <span className="text-[#647067]">·</span>
                      <span className="text-xs font-mono text-[#9AA69C]">{agentTrace.duration_ms}ms execution latency</span>
                    </div>
                    <EpistemicBadge
                      kind={agentTrace.intervention_simulated ? "SIMULATED" : "INFERRED"}
                      label={agentTrace.confidence_level}
                    />
                  </div>

                  <p className="text-xs text-[#E9EDE5] leading-relaxed font-sans font-medium">
                    {agentTrace.narrative_summary}
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-2 text-xs font-mono border-t border-[#1E2622]">
                    <div className="p-2.5 rounded bg-[#0B0E0D] border border-[#232B26]">
                      <span className="text-[10px] text-[#647067] uppercase">Top Root Cause</span>
                      <p className="text-[#E9EDE5] font-semibold mt-0.5 truncate">{agentTrace.top_hypothesis_title || "None"}</p>
                    </div>
                    <div className="p-2.5 rounded bg-[#0B0E0D] border border-[#232B26]">
                      <span className="text-[10px] text-[#647067] uppercase">Score & Verdict</span>
                      <p className="text-[#DDAA60] font-bold mt-0.5">
                        {agentTrace.top_hypothesis_score ? `${agentTrace.top_hypothesis_score.toFixed(2)}` : "N/A"} · {agentTrace.final_verdict}
                      </p>
                    </div>
                    <div className="p-2.5 rounded bg-[#0B0E0D] border border-[#232B26]">
                      <span className="text-[10px] text-[#647067] uppercase">Evidence Items</span>
                      <p className="text-[#72C6A0] font-bold mt-0.5">
                        {agentTrace.supporting_evidence_count} Supporting / {agentTrace.contradicting_evidence_count} Contradicting
                      </p>
                    </div>
                    <div className="p-2.5 rounded bg-[#0B0E0D] border border-[#232B26]">
                      <span className="text-[10px] text-[#647067] uppercase">Counterfactual Surgery</span>
                      <p className="text-[#A78BFA] font-bold mt-0.5">
                        {agentTrace.intervention_simulated
                          ? `Simulated (${agentTrace.simulation_blast_reduction} nodes contracted)`
                          : "Not required"}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Step Timeline */}
                <div className="space-y-4">
                  <h4 className="text-xs font-mono uppercase tracking-wider text-[#9AA69C] flex items-center gap-2">
                    <Terminal className="h-4 w-4 text-[#A78BFA]" />
                    Sequential MCP Tool Execution Timeline ({agentTrace.steps.length} Steps)
                  </h4>

                  <div className="space-y-3">
                    {agentTrace.steps.map((st) => {
                      const isExpanded = expandedStepNumber === st.step_number;
                      return (
                        <div
                          key={st.step_number}
                          className="rounded-md border border-[#232B26] bg-[#111614] overflow-hidden transition-all"
                        >
                          {/* Step Header */}
                          <div
                            onClick={() => setExpandedStepNumber(isExpanded ? null : st.step_number)}
                            className="p-3.5 flex items-center justify-between cursor-pointer hover:bg-[#141A17] transition-colors"
                          >
                            <div className="flex items-center gap-3">
                              <span className="w-6 h-6 rounded-full bg-[#171D19] border border-[#232B26] text-[#A78BFA] font-mono text-xs font-bold flex items-center justify-center">
                                {st.step_number}
                              </span>
                              <div>
                                <div className="flex items-center gap-2 font-mono text-xs">
                                  <span className="font-bold text-[#E9EDE5]">{st.tool_name}</span>
                                  <span className="text-[#647067]">·</span>
                                  <span className="text-[11px] text-[#72C6A0] font-semibold">{st.duration_ms}ms</span>
                                  <span className="text-[#647067]">·</span>
                                  <span className="text-[10px] text-[#9AA69C]">{st.decision_source}</span>
                                </div>
                                <p className="text-[11px] text-[#9AA69C] mt-0.5 font-sans truncate max-w-xl">
                                  {st.result_summary}
                                </p>
                              </div>
                            </div>

                            <div className="flex items-center gap-2.5">
                              <EpistemicBadge kind={st.epistemic_status} />
                              <span className="text-[10px] font-mono uppercase font-bold px-2 py-0.5 rounded bg-[#72C6A0]/15 text-[#72C6A0] border border-[#72C6A0]/30">
                                {st.status}
                              </span>
                              {isExpanded ? (
                                <ChevronUp className="h-4 w-4 text-[#647067]" />
                              ) : (
                                <ChevronDown className="h-4 w-4 text-[#647067]" />
                              )}
                            </div>
                          </div>

                          {/* Expanded Step Body */}
                          {isExpanded && (
                            <div className="p-4 border-t border-[#1E2622] bg-[#0E1210] space-y-3.5 text-xs">
                              {/* Rationale */}
                              <div className="space-y-1">
                                <span className="text-[10px] font-mono uppercase font-semibold text-[#647067]">
                                  Selection Rationale & Evidence Context:
                                </span>
                                <p className="text-xs text-[#E9EDE5] bg-[#141A17] p-2.5 rounded border border-[#232B26] font-sans leading-relaxed">
                                  {st.selection_rationale}
                                </p>
                              </div>

                              {/* Parameters & Entities Grid */}
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 font-mono text-[11px]">
                                <div className="p-3 rounded bg-[#111614] border border-[#232B26] space-y-1.5">
                                  <span className="text-[10px] text-[#647067] uppercase font-semibold">
                                    Validated Tool Parameters:
                                  </span>
                                  <pre className="text-[#89B8D9] text-[10px] overflow-x-auto p-2 bg-[#0B0E0D] rounded border border-[#1E2622]">
                                    {JSON.stringify(st.validated_parameters, null, 2)}
                                  </pre>
                                </div>

                                <div className="p-3 rounded bg-[#111614] border border-[#232B26] space-y-1.5">
                                  <span className="text-[10px] text-[#647067] uppercase font-semibold">
                                    Associated Graph Entities:
                                  </span>
                                  <div className="flex flex-wrap gap-1.5 pt-1">
                                    {st.associated_entities.map((ent, idx) => (
                                      <span
                                        key={idx}
                                        className="px-2 py-0.5 rounded bg-[#171D19] border border-[#232B26] text-[#C8F169] text-[10px]"
                                      >
                                        {ent}
                                      </span>
                                    ))}
                                    {st.associated_entities.length === 0 && (
                                      <span className="text-[#647067] text-[10px]">None directly referenced</span>
                                    )}
                                  </div>
                                </div>
                              </div>

                              {/* Next Goal */}
                              {st.next_investigation_goal && (
                                <div className="p-2.5 rounded bg-[#141A17] border border-[#232B26] flex items-center gap-2 font-mono text-[11px]">
                                  <ArrowRight className="h-3.5 w-3.5 text-[#A78BFA] shrink-0" />
                                  <span className="text-[#647067]">Next Sub-Goal:</span>
                                  <span className="text-[#A78BFA]">{st.next_investigation_goal}</span>
                                </div>
                              )}

                              {/* Raw Result Inspector */}
                              {st.raw_result && (
                                <details className="p-2.5 rounded bg-[#111614] border border-[#232B26] text-xs">
                                  <summary className="font-mono text-[11px] text-[#9AA69C] cursor-pointer hover:text-[#E9EDE5]">
                                    Inspect Full Structured MCP Tool Output (JSON)
                                  </summary>
                                  <pre className="mt-2 text-[10px] font-mono text-[#9AA69C] bg-[#0B0E0D] p-3 rounded border border-[#1E2622] overflow-x-auto max-h-60">
                                    {JSON.stringify(st.raw_result, null, 2)}
                                  </pre>
                                </details>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* =========================================================================
            VIEW 3: INTERACTIVE DEPENDENCY EXPLORER
            ========================================================================= */}
        {activeView === "dependency_explorer" && investigation && (
          <div className="space-y-6">
            {/* Explorer Header */}
            <div className="rounded-md border border-[#232B26] bg-[#111614] p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div>
                <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E9EDE5] flex items-center gap-2">
                  <Network className="h-4 w-4 text-[#72C6A0]" />
                  Interactive Topological Dependency Explorer
                </h3>
                <p className="text-xs text-[#9AA69C] mt-1 font-sans">
                  Traversed multi-hop dependency paths retrieved dynamically from FalkorDB graph layer with bounded depth (max_depth=3). Click any node to inspect service parameters.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <EpistemicBadge kind="INFERRED" label="GRAPH TOPOLOGY" />
                <span className="text-xs font-mono text-[#9AA69C]">
                  {investigation.topology.traversed_paths.length} Paths · {investigation.topology.dependency_edges.length} Edges
                </span>
              </div>
            </div>

            {/* Catalog Missing Relationship Alert */}
            {investigation.topology.missing_relationships_detected.length > 0 && (
              <div className="rounded-md border border-[#DDAA60]/30 bg-[#DDAA60]/10 p-4 text-xs text-[#DDAA60] flex items-start gap-3">
                <AlertTriangle className="h-4 w-4 text-[#DDAA60] shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <span className="font-bold text-[#DDAA60]">Catalog Knowledge Debt Detected</span>
                  {investigation.topology.missing_relationships_detected.map((msg, idx) => (
                    <p key={idx} className="text-[#DDAA60]/80 font-mono text-[11px]">
                      {msg}
                    </p>
                  ))}
                </div>
              </div>
            )}

            {/* Interactive React Flow Graph Canvas */}
            <div className="h-[460px] w-full">
              <InteractiveTopologyGraph
                services={[
                  ...investigation.topology.traversed_services,
                  ...investigation.topology.affected_services.filter(
                    (a) => !investigation.topology.traversed_services.some((t) => t.id === a.id)
                  ),
                ]}
                edges={investigation.topology.dependency_edges}
                selectedServiceId={selectedNodeId}
                onSelectService={setSelectedNodeId}
                highlightedPath={
                  selectedNodeId
                    ? investigation.topology.traversed_paths
                        .find((p) => p.node_ids.includes(selectedNodeId))
                        ?.node_ids || []
                    : []
                }
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              {/* Left Column: Traversed Paths (8 cols) */}
              <div className="lg:col-span-8 rounded-md border border-[#232B26] bg-[#111614] p-5 space-y-4">
                <span className="text-xs font-mono font-semibold uppercase tracking-wider text-[#9AA69C] block pb-2 border-b border-[#1E2622]">
                  Causal & Blast Traversal Paths ({investigation.topology.traversed_paths.length})
                </span>

                <div className="space-y-2.5 max-h-[500px] overflow-y-auto pr-1">
                  {investigation.topology.traversed_paths.map((p, pidx) => (
                    <div
                      key={pidx}
                      className="p-3.5 rounded border border-[#232B26] bg-[#141A17] text-xs font-mono flex items-center gap-2 flex-wrap"
                    >
                      <span className="text-[#647067] font-sans text-[11px] mr-1">
                        Path #{pidx + 1} ({p.length} hops):
                      </span>
                      {p.node_ids.map((nid, nidx) => {
                        const isSelected = selectedNodeId === nid;
                        const isStart = nidx === 0;
                        const isEnd = nidx === p.node_ids.length - 1;

                        return (
                          <div key={nidx} className="flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => setSelectedNodeId(nid)}
                              className={`px-2.5 py-1 rounded border text-[11px] font-mono transition-colors cursor-pointer ${
                                isSelected
                                  ? "ring-1 ring-[#C8F169] bg-[#171E1A] border-[#C8F169] text-[#C8F169] font-bold"
                                  : isStart
                                  ? "bg-[#EF7777]/10 border-[#EF7777]/30 text-[#EF7777] hover:border-[#EF7777]/60"
                                  : isEnd
                                  ? "bg-[#72C6A0]/10 border-[#72C6A0]/30 text-[#72C6A0] hover:border-[#72C6A0]/60"
                                  : "bg-[#0B0E0D] border-[#232B26] text-[#9AA69C] hover:border-[#344039] hover:text-[#E9EDE5]"
                              }`}
                            >
                              {nid}
                            </button>
                            {nidx < p.node_ids.length - 1 && (
                              <ArrowRight className="h-3 w-3 text-[#647067] shrink-0" />
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>

              {/* Right Column: Node Details Inspector (4 cols) */}
              <div className="lg:col-span-4 rounded-md border border-[#232B26] bg-[#111614] p-5 space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-[#1E2622]">
                  <h4 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E9EDE5] flex items-center gap-1.5">
                    <Info className="h-4 w-4 text-[#72C6A0]" />
                    Service Node Inspector
                  </h4>
                  {selectedNodeId && <EpistemicBadge kind="OBSERVED" label="CATALOG" />}
                </div>

                {selectedNodeDetails ? (
                  <div className="p-4 rounded border border-[#232B26] bg-[#0B0E0D] space-y-3 text-xs">
                    <div>
                      <span className="text-[10px] text-[#647067] font-mono uppercase">Service Identifier</span>
                      <p className="font-mono font-bold text-[#C8F169] text-sm">{selectedNodeDetails.id}</p>
                    </div>
                    <div>
                      <span className="text-[10px] text-[#647067] font-mono uppercase">Display Name</span>
                      <p className="font-semibold text-[#E9EDE5] font-sans">{selectedNodeDetails.name}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 pt-1 font-mono">
                      <div>
                        <span className="text-[10px] text-[#647067] uppercase">Tier</span>
                        <p className="text-[#E9EDE5] font-bold">Tier-{selectedNodeDetails.tier}</p>
                      </div>
                      <div>
                        <span className="text-[10px] text-[#647067] uppercase">Status</span>
                        <p className="text-[#EF7777] font-bold uppercase">{selectedNodeDetails.status}</p>
                      </div>
                      <div className="col-span-2">
                        <span className="text-[10px] text-[#647067] uppercase">Owner Team</span>
                        <p className="text-[#9AA69C]">{selectedNodeDetails.team}</p>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-[#1E2622] space-y-1">
                      <span className="text-[10px] text-[#647067] uppercase font-mono font-semibold">Outgoing Edges:</span>
                      <div className="space-y-1 max-h-36 overflow-y-auto font-mono text-[11px]">
                        {investigation.topology.dependency_edges
                          .filter((e) => e.source === selectedNodeDetails.id)
                          .map((e, idx) => (
                            <div key={idx} className="p-1.5 rounded bg-[#141A17] border border-[#232B26] text-[#9AA69C] flex items-center justify-between">
                              <span>&rarr; {e.target}</span>
                              <span className="text-[10px] text-[#72C6A0] font-bold">{e.type}</span>
                            </div>
                          ))}
                        {investigation.topology.dependency_edges.filter((e) => e.source === selectedNodeDetails.id).length === 0 && (
                          <p className="text-[#647067] text-[11px] italic">No outgoing dependencies within bounded depth.</p>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="h-48 rounded border border-dashed border-[#232B26] flex flex-col items-center justify-center text-[#647067] text-xs p-4 text-center">
                    <Network className="h-6 w-6 text-[#29332D] mb-2" />
                    <p>Click on any service node in the causal paths to inspect its metadata, tier, and connected edges.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* =========================================================================
            VIEW 3: HYPOTHESIS AND EVIDENCE LAB
            ========================================================================= */}
        {activeView === "hypothesis_lab" && (
          <div className="space-y-6">
            {/* Header */}
            <div className="rounded-md border border-[#232B26] bg-[#111614] p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div>
                <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E9EDE5] flex items-center gap-2">
                  <Award className="h-4 w-4 text-[#C8F169]" />
                  Hypothesis & Deterministic Evidence Lab
                </h3>
                <p className="text-xs text-[#9AA69C] mt-1 font-sans">
                  Transparent multi-factor scoring of candidate root causes. Supporting and contradicting evidence references are clickable to inspect telemetry.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <EpistemicBadge kind="HYPOTHETICAL" label="DETERMINISTIC EVALUATION" />
                <button
                  type="button"
                  onClick={() => triggerRanking(selectedIncidentId)}
                  disabled={rankingInProgress}
                  className="px-3 py-1.5 rounded bg-[#171E1A] hover:bg-[#1E2622] text-[#C8F169] border border-[#C8F169]/30 font-mono font-medium text-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50 transition-colors"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${rankingInProgress ? "animate-spin" : ""}`} />
                  Re-evaluate Scores
                </button>
              </div>
            </div>

            {/* Epistemic Abstention Warning Banner */}
            {rankedData?.abstained && (
              <div className="p-4 rounded-md border border-[#DDAA60]/30 bg-[#DDAA60]/10 text-xs text-[#DDAA60] flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-[#DDAA60] shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-[#DDAA60]">
                    Epistemic Abstention Applied (Safety Invariant):
                  </span>
                  <p className="mt-1 text-[11px] text-[#DDAA60]/80 leading-relaxed font-sans">
                    Telemetry coverage or contradiction density is insufficient to establish mathematical confidence. TraceForge abstains from recommending high-risk autonomous mitigation.
                  </p>
                </div>
              </div>
            )}

            {/* Active Evidence Filter Banner if user clicked a chip */}
            {selectedEvidenceFilter && (
              <div className="p-3 rounded-md border border-[#72C6A0]/30 bg-[#72C6A0]/10 text-xs text-[#72C6A0] flex items-center justify-between">
                <div className="flex items-center gap-2 font-mono">
                  <Search className="h-3.5 w-3.5" />
                  <span>Filtered to Evidence ID: <strong className="text-[#C8F169]">{selectedEvidenceFilter}</strong></span>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedEvidenceFilter(null)}
                  className="text-xs text-[#9AA69C] hover:text-[#E9EDE5] underline cursor-pointer font-mono"
                >
                  Clear Evidence Filter
                </button>
              </div>
            )}

            {/* Ranked Hypotheses List */}
            <div className="space-y-4">
              {rankedData?.hypotheses.map((hyp) => {
                const isExpanded = expandedHypId === hyp.id;
                const isTop = hyp.rank === 1 && hyp.verdict === "HIGH_CONFIDENCE_ROOT_CAUSE";

                return (
                  <div
                    key={hyp.id}
                    className={`rounded-md border p-5 text-xs space-y-3 transition-colors ${
                      isTop
                        ? "bg-[#111614] border-[#72C6A0]/50"
                        : hyp.verdict === "WEAK_OR_MISLEADING"
                        ? "bg-[#0B0E0D] border-[#232B26] opacity-75"
                        : "bg-[#111614] border-[#232B26]"
                    }`}
                  >
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center gap-2.5">
                        <span className="font-mono font-bold text-[#C8F169] text-xs px-2.5 py-0.5 rounded bg-[#C8F169]/10 border border-[#C8F169]/30">
                          Rank #{hyp.rank}
                        </span>
                        <span className="font-mono text-[#647067]">{hyp.id}</span>
                        <h4 className="font-semibold text-[#E9EDE5] text-sm font-sans">{hyp.title}</h4>
                      </div>

                      <div className="flex items-center gap-2">
                        <span
                          className={`text-[9px] uppercase font-bold font-mono px-2 py-0.5 rounded ${
                            hyp.verdict === "HIGH_CONFIDENCE_ROOT_CAUSE"
                              ? "bg-[#72C6A0]/15 text-[#72C6A0] border border-[#72C6A0]/30"
                              : hyp.verdict === "PLAUSIBLE_CONTRIBUTOR"
                              ? "bg-[#89B8D9]/15 text-[#89B8D9] border border-[#89B8D9]/30"
                              : hyp.verdict === "WEAK_OR_MISLEADING"
                              ? "bg-[#EF7777]/15 text-[#EF7777] border border-[#EF7777]/30"
                              : "bg-[#9AA69C]/15 text-[#9AA69C] border border-[#9AA69C]/30"
                          }`}
                        >
                          {hyp.verdict.replace(/_/g, " ")}
                        </span>
                        <span className="font-mono text-xs font-bold px-2.5 py-0.5 rounded bg-[#0B0E0D] border border-[#232B26] text-[#E9EDE5]">
                          Score: {hyp.deterministic_score.toFixed(1)}
                        </span>
                        <button
                          type="button"
                          onClick={() => setExpandedHypId(isExpanded ? null : hyp.id)}
                          className="p-1 rounded hover:bg-[#1E2622] text-[#9AA69C] hover:text-[#E9EDE5] transition-colors cursor-pointer"
                        >
                          {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>

                    <p className="text-[#9AA69C] text-xs leading-relaxed font-sans">{hyp.statement}</p>

                    <div className="flex items-center gap-4 text-[11px] text-[#9AA69C] flex-wrap">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-[#647067]">Suspected Entity:</span>
                        <code className="text-[#72C6A0] font-mono bg-[#141A17] px-1.5 py-0.5 rounded border border-[#232B26]">
                          {hyp.suspected_entity}
                        </code>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-[#647067]">Causal Path:</span>
                        <span className={`font-mono text-[10px] ${hyp.causal_path_found ? "text-[#72C6A0]" : "text-[#DDAA60]"}`}>
                          {hyp.causal_path_found ? hyp.causal_path.join(" → ") : "None Detected"}
                        </span>
                      </div>
                    </div>

                    {/* Clickable Supporting & Contradicting Evidence references */}
                    <div className="pt-2 border-t border-[#1E2622] flex flex-wrap gap-4 text-[11px]">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="font-mono text-[#72C6A0] flex items-center gap-1">
                          <CheckCircle2 className="h-3.5 w-3.5" /> Supporting:
                        </span>
                        {hyp.supporting_evidence_ids.map((eid) => (
                          <button
                            key={eid}
                            type="button"
                            onClick={() => setSelectedEvidenceFilter(eid)}
                            className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#72C6A0]/10 border border-[#72C6A0]/30 text-[#72C6A0] hover:bg-[#72C6A0]/20 cursor-pointer transition-colors"
                          >
                            {eid}
                          </button>
                        ))}
                      </div>

                      {hyp.contradicting_evidence_ids.length > 0 && (
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-mono text-[#EF7777] flex items-center gap-1">
                            <XCircle className="h-3.5 w-3.5" /> Contradicting:
                          </span>
                          {hyp.contradicting_evidence_ids.map((eid) => (
                            <button
                              key={eid}
                              type="button"
                              onClick={() => setSelectedEvidenceFilter(eid)}
                              className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#EF7777]/10 border border-[#EF7777]/30 text-[#EF7777] hover:bg-[#EF7777]/20 cursor-pointer transition-colors"
                            >
                              {eid}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Collapsible Factor Breakdown */}
                    {isExpanded && (
                      <div className="mt-3 pt-3 border-t border-[#1E2622] space-y-3">
                        <span className="text-[10px] text-[#647067] uppercase font-mono font-semibold">
                          Deterministic Factor Contributions
                        </span>
                        <div className="grid grid-cols-1 gap-1.5 font-mono text-[11px]">
                          {hyp.score_factors.map((f, fidx) => (
                            <div
                              key={fidx}
                              className="p-2 rounded bg-[#0B0E0D] border border-[#232B26] flex items-center justify-between"
                            >
                              <div className="flex items-center gap-2">
                                <span
                                  className={`font-bold ${
                                    f.contribution > 0
                                      ? "text-[#72C6A0]"
                                      : f.contribution < 0
                                      ? "text-[#EF7777]"
                                      : "text-[#647067]"
                                  }`}
                                >
                                  {f.contribution > 0 ? `+${f.contribution}` : f.contribution}
                                </span>
                                <span className="text-[#E9EDE5] font-sans">{f.reason}</span>
                              </div>
                              <span className="text-[#647067] text-[10px]">{f.name}</span>
                            </div>
                          ))}
                        </div>

                        {hyp.recommended_action && (
                          <div className="p-2.5 rounded bg-[#72C6A0]/10 border border-[#72C6A0]/30 text-[#72C6A0] flex items-center gap-2">
                            <Terminal className="h-3.5 w-3.5 shrink-0" />
                            <span>Recommended: <strong className="font-mono">{hyp.recommended_action}</strong></span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* =========================================================================
            VIEW 4: GRAPH SURGERY EXPERIMENT WORKSPACE
            ========================================================================= */}
        {activeView === "graph_surgery" && (
          <div className="space-y-6">
            <div className="rounded-md border border-[#232B26] bg-[#111614] p-5 space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-[#1E2622]">
                <div className="flex items-center gap-2">
                  <Scissors className="h-4 w-4 text-[#EF7777]" />
                  <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E9EDE5]">
                    Graph Surgery: Counterfactual Incident Simulator
                  </h3>
                </div>
                <EpistemicBadge kind="SYNTHETIC" label="ISOLATED FALKORDB EXPERIMENT GRAPH" />
              </div>

              <p className="text-xs text-[#9AA69C] leading-relaxed font-sans">
                Execute genuine counterfactual graph surgery in FalkorDB using isolated graph-copying. Compare hypothesis rank shifts, causal path severance, and blast radius contractions side-by-side against the baseline.
              </p>

              {/* Controls Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs pt-1">
                <div>
                  <label className="block text-[11px] text-[#647067] font-mono font-medium mb-1">
                    Surgical Action
                  </label>
                  <select
                    value={surgeryActionType}
                    onChange={(e: any) => setSurgeryActionType(e.target.value)}
                    className="w-full bg-[#0B0E0D] border border-[#232B26] rounded p-2 text-xs text-[#E9EDE5] font-mono focus:outline-none focus:border-[#C8F169]"
                  >
                    <option value="remove_dependency">Sever Dependency (DEPENDS_ON)</option>
                    <option value="isolate_service">Isolate Service (All edges)</option>
                    <option value="rollback_deployment">Rollback Deployment (DEPLOYED_TO)</option>
                    <option value="remove_evidence">Sever Evidence Node</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] text-[#647067] font-mono font-medium mb-1">
                    Source Entity ID
                  </label>
                  <input
                    type="text"
                    value={surgerySourceId}
                    onChange={(e) => setSurgerySourceId(e.target.value)}
                    className="w-full bg-[#0B0E0D] border border-[#232B26] rounded p-2 font-mono text-xs text-[#E9EDE5] focus:outline-none focus:border-[#C8F169]"
                  />
                </div>

                {surgeryActionType === "remove_dependency" && (
                  <div>
                    <label className="block text-[11px] text-[#647067] font-mono font-medium mb-1">
                      Target Entity ID
                    </label>
                    <input
                      type="text"
                      value={surgeryTargetId}
                      onChange={(e) => setSurgeryTargetId(e.target.value)}
                      className="w-full bg-[#0B0E0D] border border-[#232B26] rounded p-2 font-mono text-xs text-[#E9EDE5] focus:outline-none focus:border-[#C8F169]"
                    />
                  </div>
                )}

                <div className="sm:col-span-2 lg:col-span-1">
                  <label className="block text-[11px] text-[#647067] font-mono font-medium mb-1">
                    Hypothesis Rationale
                  </label>
                  <input
                    type="text"
                    value={surgeryJustification}
                    onChange={(e) => setSurgeryJustification(e.target.value)}
                    className="w-full bg-[#0B0E0D] border border-[#232B26] rounded p-2 text-xs text-[#E9EDE5] focus:outline-none focus:border-[#C8F169]"
                  />
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-3 border-t border-[#1E2622] flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-[#647067] font-mono">Quick Scenarios:</span>
                  <button
                    type="button"
                    onClick={() => {
                      setSurgeryActionType("remove_dependency");
                      setSurgerySourceId("payment-core");
                      setSurgeryTargetId("payment-db-cluster");
                      setSurgeryRelType("DEPENDS_ON");
                      setSurgeryJustification("Isolate database to test if payment-core connection exhaustion is the true root cause");
                    }}
                    className="px-2.5 py-1 rounded bg-[#141A17] hover:bg-[#1E2622] text-[11px] text-[#9AA69C] hover:text-[#E9EDE5] border border-[#232B26] cursor-pointer font-mono transition-colors"
                  >
                    Sever Core &rarr; DB
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSurgeryActionType("remove_dependency");
                      setSurgerySourceId("auth-service");
                      setSurgeryTargetId("session-cache-redis");
                      setSurgeryRelType("DEPENDS_ON");
                      setSurgeryJustification("Sever unrelated auth cache to prove surgical precision");
                    }}
                    className="px-2.5 py-1 rounded bg-[#141A17] hover:bg-[#1E2622] text-[11px] text-[#9AA69C] hover:text-[#E9EDE5] border border-[#232B26] cursor-pointer font-mono transition-colors"
                  >
                    Unrelated Auth Edge
                  </button>
                </div>

                <button
                  type="button"
                  onClick={executeSurgerySimulation}
                  disabled={surgeryInProgress}
                  className="px-4 py-2 rounded bg-[#EF7777]/15 hover:bg-[#EF7777]/25 text-[#EF7777] border border-[#EF7777]/30 font-mono font-medium text-xs flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
                >
                  {surgeryInProgress ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      Cloning Graph &amp; Simulating...
                    </>
                  ) : (
                    <>
                      <Play className="h-3.5 w-3.5" />
                      Simulate Counterfactual
                    </>
                  )}
                </button>
              </div>

              {surgeryError && (
                <div className="p-3 rounded bg-[#EF7777]/10 border border-[#EF7777]/30 text-xs text-[#EF7777] flex items-center gap-2 font-mono">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>{surgeryError}</span>
                </div>
              )}
            </div>

            {/* Counterfactual Results Comparison */}
            {surgeryComparison && (
              <div className="space-y-4">
                <div className="p-3.5 rounded border border-[#89B8D9]/30 bg-[#89B8D9]/10 text-xs text-[#89B8D9] flex items-start gap-2.5">
                  <ShieldAlert className="h-4 w-4 text-[#89B8D9] shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-[#E9EDE5]">Scientific Framing Note:</span>{" "}
                    {surgeryComparison.disclaimer}
                  </div>
                </div>

                {/* Causal Shift Explanation */}
                <div className="p-4 rounded border border-[#232B26] bg-[#111614] space-y-2">
                  <div className="flex items-center gap-2 text-xs font-mono font-semibold uppercase tracking-wider text-[#EF7777]">
                    <Zap className="h-3.5 w-3.5 text-[#EF7777]" />
                    Causal Shift Explanation
                  </div>
                  <p className="text-xs text-[#9AA69C] leading-relaxed font-sans">
                    {surgeryComparison.causal_change_explanation}
                  </p>
                </div>

                {/* Side-by-Side Dual Interactive Topology Graphs */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs font-mono font-bold text-[#E9EDE5]">
                      <span className="flex items-center gap-1.5">
                        <Database className="w-3.5 h-3.5 text-[#72C6A0]" />
                        BASELINE GRAPH: traceforge
                      </span>
                      <EpistemicBadge kind="OBSERVED" label="100% UNTOUCHED" />
                    </div>
                    <div className="h-[440px] w-full relative">
                      <InteractiveTopologyGraph
                        services={investigation?.topology.traversed_services || []}
                        edges={investigation?.topology.dependency_edges || []}
                        selectedServiceId={surgeryComparison.blast_radius_diff.service_id}
                        onSelectService={() => {}}
                        highlightedPath={["payment-core", "payment-db-cluster"]}
                        showMiniMap={false}
                        tierSpacingX={280}
                        nodeSpacingY={100}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs font-mono font-bold text-[#EF7777]">
                      <span className="flex items-center gap-1.5">
                        <Scissors className="w-3.5 h-3.5 text-[#EF7777]" />
                        EXPERIMENT GRAPH: {surgeryComparison.experiment_id}
                      </span>
                      <EpistemicBadge kind="SYNTHETIC" label="SEVERED COUNTERFACTUAL" />
                    </div>
                    <div className="h-[440px] w-full relative">
                      <InteractiveTopologyGraph
                        services={investigation?.topology.traversed_services || []}
                        edges={investigation?.topology.dependency_edges || []}
                        selectedServiceId={surgeryComparison.blast_radius_diff.service_id}
                        onSelectService={() => {}}
                        severedEdges={[
                          {
                            source: surgerySourceId,
                            target: surgeryTargetId,
                          },
                        ]}
                        isExperiment={true}
                        showMiniMap={false}
                        tierSpacingX={280}
                        nodeSpacingY={100}
                      />
                    </div>
                  </div>
                </div>

                {/* Blast Radius Contraction */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs mt-4">
                  <div className="p-3 rounded border border-[#232B26] bg-[#111614]">
                    <span className="text-[10px] text-[#647067] uppercase font-mono font-semibold">
                      Target Tested Service
                    </span>
                    <p className="text-sm font-mono font-bold text-[#C8F169] mt-1">
                      {surgeryComparison.blast_radius_diff.service_id}
                    </p>
                  </div>
                  <div className="p-3 rounded border border-[#232B26] bg-[#111614]">
                    <span className="text-[10px] text-[#647067] uppercase font-mono font-semibold">
                      Downstream Blast Contraction
                    </span>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-sm font-mono font-bold text-[#9AA69C]">
                        {surgeryComparison.blast_radius_diff.baseline_downstream_count}
                      </span>
                      <ArrowRight className="h-3 w-3 text-[#EF7777]" />
                      <span className="text-sm font-mono font-bold text-[#EF7777]">
                        {surgeryComparison.blast_radius_diff.experiment_downstream_count} services
                      </span>
                    </div>
                  </div>
                  <div className="p-3 rounded border border-[#232B26] bg-[#111614]">
                    <span className="text-[10px] text-[#647067] uppercase font-mono font-semibold">
                      Severed Dependencies
                    </span>
                    <p className="text-xs font-mono text-[#72C6A0] mt-1 truncate">
                      {surgeryComparison.blast_radius_diff.severed_services.length > 0
                        ? surgeryComparison.blast_radius_diff.severed_services.join(", ")
                        : "No downstream cascade affected"}
                    </p>
                  </div>
                </div>

                {/* Side-by-Side Table */}
                <div className="rounded-md border border-[#232B26] bg-[#111614] p-4 space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-[#1E2622]">
                    <div className="flex items-center gap-2 text-xs font-mono font-semibold uppercase tracking-wider text-[#E9EDE5]">
                      <Split className="h-3.5 w-3.5 text-[#72C6A0]" />
                      Side-by-Side Hypothesis Shift (Baseline vs. Experiment)
                    </div>
                    <span className="text-[11px] font-mono text-[#647067]">
                      ID: {surgeryComparison.experiment_id}
                    </span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-[#1E2622] text-[10px] text-[#647067] uppercase font-mono">
                          <th className="py-2.5 px-3">Hypothesis</th>
                          <th className="py-2.5 px-3">Baseline</th>
                          <th className="py-2.5 px-3">Experiment</th>
                          <th className="py-2.5 px-3">Score Delta</th>
                          <th className="py-2.5 px-3">Causal Path</th>
                          <th className="py-2.5 px-3">Evidence State</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1E2622] font-sans">
                        {surgeryComparison.hypothesis_diffs.map((diff) => (
                          <React.Fragment key={diff.hypothesis_id}>
                            <tr
                              onClick={() =>
                                setExpandedHypothesisDiff(
                                  expandedHypothesisDiff === diff.hypothesis_id ? null : diff.hypothesis_id
                                )
                              }
                              className="hover:bg-[#171E1A] cursor-pointer transition-colors"
                            >
                              <td className="py-3 px-3 font-medium text-[#E9EDE5]">
                                <div className="flex items-center gap-1.5">
                                  <ChevronRight
                                    className={`h-3 w-3 text-[#647067] transition-transform ${
                                      expandedHypothesisDiff === diff.hypothesis_id ? "rotate-90 text-[#C8F169]" : ""
                                    }`}
                                  />
                                  <div className="font-semibold text-[#E9EDE5]">{diff.title}</div>
                                </div>
                                <div className="text-[10px] font-mono text-[#647067] pl-4.5">{diff.hypothesis_id}</div>
                              </td>
                              <td className="py-3 px-3 font-mono">
                                <span className="text-[#E9EDE5] font-bold">#{diff.baseline_rank}</span>
                                <span className="text-[#647067] ml-1.5">({diff.baseline_score?.toFixed(2)})</span>
                              </td>
                              <td className="py-3 px-3 font-mono">
                                <span className={`font-bold ${diff.experiment_rank !== diff.baseline_rank ? "text-[#DDAA60]" : "text-[#E9EDE5]"}`}>
                                  #{diff.experiment_rank}
                                </span>
                                <span className="text-[#647067] ml-1.5">({diff.experiment_score?.toFixed(2)})</span>
                              </td>
                              <td className="py-3 px-3 font-mono">
                                <span
                                  className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                                    diff.score_delta < 0
                                      ? "bg-[#EF7777]/15 text-[#EF7777] border border-[#EF7777]/30"
                                      : diff.score_delta > 0
                                      ? "bg-[#72C6A0]/15 text-[#72C6A0] border border-[#72C6A0]/30"
                                      : "bg-[#141A17] text-[#647067]"
                                  }`}
                                >
                                  {diff.score_delta > 0 ? `+${diff.score_delta.toFixed(2)}` : diff.score_delta.toFixed(2)}
                                </span>
                              </td>
                              <td className="py-3 px-3">
                                {diff.causal_path_changed ? (
                                  <span className="text-[11px] font-semibold text-[#EF7777] flex items-center gap-1 font-mono">
                                    <Scissors className="h-3 w-3" /> Severed
                                  </span>
                                ) : (
                                  <span className="text-[11px] text-[#9AA69C] font-mono">Intact</span>
                                )}
                              </td>
                              <td className="py-3 px-3 text-[11px] text-[#9AA69C]">
                                <div>{diff.evidence_diff_summary}</div>
                                {diff.score_delta_explanation && (
                                  <div className="text-[10px] text-[#647067] font-mono mt-0.5 truncate max-w-xs">
                                    {diff.score_delta_explanation}
                                  </div>
                                )}
                              </td>
                            </tr>
                            {/* Expandable Auditable Score Factor Breakdown */}
                            {expandedHypothesisDiff === diff.hypothesis_id && (
                              <tr className="bg-[#0B0E0D] border-b border-[#1E2622]">
                                <td colSpan={6} className="p-3.5 space-y-2.5">
                                  <div className="flex items-center justify-between text-[11px] font-mono">
                                    <span className="text-[#72C6A0] font-semibold flex items-center gap-1.5">
                                      <Info className="w-3.5 h-3.5 text-[#72C6A0]" />
                                      Auditable Score Factor Attribution Breakdown ({diff.hypothesis_id})
                                    </span>
                                    <span className="text-[#9AA69C]">
                                      Score Delta: <strong className={diff.score_delta < 0 ? "text-[#EF7777]" : "text-[#72C6A0]"}>{diff.score_delta > 0 ? `+${diff.score_delta}` : diff.score_delta}</strong>
                                    </span>
                                  </div>
                                  <p className="text-xs text-[#9AA69C] font-sans leading-relaxed bg-[#141A17] p-2.5 rounded border border-[#232B26]">
                                    <strong className="text-[#E9EDE5]">Score Shift Rationale:</strong> {diff.score_delta_explanation || "No factor contribution divergence detected."}
                                  </p>
                                  {diff.factor_diffs && diff.factor_diffs.length > 0 ? (
                                    <div className="space-y-1.5 pt-1">
                                      <div className="text-[10px] font-mono uppercase text-[#647067] font-semibold tracking-wider">
                                        Shifted Scoring Factors (Baseline vs Counterfactual Experiment)
                                      </div>
                                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                                        {diff.factor_diffs.map((fd, fIdx) => (
                                          <div key={fIdx} className="p-2.5 rounded bg-[#111614] border border-[#232B26] text-[11px] space-y-1">
                                            <div className="flex items-center justify-between font-mono">
                                              <span className="font-semibold text-[#E9EDE5]">{fd.factor_name.replace(/_/g, " ").toUpperCase()}</span>
                                              <span className={`px-1.5 py-0.2 rounded font-bold ${fd.contribution_delta < 0 ? "text-[#EF7777] bg-[#EF7777]/10" : "text-[#72C6A0] bg-[#72C6A0]/10"}`}>
                                                Δ {fd.contribution_delta > 0 ? `+${fd.contribution_delta}` : fd.contribution_delta}
                                              </span>
                                            </div>
                                            <div className="text-[10px] text-[#647067] flex items-center justify-between font-mono">
                                              <span>Baseline: {fd.baseline_contribution > 0 ? `+${fd.baseline_contribution}` : fd.baseline_contribution}</span>
                                              <span>Experiment: {fd.experiment_contribution > 0 ? `+${fd.experiment_contribution}` : fd.experiment_contribution}</span>
                                            </div>
                                            <div className="text-[10px] text-[#9AA69C] pt-1 border-t border-[#1E2622]">
                                              <span className="text-[#647067] font-mono">Experiment:</span> {fd.experiment_reason}
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  ) : (
                                    <div className="text-[11px] text-[#647067] font-mono">
                                      All underlying mathematical scoring factors evaluated identically between graphs.
                                    </div>
                                  )}
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="flex items-center justify-between p-3 rounded bg-[#72C6A0]/10 border border-[#72C6A0]/30 text-xs text-[#72C6A0]">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-[#72C6A0]" />
                    <span>Baseline graph <strong className="font-mono">traceforge</strong> remained 100% pristine throughout simulation.</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSurgeryComparison(null)}
                    className="px-3 py-1 rounded bg-[#171E1A] hover:bg-[#1E2622] text-[#72C6A0] border border-[#72C6A0]/30 font-mono font-medium cursor-pointer flex items-center gap-1.5 transition-colors"
                  >
                    <RotateCcw className="h-3 w-3" /> Reset Simulator
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* =========================================================================
            VIEW 5: SAFE RECOVERY CONSOLE
            ========================================================================= */}
        {activeView === "recovery_console" && (
          <div className="space-y-6">
            <div className="rounded-md border border-[#232B26] bg-[#111614] p-5 space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-[#1E2622]">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-[#72C6A0]" />
                  <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E9EDE5]">
                    Safe Simulated Recovery Console
                  </h3>
                </div>
                <EpistemicBadge kind="SYNTHETIC" label="DRY-RUN ISOLATED SIMULATION ONLY" />
              </div>

              <p className="text-xs text-[#9AA69C] leading-relaxed font-sans">
                Non-destructive execution console. Enforces policy checks, allowlisted recovery actions, target validation, and human cryptographic sign-off before simulation runs in FalkorDB.
              </p>

              {recoveryError && (
                <div className="p-3 rounded bg-[#EF7777]/10 border border-[#EF7777]/30 text-xs text-[#EF7777] flex items-center gap-2 font-mono">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{recoveryError}</span>
                </div>
              )}
            </div>

            {/* Proposal Submission Form */}
            <div className="rounded-md border border-[#232B26] bg-[#111614] p-5 space-y-4">
              <h4 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E9EDE5] flex items-center gap-1.5 pb-2 border-b border-[#1E2622]">
                <Sliders className="h-4 w-4 text-[#72C6A0]" />
                Propose New Remediation Action
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
                <div>
                  <label className="block text-[11px] text-[#647067] font-mono font-medium mb-1">
                    Action Type (Allowlisted)
                  </label>
                  <select
                    value={newActionType}
                    onChange={(e) => setNewActionType(e.target.value)}
                    className="w-full bg-[#0B0E0D] border border-[#232B26] rounded p-2 text-xs text-[#E9EDE5] font-mono focus:outline-none focus:border-[#72C6A0]"
                  >
                    <option value="rollback_deployment">Rollback Deployment</option>
                    <option value="restart_service">Restart Service Pods</option>
                    <option value="scale_replicas">Scale Worker Replicas</option>
                    <option value="drain_connections">Drain Idle Connections</option>
                    <option value="toggle_circuit_breaker">Toggle Circuit Breaker</option>
                    <option value="isolate_cluster">Isolate Degraded Cluster</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] text-[#647067] font-mono font-medium mb-1">
                    Target Service
                  </label>
                  <input
                    type="text"
                    value={newTargetService}
                    onChange={(e) => setNewTargetService(e.target.value)}
                    className="w-full bg-[#0B0E0D] border border-[#232B26] rounded p-2 font-mono text-xs text-[#E9EDE5] focus:outline-none focus:border-[#72C6A0]"
                  />
                </div>

                {newActionType === "rollback_deployment" && (
                  <div>
                    <label className="block text-[11px] text-[#647067] font-mono font-medium mb-1">
                      Target Revision
                    </label>
                    <input
                      type="text"
                      value={newRevision}
                      onChange={(e) => setNewRevision(e.target.value)}
                      className="w-full bg-[#0B0E0D] border border-[#232B26] rounded p-2 font-mono text-xs text-[#E9EDE5] focus:outline-none focus:border-[#72C6A0]"
                    />
                  </div>
                )}

                <div>
                  <label className="block text-[11px] text-[#647067] font-mono font-medium mb-1">
                    Runbook ID
                  </label>
                  <input
                    type="text"
                    value={newRunbookId}
                    onChange={(e) => setNewRunbookId(e.target.value)}
                    className="w-full bg-[#0B0E0D] border border-[#232B26] rounded p-2 font-mono text-xs text-[#E9EDE5] focus:outline-none focus:border-[#72C6A0]"
                  />
                </div>

                <div>
                  <label className="block text-[11px] text-[#647067] font-mono font-medium mb-1">
                    Runbook Step ID
                  </label>
                  <input
                    type="text"
                    value={newStepId}
                    onChange={(e) => setNewStepId(e.target.value)}
                    className="w-full bg-[#0B0E0D] border border-[#232B26] rounded p-2 font-mono text-xs text-[#E9EDE5] focus:outline-none focus:border-[#72C6A0]"
                  />
                </div>

                <div>
                  <label className="block text-[11px] text-[#647067] font-mono font-medium mb-1">
                    Engineering Justification
                  </label>
                  <input
                    type="text"
                    value={newJustification}
                    onChange={(e) => setNewJustification(e.target.value)}
                    className="w-full bg-[#0B0E0D] border border-[#232B26] rounded p-2 text-xs text-[#E9EDE5] focus:outline-none focus:border-[#72C6A0]"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={submitRecoveryProposal}
                  className="px-4 py-2 rounded bg-[#72C6A0]/15 hover:bg-[#72C6A0]/25 text-[#72C6A0] border border-[#72C6A0]/30 font-mono font-medium text-xs flex items-center gap-1.5 cursor-pointer transition-colors"
                >
                  <CheckSquare className="h-3.5 w-3.5" />
                  Submit Proposal for Policy Verification
                </button>
              </div>
            </div>

            {/* Proposals List & Approver Bar */}
            <div className="space-y-4">
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-[#9AA69C] block">
                Recovery Actions & Approval Bar ({recoveryProposals.length})
              </span>

              {recoveryLoading ? (
                <div className="h-32 flex items-center justify-center text-[#647067] text-xs font-mono">
                  <RefreshCw className="h-4 w-4 animate-spin text-[#72C6A0] mr-2" />
                  Evaluating recovery proposals...
                </div>
              ) : recoveryProposals.length > 0 ? (
                <div className="space-y-3">
                  {recoveryProposals.map((prop) => {
                    const isAwaiting = prop.state === "AWAITING_APPROVAL";
                    const isApproved = prop.state === "APPROVED";
                    const isSucceeded = prop.state === "SUCCEEDED";
                    const isRejected = prop.state === "REJECTED";

                    return (
                      <div
                        key={prop.action_id}
                        className={`rounded-md border p-5 text-xs space-y-3 transition-colors ${
                          isSucceeded
                            ? "bg-[#111614] border-[#72C6A0]/40"
                            : isApproved
                            ? "bg-[#111614] border-[#89B8D9]/40"
                            : isAwaiting
                            ? "bg-[#111614] border-[#DDAA60]/40"
                            : isRejected
                            ? "bg-[#111614] border-[#EF7777]/40"
                            : "bg-[#111614] border-[#232B26]"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2 flex-wrap">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-[9px] uppercase font-bold font-mono px-2 py-0.5 rounded ${
                                isSucceeded
                                  ? "bg-[#72C6A0]/15 text-[#72C6A0] border border-[#72C6A0]/30"
                                  : isApproved
                                  ? "bg-[#89B8D9]/15 text-[#89B8D9] border border-[#89B8D9]/30"
                                  : isAwaiting
                                  ? "bg-[#DDAA60]/15 text-[#DDAA60] border border-[#DDAA60]/30"
                                  : isRejected
                                  ? "bg-[#EF7777]/15 text-[#EF7777] border border-[#EF7777]/30"
                                  : "bg-[#141A17] text-[#647067]"
                              }`}
                            >
                              {prop.state}
                            </span>
                            <span className="font-mono text-xs font-bold text-[#E9EDE5]">
                              {prop.action_id}
                            </span>
                            <span className="text-[10px] font-mono text-[#9AA69C]">
                              {prop.action_type} &rarr; {prop.target_service_id}
                            </span>
                          </div>
                          <span className="text-[10px] font-mono text-[#647067]">
                            Hash: {prop.proposal_hash.slice(0, 16)}...
                          </span>
                        </div>

                        <p className="text-[11px] text-[#9AA69C] leading-relaxed font-sans">
                          {prop.justification}
                        </p>

                        {/* Policy Preconditions */}
                        <div className="p-3 rounded border border-[#232B26] bg-[#0B0E0D] space-y-1.5">
                          <div className="text-[10px] text-[#647067] uppercase font-mono font-semibold">
                            Policy Gate Results:
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                            {prop.validation_results.map((vr, vidx) => (
                              <div key={vidx} className="flex items-center gap-1.5 font-mono">
                                {vr.passed ? (
                                  <CheckCircle2 className="h-3.5 w-3.5 text-[#72C6A0] shrink-0" />
                                ) : (
                                  <XCircle className="h-3.5 w-3.5 text-[#EF7777] shrink-0" />
                                )}
                                <span className={vr.passed ? "text-[#E9EDE5]" : "text-[#EF7777]"}>
                                  {vr.details}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Simulation Success Output */}
                        {isSucceeded && prop.simulation_output && (
                          <div className="p-3.5 rounded border border-[#72C6A0]/30 bg-[#72C6A0]/10 space-y-1 text-[11px]">
                            <div className="flex items-center justify-between text-[#72C6A0] font-semibold">
                              <span className="flex items-center gap-1.5 font-mono">
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                Simulation Succeeded (Non-Destructive)
                              </span>
                              <span className="font-mono text-[10px]">
                                Real Infra Mutated: NO
                              </span>
                            </div>
                            <p className="text-[#9AA69C] pt-1 font-sans">
                              {prop.simulation_output.simulated_topological_effect}
                            </p>
                          </div>
                        )}

                        {/* Interactive Approver Decision Strip */}
                        <div className="flex items-center justify-between pt-2 border-t border-[#1E2622] flex-wrap gap-2">
                          <div className="text-[10px] text-[#647067] font-mono">
                            Created: {new Date(prop.created_at).toLocaleTimeString()}
                            {prop.approver && ` · Signed by: ${prop.approver}`}
                          </div>

                          {isAwaiting && (
                            <div className="flex items-center gap-2 flex-wrap">
                              <input
                                type="text"
                                placeholder="Approver email..."
                                value={approverName}
                                onChange={(e) => setApproverName(e.target.value)}
                                className="bg-[#0B0E0D] border border-[#232B26] rounded px-2 py-1 text-[11px] text-[#E9EDE5] font-mono"
                              />
                              <input
                                type="text"
                                placeholder="Role..."
                                value={approverRole}
                                onChange={(e) => setApproverRole(e.target.value)}
                                className="bg-[#0B0E0D] border border-[#232B26] rounded px-2 py-1 text-[11px] text-[#E9EDE5] font-mono"
                              />
                              <input
                                type="text"
                                placeholder="Audit notes..."
                                value={approvalNotes}
                                onChange={(e) => setApprovalNotes(e.target.value)}
                                className="bg-[#0B0E0D] border border-[#232B26] rounded px-2 py-1 text-[11px] text-[#E9EDE5]"
                              />
                              <button
                                type="button"
                                onClick={() => decideRecoveryProposal(prop.action_id, "APPROVED", prop.proposal_hash)}
                                className="px-3 py-1 rounded bg-[#72C6A0]/20 hover:bg-[#72C6A0]/30 text-[#72C6A0] border border-[#72C6A0]/40 font-mono font-medium text-xs flex items-center gap-1 cursor-pointer transition-colors"
                              >
                                <ThumbsUp className="h-3 w-3" />
                                Approve
                              </button>
                              <button
                                type="button"
                                onClick={() => decideRecoveryProposal(prop.action_id, "REJECTED", prop.proposal_hash)}
                                className="px-3 py-1 rounded bg-[#EF7777]/20 hover:bg-[#EF7777]/30 text-[#EF7777] border border-[#EF7777]/40 font-mono font-medium text-xs flex items-center gap-1 cursor-pointer transition-colors"
                              >
                                <ThumbsDown className="h-3 w-3" />
                                Reject
                              </button>
                            </div>
                          )}

                          {isApproved && (
                            <button
                              type="button"
                              onClick={() => simulateRecoveryProposal(prop.action_id, prop.approver || approverName, prop.proposal_hash)}
                              className="px-3.5 py-1.5 rounded bg-[#89B8D9]/20 hover:bg-[#89B8D9]/30 text-[#89B8D9] border border-[#89B8D9]/40 font-mono font-medium text-xs flex items-center gap-1.5 cursor-pointer transition-colors"
                            >
                              <Play className="h-3.5 w-3.5" />
                              Execute Safe Simulation
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="h-28 flex items-center justify-center text-[#647067] text-xs font-mono">
                  No recovery proposals recorded for this scenario.
                </div>
              )}
            </div>
          </div>
        )}

        {/* =========================================================================
            VIEW 6: HISTORICAL MEMORY AND EVIDENCE DEBT
            ========================================================================= */}
        {activeView === "memory_debt" && (
          <div className="space-y-6">
            <div className="rounded-md border border-[#232B26] bg-[#111614] p-5 space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-[#1E2622]">
                <div className="flex items-center gap-2">
                  <Scale className="h-4 w-4 text-[#C8F169]" />
                  <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E9EDE5]">
                    Historical Memory, Precedents &amp; Evidence Debt
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <EpistemicBadge kind="OBSERVED" label="TOPOLOGICAL PRECEDENTS" />
                  <EpistemicBadge kind="INFERRED" label="RUNBOOK VERIFICATION" />
                </div>
              </div>

              <p className="text-xs text-[#9AA69C] leading-relaxed font-sans">
                Persistent institutional knowledge retrieved from FalkorDB. Evaluates structural similarities against past outages, verifies runbook prerequisites, and tracks evidence gaps blocking safe actions.
              </p>
            </div>

            {/* Sub-tab navigation */}
            <div className="flex border-b border-[#1E2622] gap-4 text-xs font-mono">
              <button
                type="button"
                onClick={() => setActiveMemoryTab("comparisons")}
                className={`pb-2.5 flex items-center gap-1.5 transition-colors cursor-pointer shrink-0 ${
                  activeMemoryTab === "comparisons"
                    ? "border-b-2 border-[#C8F169] text-[#C8F169] font-semibold"
                    : "text-[#9AA69C] hover:text-[#E9EDE5]"
                }`}
              >
                <BookmarkCheck className="h-3.5 w-3.5 text-[#C8F169]" />
                Cross-Incident Precedents ({memoryComparison?.total_relevant_found || 0})
              </button>

              <button
                type="button"
                onClick={() => setActiveMemoryTab("debt_registry")}
                className={`pb-2.5 flex items-center gap-1.5 transition-colors cursor-pointer shrink-0 ${
                  activeMemoryTab === "debt_registry"
                    ? "border-b-2 border-[#DDAA60] text-[#DDAA60] font-semibold"
                    : "text-[#9AA69C] hover:text-[#E9EDE5]"
                }`}
              >
                <FileQuestion className="h-3.5 w-3.5 text-[#DDAA60]" />
                Evidence Debt Workbench ({debtReport?.summary.total_gaps || 0})
              </button>

              <button
                type="button"
                onClick={() => setActiveMemoryTab("investigation_archive")}
                className={`pb-2.5 flex items-center gap-1.5 transition-colors cursor-pointer shrink-0 ${
                  activeMemoryTab === "investigation_archive"
                    ? "border-b-2 border-[#89B8D9] text-[#89B8D9] font-semibold"
                    : "text-[#9AA69C] hover:text-[#E9EDE5]"
                }`}
              >
                <History className="h-3.5 w-3.5 text-[#89B8D9]" />
                Investigation Archive ({historicalInvestigations.length})
              </button>
            </div>

            {/* Sub-Tab 1: Cross-Incident Precedents */}
            {activeMemoryTab === "comparisons" && (
              <div className="space-y-4">
                {memoryLoading ? (
                  <div className="h-40 flex items-center justify-center text-[#9AA69C] text-xs gap-2 font-mono">
                    <RefreshCw className="h-4 w-4 animate-spin text-[#C8F169]" />
                    Querying FalkorDB historical memory...
                  </div>
                ) : memoryComparison && memoryComparison.historical_comparisons.length > 0 ? (
                  memoryComparison.historical_comparisons.map((comp) => {
                    const isRelevant = comp.is_relevant;
                    const hasRealOutcome = comp.verified_recovery_outcomes.length > 0;

                    return (
                      <div
                        key={comp.historical_incident_id}
                        className={`p-5 rounded-md border transition-colors space-y-3.5 ${
                          isRelevant
                            ? "border-[#72C6A0]/40 bg-[#111614]"
                            : "border-[#232B26] bg-[#0B0E0D] opacity-70"
                        }`}
                      >
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <div className="flex items-center gap-2.5">
                            <span className="font-mono text-xs font-bold text-[#C8F169]">
                              {comp.historical_incident_id}
                            </span>
                            <span className="text-xs font-semibold text-[#E9EDE5] font-sans">
                              {comp.historical_title}
                            </span>
                          </div>
                          <span
                            className={`text-[10px] uppercase font-bold font-mono px-2 py-0.5 rounded border ${
                              isRelevant
                                ? "bg-[#72C6A0]/15 text-[#72C6A0] border-[#72C6A0]/30"
                                : "bg-[#141A17] text-[#647067] border-[#232B26]"
                            }`}
                          >
                            {isRelevant ? `Relevant (${Math.round(comp.relevance_score * 100)}%)` : "Not Relevant"}
                          </span>
                        </div>

                        <div className="p-3 rounded border border-[#232B26] bg-[#141A17] text-xs text-[#9AA69C]">
                          <span className="font-semibold text-[#E9EDE5]">Relevance Attribution: </span>
                          {comp.relevance_explanation}
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                          <div className="p-3 rounded border border-[#232B26] bg-[#141A17] space-y-1">
                            <span className="font-mono font-semibold text-[#72C6A0] text-[11px] uppercase tracking-wider block">
                              Shared Topology & Evidence:
                            </span>
                            <ul className="space-y-1 text-[#9AA69C] text-[11px]">
                              {comp.evidence_similarities.map((sim, sidx) => (
                                <li key={sidx} className="flex items-start gap-1.5">
                                  <span className="text-[#72C6A0] font-bold">•</span>
                                  <span>{sim}</span>
                                </li>
                              ))}
                            </ul>
                          </div>

                          <div className="p-3 rounded border border-[#232B26] bg-[#141A17] space-y-1">
                            <span className="font-mono font-semibold text-[#DDAA60] text-[11px] uppercase tracking-wider block">
                              Key Differences:
                            </span>
                            <ul className="space-y-1 text-[#9AA69C] text-[11px]">
                              {comp.evidence_differences.map((diff, didx) => (
                                <li key={didx} className="flex items-start gap-1.5">
                                  <span className="text-[#DDAA60] font-bold">•</span>
                                  <span>{diff}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>

                        {/* Verified historical outcomes */}
                        {hasRealOutcome && (
                          <div className="p-3 rounded border border-[#72C6A0]/20 bg-[#72C6A0]/10 text-xs space-y-1">
                            <span className="font-mono font-semibold text-[#72C6A0] text-[11px] uppercase tracking-wider">
                              Verified Past Resolution:
                            </span>
                            {comp.verified_recovery_outcomes.map((act, aidx) => (
                              <div key={aidx} className="text-[#E9EDE5] font-mono text-[11px]">
                                &bull; {act.action_type} &rarr; Status: {act.status}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="h-32 flex items-center justify-center text-[#647067] text-xs font-mono">
                    No related incidents discovered in the graph memory.
                  </div>
                )}
              </div>
            )}

            {/* Sub-Tab 2: Evidence Debt Registry */}
            {activeMemoryTab === "debt_registry" && (
              <div className="space-y-4">
                {debtReport && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                    <div className="p-3 rounded border border-[#232B26] bg-[#111614]">
                      <span className="text-[10px] text-[#647067] uppercase font-mono font-semibold">Total Gaps</span>
                      <p className="mt-0.5 text-lg font-bold text-[#E9EDE5] font-mono">
                        {debtReport.summary.total_gaps}
                      </p>
                    </div>
                    <div className="p-3 rounded border border-[#EF7777]/30 bg-[#EF7777]/10">
                      <span className="text-[10px] text-[#EF7777] uppercase font-mono font-semibold">Blocking Actions</span>
                      <p className="mt-0.5 text-lg font-bold text-[#EF7777] font-mono">
                        {debtReport.summary.blocking_count}
                      </p>
                    </div>
                    <div className="p-3 rounded border border-[#DDAA60]/30 bg-[#DDAA60]/10">
                      <span className="text-[10px] text-[#DDAA60] uppercase font-mono font-semibold">Telemetry Warnings</span>
                      <p className="mt-0.5 text-lg font-bold text-[#DDAA60] font-mono">
                        {debtReport.summary.warning_count}
                      </p>
                    </div>
                    <div className="p-3 rounded border border-[#72C6A0]/30 bg-[#72C6A0]/10">
                      <span className="text-[10px] text-[#72C6A0] uppercase font-mono font-semibold">Resolved in Graph</span>
                      <p className="mt-0.5 text-lg font-bold text-[#72C6A0] font-mono">
                        {debtReport.summary.resolved_count}
                      </p>
                    </div>
                  </div>
                )}

                {debtReport && debtReport.blocked_recovery_actions.length > 0 && (
                  <div className="p-3.5 rounded border border-[#EF7777]/30 bg-[#EF7777]/10 text-xs text-[#EF7777] space-y-1.5">
                    <div className="flex items-center gap-2 font-mono font-bold text-[#EF7777]">
                      <Lock className="h-4 w-4 text-[#EF7777]" />
                      <span>Recovery Actions Blocked by Evidence Debt:</span>
                    </div>
                    <ul className="list-disc list-inside space-y-0.5 text-[11px] text-[#EF7777]/90 font-mono pl-1">
                      {debtReport.blocked_recovery_actions.map((act, aidx) => (
                        <li key={aidx}>{act}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {debtLoading ? (
                  <div className="h-32 flex items-center justify-center text-[#647067] text-xs font-mono">
                    <RefreshCw className="h-4 w-4 animate-spin text-[#DDAA60] mr-2" />
                    Auditing graph knowledge debt...
                  </div>
                ) : (
                  <div className="space-y-3">
                    {debtReport?.gaps.map((gap) => {
                      const isBlocking = gap.severity === "BLOCKING";
                      const isResolved = gap.status === "RESOLVED";

                      return (
                      <div
                        key={gap.id}
                        className={`rounded-md border p-4 text-xs space-y-2.5 transition-colors ${
                          isResolved
                            ? "bg-[#111614] border-[#72C6A0]/30 opacity-75"
                            : isBlocking
                            ? "bg-[#111614] border-[#EF7777]/40"
                            : "bg-[#111614] border-[#DDAA60]/30"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-[9px] uppercase font-bold font-mono px-2 py-0.5 rounded ${
                                isResolved
                                  ? "bg-[#72C6A0]/15 text-[#72C6A0] border border-[#72C6A0]/30"
                                  : isBlocking
                                  ? "bg-[#EF7777]/15 text-[#EF7777] border border-[#EF7777]/30"
                                  : "bg-[#DDAA60]/15 text-[#DDAA60] border border-[#DDAA60]/30"
                              }`}
                            >
                              {isResolved ? "RESOLVED" : gap.severity}
                            </span>
                            <span className="font-mono text-[10px] text-[#647067]">{gap.id}</span>
                          </div>
                          <span className="text-[10px] font-mono text-[#647067]">{gap.provenance}</span>
                        </div>

                        <div>
                          <h5 className="font-semibold text-[#E9EDE5] text-xs font-sans">{gap.title}</h5>
                          <p className="mt-1 text-[11px] text-[#9AA69C] leading-relaxed font-sans">
                            {gap.why_it_matters}
                          </p>
                        </div>

                        <div className="p-2.5 rounded bg-[#0B0E0D] border border-[#232B26] text-[11px] space-y-1">
                          <div className="text-[#647067] font-mono font-semibold">Resolving Evidence Required:</div>
                          <div className="text-[#72C6A0] font-sans">{gap.resolving_evidence}</div>
                        </div>

                        <div className="flex items-center justify-between pt-1 border-t border-[#1E2622]">
                          <div className="text-[10px] text-[#647067] font-mono">
                            Entities: {gap.affected_entities.join(", ") || "General"}
                          </div>

                          {!isResolved ? (
                            selectedDebtGapId === gap.id ? (
                              <div className="flex items-center gap-2">
                                <input
                                  type="text"
                                  placeholder="Verification notes..."
                                  value={debtResolutionNote}
                                  onChange={(e) => setDebtResolutionNote(e.target.value)}
                                  className="bg-[#0B0E0D] border border-[#232B26] rounded px-2 py-1 text-[11px] text-[#E9EDE5] font-mono"
                                />
                                <button
                                  type="button"
                                  onClick={() => resolveDebtGap(gap.id)}
                                  className="px-2.5 py-1 rounded bg-[#72C6A0]/20 hover:bg-[#72C6A0]/30 text-[#72C6A0] border border-[#72C6A0]/40 font-mono font-medium text-[11px] flex items-center gap-1 cursor-pointer transition-colors"
                                >
                                  <Check className="h-3 w-3" /> Commit
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setSelectedDebtGapId(null)}
                                  className="px-2 py-1 text-[11px] text-[#647067] hover:text-[#E9EDE5] cursor-pointer font-mono"
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedDebtGapId(gap.id);
                                  setDebtResolutionNote(`Verified telemetry for ${gap.id}`);
                                }}
                                className="px-2.5 py-1 rounded bg-[#141A17] hover:bg-[#1E2622] text-[#9AA69C] hover:text-[#E9EDE5] border border-[#232B26] text-[11px] font-mono flex items-center gap-1 cursor-pointer transition-colors"
                              >
                                <Check className="h-3 w-3 text-[#72C6A0]" />
                                Resolve in FalkorDB
                              </button>
                            )
                          ) : (
                            <span className="text-[10px] text-[#72C6A0] flex items-center gap-1 font-mono font-semibold">
                              <CheckCircle2 className="h-3 w-3" /> Resolution Persisted in Graph
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
              </div>
            )}

            {/* Sub-Tab 3: Investigation Archive */}
            {activeMemoryTab === "investigation_archive" && (
              <div className="space-y-3">
                {historicalInvestigations.map((inv) => (
                  <div
                    key={inv.investigation_id}
                    className="p-4 rounded-md border border-[#232B26] bg-[#111614] space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[#89B8D9] font-bold">{inv.investigation_id}</span>
                        <span className="text-[#E9EDE5] font-semibold font-sans">{inv.incident_title}</span>
                        <span className="text-[10px] font-mono text-[#647067] px-1.5 py-0.5 rounded bg-[#0B0E0D] border border-[#232B26]">
                          {inv.incident_id}
                        </span>
                      </div>
                      <EpistemicBadge
                        kind={
                          inv.provenance.epistemic_status === "VERIFIED_OBSERVATION"
                            ? "OBSERVED"
                            : inv.provenance.epistemic_status === "SIMULATED_DRY_RUN"
                            ? "SYNTHETIC"
                            : "HYPOTHETICAL"
                        }
                        label={inv.provenance.epistemic_status.replace(/_/g, " ")}
                      />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1 font-mono text-[11px]">
                      <div className="p-2 rounded bg-[#0B0E0D] border border-[#232B26]">
                        <span className="text-[10px] text-[#647067] uppercase">Top Hypothesis</span>
                        <p className="text-[#E9EDE5] truncate mt-0.5">{inv.top_hypothesis_title || "None"}</p>
                      </div>
                      <div className="p-2 rounded bg-[#0B0E0D] border border-[#232B26]">
                        <span className="text-[10px] text-[#647067] uppercase">Score / Verdict</span>
                        <p className="text-[#DDAA60] font-bold mt-0.5">
                          {inv.top_hypothesis_score != null ? `${inv.top_hypothesis_score.toFixed(2)}` : "N/A"}
                        </p>
                      </div>
                      <div className="p-2 rounded bg-[#0B0E0D] border border-[#232B26]">
                        <span className="text-[10px] text-[#647067] uppercase">Verified Actions</span>
                        <p className="text-[#72C6A0] font-bold mt-0.5">
                          {inv.verified_recovery_actions.length} action(s)
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  </main>

      {/* Footer */}
      <footer className="border-t border-[#1E2622] py-3.5 px-6 text-center text-xs text-[#647067] font-mono">
        TraceForge Mission Command Center · WeMakeDevs × FalkorDB Graph Hacks · Zero Synthetic Fake Metrics
      </footer>
    </div>
  );
}

export default App;
