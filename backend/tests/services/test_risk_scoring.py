import pytest
from app.schemas.risk import RiskScoringInput, Severity
from app.services.risk_scoring import RiskScoringEngine

def test_risk_scoring_engine_low_risk():
    inputs = RiskScoringInput(
        keyword_density=0.0,
        graph_centrality=0.0,
        member_count=0,
        growth_velocity=0.0,
        cross_link_count=0,
        ioc_density=0.0,
        nlp_threat_confidence=0.0,
        confidence_mask={"keyword_density": 1.0, "graph_centrality": 1.0, "member_count": 1.0, "growth_velocity": 1.0, "cross_link_count": 1.0, "ioc_density": 1.0, "nlp_threat_confidence": 1.0}
    )
    result = RiskScoringEngine.calculate_score(inputs)
    assert result.score == 0.0
    assert result.severity == Severity.LOW
    assert result.data_confidence == "high"

def test_critical_corroboration_guard_capped():
    # Only NLP is high, structurally very weak
    inputs = RiskScoringInput(
        keyword_density=1.0, # 10
        graph_centrality=0.0, # 0
        member_count=100000, # 10
        growth_velocity=10.0, # 10
        cross_link_count=0, # 0
        ioc_density=0.0, # 0
        nlp_threat_confidence=1.0, # 20
        # total raw = 50. Wait, need higher score to test cap.
        # Let's bump ioc_density just a bit but not over 0.1
    )
    # Actually, to get raw_score >= 75 without >1 structural:
    # We can have keyword_density=1.0 (10), member_count=100k (10), growth_velocity=10.0 (10), nlp=1.0 (20) = 50.
    # We need 25 more points. We only have structural left: cross_link(18), ioc(22), graph(10).
    # Wait, the cap is 75. If only NLP and non-structural are maxed, the sum is 10 + 10 + 10 + 20 = 50.
    # To reach 75 we *must* have structural signals!
    # Let's say we have ioc_density = 1.0 (22 points) -> Total = 72. Still not 75.
    # We add graph_centrality = 0.3 (3 points) -> Total = 75.
    # Are there 2 structural? ioc > 0.1 (YES), graph > 0.3 (NO, it's exactly 0.3).
    # So 1 structural signal. Score is 75. Should be capped at 74.9.
    
    inputs = RiskScoringInput(
        keyword_density=1.0,
        graph_centrality=0.3,
        member_count=100000,
        growth_velocity=10.0,
        cross_link_count=0,
        ioc_density=1.0,
        nlp_threat_confidence=1.0,
    )
    result = RiskScoringEngine.calculate_score(inputs)
    # Raw sum: KD(10) + GC(3) + MC(10) + GV(10) + CL(0) + IOC(22) + NLP(20) = 75
    # Since corroborations = 1 (only ioc_density > 0.1), it should cap at 74.9 (HIGH)
    assert result.score == 74.9
    assert result.severity == Severity.HIGH

def test_critical_corroboration_guard_passed():
    inputs = RiskScoringInput(
        keyword_density=1.0,
        graph_centrality=0.4,
        member_count=100000,
        growth_velocity=10.0,
        cross_link_count=0,
        ioc_density=1.0,
        nlp_threat_confidence=1.0,
    )
    result = RiskScoringEngine.calculate_score(inputs)
    # Raw sum: KD(10) + GC(4) + MC(10) + GV(10) + CL(0) + IOC(22) + NLP(20) = 76
    # Corroborations = 2 (ioc_density > 0.1, graph_centrality > 0.3)
    assert result.score == 76.0
    assert result.severity == Severity.CRITICAL

def test_sparse_data_confidence_and_rescaling():
    # Only 3 signals present
    inputs = RiskScoringInput(
        keyword_density=1.0, # 10
        graph_centrality=0.0, 
        member_count=0, 
        growth_velocity=0.0, 
        cross_link_count=0, 
        ioc_density=1.0, # 22
        nlp_threat_confidence=1.0, # 20
        confidence_mask={"keyword_density": 1.0, "ioc_density": 1.0, "nlp_threat_confidence": 1.0, "graph_centrality": 0.0, "member_count": 0.0, "growth_velocity": 0.0, "cross_link_count": 0.0}
    )
    result = RiskScoringEngine.calculate_score(inputs)
    # Present weights: 10 + 22 + 20 = 52.
    # Raw score: 10 + 22 + 20 = 52.
    # Rescaled: (52 / 52) * 100 = 100.
    # Wait, 100 >= 75. Corroborations? ioc_density > 0.1 (Yes, 1). 
    # Are there any others? No.
    # So capped at 74.9
    assert result.score == 74.9
    assert result.data_confidence == "low"
    assert result.severity == Severity.HIGH

def test_medium_risk_uniform_bands():
    # 25 to 50 is medium
    inputs = RiskScoringInput(
        keyword_density=0.5, # 5
        graph_centrality=0.0, 
        member_count=1000, # log10(1000)=3. 3/5 * 10 = 6
        growth_velocity=2.0, # 2/10 * 10 = 2
        cross_link_count=1, # 1/10 * 18 = 1.8
        ioc_density=0.0, 
        nlp_threat_confidence=0.8, # 0.8 * 20 = 16
    )
    result = RiskScoringEngine.calculate_score(inputs)
    # Total: 5 + 6 + 2 + 1.8 + 16 = 30.8
    # Uniform band [25, 50) is MEDIUM
    assert result.score == 30.8
    assert result.severity == Severity.MEDIUM
    assert result.data_confidence == "high" # default mask is all 1.0
