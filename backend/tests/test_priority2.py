import pytest
from app.services.pdf_report_generator import EvidenceReportGenerator

def test_priority2_pdf_generation():
    generator = EvidenceReportGenerator()
    mock_data = {
        "case_id": "CASE-2026-0042",
        "report_ref": "REF-883A",
        "generated_timestamp": "2026-06-11 14:00:00 UTC",
        "source": "DarkWeb Forum 'Alpha'",
        "source_status": "Active / Monitored",
        "source_reliability_rating": "B / 3",
        "model_version": "v2.1",
        "data_confidence": "0.92",
        "risk_score": 85,
        "severity": "CRITICAL",
        "threat_category": "Malware Distribution",
        "original_message": "We have the new RAT available for deployment.",
        "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "collected_at": "2026-06-11T13:50:00Z",
        "author_handle": "ZeroCool",
        "source_url": "http://alpha.onion/thread/123",
        "tactics": ["Initial Access", "Execution"],
        "techniques": ["Phishing", "Command and Scripting Interpreter"],
        "extracted_entities": [
            {"type": "MalwareType", "value": "RAT", "confidence": 0.95}
        ],
        "related_channels": ["Telegram Group: @MalwareOps"],
        "recommended_actions": ["Isolate affected hosts", "Block indicator IOCs"],
        "media_urls": ["http://alpha.onion/screenshot.png"],
        "timeline": [
            {"timestamp": "2026-06-10 12:00:00 UTC", "description": "Initial detection."}
        ],
        "analyst_notes": [
            {
                "author": "Analyst Smith", 
                "timestamp": "2026-06-11T14:15:00Z", 
                "text": "High priority threat."
            }
        ]
    }
    
    # Also test saving to file to easily verify layout visually
    generator.save_to_file(mock_data, "test_priority2_report.pdf")
    pdf_bytes = generator.generate_bytes(mock_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b'%PDF')
