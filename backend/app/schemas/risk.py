from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class RiskScoringInput(BaseModel):
    keyword_density: float = Field(..., ge=0.0, description="Density of suspicious keywords (expected range: 0.0 to 1.0; cap: 1.0)")
    graph_centrality: float = Field(..., ge=0.0, description="Centrality score in the network graph (expected range: 0.0 to 1.0; cap: 1.0)")
    member_count: int = Field(..., ge=0, description="Number of members in the group/channel (uses log10 scaling capped at 100,000)")
    growth_velocity: float = Field(..., ge=0.0, description="Rate of new members joining relative to historical average (e.g., 1.0 = normal, >1.0 = anomalous surge)")
    cross_link_count: int = Field(..., ge=0, description="Number of links to other known suspicious groups (cap: 10)")
    ioc_density: float = Field(..., ge=0.0, description="Density of Indicators of Compromise (expected range: 0.0 to 1.0; cap: 1.0)")
    nlp_threat_confidence: float = Field(..., ge=0.0, le=1.0, description="NLP model confidence score for threat presence")
    confidence_mask: dict[str, float] = Field(default_factory=dict, description="Per-signal confidence mask (0.0=absent, 1.0=fully observed)")

class RiskScoringResult(BaseModel):
    score: float = Field(..., ge=0.0, le=100.0, description="Overall risk score from 0 to 100")
    severity: Severity = Field(..., description="Risk severity category")
    data_confidence: str = Field(..., description="Confidence in the data ('high', 'medium', 'low') based on number of observed signals")
    top_factors: list[str] = Field(default_factory=list, description="Top 3 contributing factors to the score")
    engine_version: str = Field(..., description="Version of the scoring engine used")
    weights_snapshot: dict[str, float] = Field(..., description="Snapshot of the weights used for scoring")
    details: dict[str, dict[str, float]] = Field(default_factory=dict, description="Detailed breakdown showing {raw, max, pct} for each signal")
