from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class IncidentBase(BaseModel):
    id: str
    title: str
    severity: str
    status: str
    started_at: str
    resolved_at: Optional[str] = ""
    summary: str


class ServiceNode(BaseModel):
    id: str
    name: str
    tier: int
    team: str
    status: str


class AlertItem(BaseModel):
    id: str
    service_id: str
    service_name: str
    name: str
    severity: str
    source: str
    timestamp: str
    description: str
    metric_name: Optional[str] = None
    value: Optional[float] = None


class MetricObservationItem(BaseModel):
    id: str
    alert_id: str
    metric_name: str
    timestamp: str
    value: float
    baseline: float
    deviation_sigma: float
    unit: str


class DeploymentItem(BaseModel):
    id: str
    service_id: str
    service_name: str
    version: str
    commit_sha: str
    deployed_at: str
    author: str
    status: str
    environment: str
    strategy: Optional[str] = None


class HistoricalIncidentItem(BaseModel):
    id: str
    service_id: str
    service_name: str
    title: str
    severity: str
    status: str
    started_at: str
    resolved_at: Optional[str] = ""
    summary: str
    recovery_actions: List[Dict[str, Any]] = Field(default_factory=list)


class RunbookStepItem(BaseModel):
    id: str
    step_number: int
    action: str
    command: str
    estimated_time_mins: int


class RunbookItem(BaseModel):
    id: str
    service_id: str
    service_name: str
    title: str
    version: str
    url: str
    steps: List[RunbookStepItem] = Field(default_factory=list)


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    protocol: Optional[str] = None
    critical: Optional[bool] = None


class TraversedPath(BaseModel):
    length: int
    node_ids: List[str]
    relationship_types: List[str]


class ServiceDependencyTopology(BaseModel):
    affected_services: List[ServiceNode]
    traversed_services: List[ServiceNode]
    dependency_edges: List[GraphEdge]
    traversed_paths: List[TraversedPath]
    missing_relationships_detected: List[str] = Field(default_factory=list)


class InvestigationContextResponse(BaseModel):
    incident: IncidentBase
    alerts: List[AlertItem]
    metrics: List[MetricObservationItem]
    topology: ServiceDependencyTopology
    deployments: List[DeploymentItem]
    historical_incidents: List[HistoricalIncidentItem]
    runbooks: List[RunbookItem]
    evidence_summary: Dict[str, Any]
