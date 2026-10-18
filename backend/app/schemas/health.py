from pydantic import BaseModel, Field
from typing import Optional, Any


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall service status (healthy/degraded)")
    service: str = Field(default="traceforge-backend", description="Service name")
    environment: str = Field(..., description="Current running environment")


class DatabaseHealthDetail(BaseModel):
    connected: bool
    host: Optional[str] = None
    port: Optional[int] = None
    graph: Optional[str] = None
    query_response: Optional[str] = None
    error: Optional[str] = None


class DatabaseHealthResponse(BaseModel):
    status: str = Field(..., description="Database status (healthy/unhealthy)")
    details: DatabaseHealthDetail
