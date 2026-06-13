import pytest
from app.services.pdf_report_generator import EvidenceReportGenerator, ReportGenerationError
import hashlib

def test_content_hash_calculation():
    # Verify that the hash calculated is correct
    raw_text = "We have the new RAT available for deployment. Contact me on Tox."
    expected_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    
    # We can test the actual generator if it can run
    assert expected_hash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

def test_pdf_generation_returns_bytes():
    generator = EvidenceReportGenerator()
    mock_data = {
        "case_id": "CASE-2026-0042",
        "report_ref": "REF-883A",
        "generated_timestamp": "2026-06-11 14:00:00 UTC",
        "source": "DarkWeb Forum 'Alpha'",
        "source_status": "Active / Monitored",
        "risk_score": 85,
        "severity": "CRITICAL",
        "threat_category": "Malware Distribution",
        "original_message": "We have the new RAT available for deployment. Contact me on Tox.",
        "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "collected_at": "2026-06-11T13:50:00Z",
        "author_handle": "ZeroCool",
        "source_url": "http://alpha.onion/thread/123",
        "analyst_notes": [
            {
                "author": "Analyst Smith", 
                "timestamp": "2026-06-11T14:15:00Z", 
                "text": "This appears to be a high-priority threat actor distributing a new Remote Access Trojan. Recommend immediate network indicator monitoring."
            }
        ]
    }
    
    pdf_bytes = generator.generate_bytes(mock_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b'%PDF')
    
    # generate() is deprecated but should also work
    pdf_bytes2 = generator.generate(mock_data)
    assert isinstance(pdf_bytes2, bytes)
