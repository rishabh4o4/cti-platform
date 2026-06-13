import math
import logging
from app.schemas.risk import RiskScoringInput, RiskScoringResult, Severity

logger = logging.getLogger(__name__)

class RiskScoringEngine:
    """
    Risk Scoring Engine that calculates a risk score from 0 to 100 based on various metrics.
    Assigns a Severity based on the final score.
    """

    ENGINE_VERSION = "1.1.0"

    _MEMBER_COUNT_LOG_SCALE = 5.0  # log10(100,000)
    _GROWTH_VELOCITY_CAP = 10.0    # Cap at 10x normal growth

    # Define weights for each factor.
    WEIGHTS = {
        "keyword_density": 10.0,
        "graph_centrality": 10.0,
        "member_count": 10.0,
        "growth_velocity": 10.0,
        "cross_link_count": 18.0,
        "ioc_density": 22.0,
        "nlp_threat_confidence": 20.0,
    }

    @classmethod
    def calculate_score(cls, inputs: RiskScoringInput) -> RiskScoringResult:
        """
        Calculates the risk score and severity for given inputs.

        Args:
            inputs (RiskScoringInput): The metrics and inputs.
        
        Returns:
            RiskScoringResult: Contains the 0-100 score, severity, and breakdown of the score.
        """
        try:
            # Get masks, defaulting to 1.0 if not provided
            mask = inputs.confidence_mask or {}
            def get_mask(key: str) -> float:
                val = mask.get(key, 1.0)
                return max(0.0, min(float(val), 1.0))

            # Raw unweighted values normalized to 0.0-1.0
            normalized = {
                "keyword_density": min(inputs.keyword_density, 1.0),
                "graph_centrality": min(inputs.graph_centrality, 1.0),
                "member_count": min(math.log10(inputs.member_count) / cls._MEMBER_COUNT_LOG_SCALE, 1.0) if inputs.member_count > 0 else 0.0,
                "growth_velocity": min(inputs.growth_velocity / cls._GROWTH_VELOCITY_CAP, 1.0) if inputs.growth_velocity > 0 else 0.0,
                "cross_link_count": min(inputs.cross_link_count / 10.0, 1.0),
                "ioc_density": min(inputs.ioc_density, 1.0),
                "nlp_threat_confidence": min(inputs.nlp_threat_confidence, 1.0),
            }

            details = {}
            score_contributions = []
            effective_weights = []
            
            # Count signals present (mask > 0)
            signals_present = 0

            for key, weight in cls.WEIGHTS.items():
                m = get_mask(key)
                if m > 0.0:
                    signals_present += 1
                
                # Exclude weight from denominator if mask == 0.0
                if m > 0.0:
                    effective_weights.append(weight * m)
                
                raw_score = normalized[key] * weight * m
                score_contributions.append(raw_score)
                
                pct = (raw_score / weight) * 100.0 if weight > 0 else 0.0
                details[key] = {
                    "raw": round(raw_score, 2),
                    "max": round(weight, 2),
                    "pct": round(pct, 2)
                }

            # Data confidence classification
            if signals_present == 7:
                data_confidence = "high"
            elif signals_present >= 4:
                data_confidence = "medium"
            else:
                data_confidence = "low"

            sum_effective_weights = math.fsum(effective_weights)
            raw_total = math.fsum(score_contributions)
            
            if sum_effective_weights > 0:
                # Rescale based on observed signals
                total_score = (raw_total / sum_effective_weights) * 100.0
            else:
                total_score = 0.0

            # CRITICAL Corroboration Guard
            # Must have at least two of {ioc_density > 0.1, cross_link_count > 0, graph_centrality > 0.3}
            if total_score >= 75.0:
                corroborations = sum([
                    inputs.ioc_density > 0.1,
                    inputs.cross_link_count > 0,
                    inputs.graph_centrality > 0.3
                ])
                if corroborations < 2:
                    # Cap at HIGH
                    total_score = min(total_score, 74.9)

            # Ensure bounds
            total_score = max(0.0, min(total_score, 100.0))

            # Determine Severity based on uniform bands [0, 25, 50, 75]
            if total_score >= 75.0:
                severity = Severity.CRITICAL
            elif total_score >= 50.0:
                severity = Severity.HIGH
            elif total_score >= 25.0:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW

            # Calculate top factors
            sorted_details = sorted(details.items(), key=lambda x: x[1]["raw"], reverse=True)
            top_factors = [k for k, v in sorted_details[:3] if v["raw"] > 0]

            return RiskScoringResult(
                score=round(total_score, 2),
                severity=severity,
                data_confidence=data_confidence,
                top_factors=top_factors,
                engine_version=cls.ENGINE_VERSION,
                weights_snapshot=dict(cls.WEIGHTS),
                details=details
            )
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            raise
