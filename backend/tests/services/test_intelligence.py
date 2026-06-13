import uuid

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.intelligence import (
    extract_entities,
    analyze_text,
    CATEGORY_UNCERTAIN,
    CATEGORY_ERROR,
    MODEL_NAME,
)


# ======================================================================
# Existing entity-extraction tests (updated for new behaviour)
# ======================================================================


def test_extract_usernames():
    text = "Contact me at @valid_user123 for info. Don't contact @sh"
    entities = extract_entities(text)
    assert entities["usernames"] == ["@valid_user123"]


def test_extract_invite_links():
    text = "Join our group t.me/joinchat/ABCDEFGH12345 or https://t.me/some_channel_name"
    entities = extract_entities(text)
    assert "t.me/joinchat/ABCDEFGH12345" in entities["invite_links"]
    assert "https://t.me/some_channel_name" in entities["invite_links"]


def test_extract_urls():
    text = "Check out https://google.com and http://example.org/path?q=1."
    entities = extract_entities(text)
    assert "https://google.com" in entities["urls"]
    assert "http://example.org/path?q=1" in entities["urls"]


def test_extract_domains():
    text = "The domain is example.com and also test.org.uk."
    entities = extract_entities(text)
    assert "example.com" in entities["domains"]
    assert "test.org.uk" in entities["domains"]


def test_extract_emails():
    text = "Email us at support@example.com or sales.test@company.co.uk."
    entities = extract_entities(text)
    assert "support@example.com" in entities["emails"]
    assert "sales.test@company.co.uk" in entities["emails"]


def test_extract_phones():
    text = "Call us at +1234567890 or +447911123456 for details."
    entities = extract_entities(text)
    assert "+1234567890" in entities["phones"]
    assert "+447911123456" in entities["phones"]


def test_extract_ips():
    text = "Server IP is 192.168.1.1 and public is 8.8.8.8."
    entities = extract_entities(text)
    assert "192.168.1.1" in entities["ips"]
    assert "8.8.8.8" in entities["ips"]


def test_extract_crypto_wallets():
    text = (
        "Send BTC to 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa or 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy. "
        "Also bech32: bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq. "
        "Send ETH to 0x71C7656EC7ab88b098defB751B7401B5f6d8976F."
    )
    entities = extract_entities(text)
    assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in entities["crypto_wallets"]
    assert "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy" in entities["crypto_wallets"]
    assert "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq" in entities["crypto_wallets"]
    assert "0x71C7656EC7ab88b098defB751B7401B5f6d8976F" in entities["crypto_wallets"]


def test_deduplication():
    text = "URL is https://example.com. Again, https://example.com."
    entities = extract_entities(text)
    assert entities["urls"] == ["https://example.com"]


@patch("app.services.intelligence.get_classifier")
def test_analyze_text_high_confidence(mock_get_classifier):
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = {
        "labels": ["fraud", "safe"],
        "scores": [0.95, 0.05],
    }
    mock_get_classifier.return_value = mock_pipeline

    text = "Send me 1 BTC to 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa immediately! @scammer"
    result = analyze_text(text)

    assert result["category"] == "fraud"
    assert result["confidence"] == 0.95
    assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in result["entities"]["crypto_wallets"]
    assert "@scammer" in result["entities"]["usernames"]


@patch("app.services.intelligence.get_classifier")
def test_analyze_text_low_confidence(mock_get_classifier):
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = {
        "labels": ["malware distribution", "safe"],
        "scores": [0.45, 0.40],  # Below 0.5 threshold
    }
    mock_get_classifier.return_value = mock_pipeline

    text = "Is this file safe?"
    result = analyze_text(text)

    assert result["category"] == CATEGORY_UNCERTAIN
    assert result["confidence"] == 0.45


# ======================================================================
# New tests — one per fixed issue
# ======================================================================


# Issue 1: Usernames must NOT be extracted from email addresses
def test_username_not_extracted_from_email():
    text = "Contact support@example.com for help, or DM @admin_panel"
    entities = extract_entities(text)
    # "@example" should NOT appear as a username
    assert all("@example" not in u for u in entities["usernames"])
    # Real username should still be extracted
    assert "@admin_panel" in entities["usernames"]
    # Email should be correctly extracted
    assert "support@example.com" in entities["emails"]


# Issue 2: Domain TLD filtering rejects false positives
def test_domain_tld_filtering():
    text = "Running version v2.0 on torch.cuda with file.txt loaded"
    entities = extract_entities(text)
    # None of these should appear as domains
    assert "v2.0" not in entities["domains"]
    assert "torch.cuda" not in entities["domains"]
    assert "file.txt" not in entities["domains"]


def test_domain_valid_tld_accepted():
    text = "Visit malware-c2.xyz and phishing-site.onion for indicators"
    entities = extract_entities(text)
    assert "malware-c2.xyz" in entities["domains"]
    assert "phishing-site.onion" in entities["domains"]


# Issue 3: Cross-entity deduplication
def test_invite_link_not_duplicated_in_urls():
    text = "Join https://t.me/some_channel_name for updates"
    entities = extract_entities(text)
    assert "https://t.me/some_channel_name" in entities["invite_links"]
    # The same link must NOT also appear in urls
    assert "https://t.me/some_channel_name" not in entities["urls"]


def test_domain_not_duplicated_from_url():
    text = "Visit https://evil.com/phish and report"
    entities = extract_entities(text)
    assert "https://evil.com/phish" in entities["urls"]
    # "evil.com" is part of the URL so it should be suppressed from domains
    assert "evil.com" not in entities["domains"]


# Issue 4: Empty / whitespace text returns early
def test_empty_text_returns_safe():
    result = analyze_text("")
    assert result["category"] == "safe"
    assert result["confidence"] == 1.0
    assert result["pii_risk"] is False
    assert result["entities"]["usernames"] == []


def test_whitespace_only_text_returns_safe():
    result = analyze_text("   \n\t  ")
    assert result["category"] == "safe"
    assert result["confidence"] == 1.0
    assert result["pii_risk"] is False


# Issue 5: Bech32 addresses must be lowercase only
def test_bech32_rejects_uppercase():
    # Uppercase Bech32 is invalid per BIP-173
    text = "BC1QAR0SRRR7XFKVY5L643LYDNW9RE59GTZZWF5MDQ"
    entities = extract_entities(text)
    assert entities["crypto_wallets"] == []


def test_bech32_accepts_valid_lowercase():
    text = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
    entities = extract_entities(text)
    assert "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq" in entities["crypto_wallets"]


# Issue 9: Phone numbers with separators
def test_phone_with_spaces():
    text = "Call +1 234 567 8900 now"
    entities = extract_entities(text)
    assert "+12345678900" in entities["phones"]


def test_phone_with_dashes():
    text = "Fax at +44-7911-123456"
    entities = extract_entities(text)
    assert "+447911123456" in entities["phones"]


def test_phone_rejects_short_false_positives():
    # "+1.5" has only 2 digits after normalization — too short for a phone
    text = "version +1.5 released"
    entities = extract_entities(text)
    assert entities["phones"] == []


# Issue 10: URLs with surrounding parentheses
def test_url_does_not_capture_closing_paren():
    text = "See (https://example.com) for details"
    entities = extract_entities(text)
    # The closing ')' must NOT be part of the URL
    assert "https://example.com" in entities["urls"]


def test_url_does_not_capture_closing_bracket():
    text = "Link: [https://example.org/path]"
    entities = extract_entities(text)
    assert "https://example.org/path" in entities["urls"]


# Issue 12: Category constants
def test_category_constants_are_strings():
    assert CATEGORY_UNCERTAIN == "uncertain"
    assert CATEGORY_ERROR == "error"
    # These are NOT model labels and must NOT be in CATEGORIES
    from app.services.intelligence import CATEGORIES

    assert CATEGORY_UNCERTAIN not in CATEGORIES
    assert CATEGORY_ERROR not in CATEGORIES


# Issue 13: pii_risk flag
@patch("app.services.intelligence.get_classifier")
def test_pii_risk_true_when_pii_present(mock_get_classifier):
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = {
        "labels": ["safe", "fraud"],
        "scores": [0.90, 0.10],
    }
    mock_get_classifier.return_value = mock_pipeline

    text = "Please email me at user@example.com and call +1234567890"
    result = analyze_text(text)
    assert result["pii_risk"] is True


@patch("app.services.intelligence.get_classifier")
def test_pii_risk_false_when_no_pii(mock_get_classifier):
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = {
        "labels": ["safe", "fraud"],
        "scores": [0.90, 0.10],
    }
    mock_get_classifier.return_value = mock_pipeline

    text = "This is a normal message with no personal data"
    result = analyze_text(text)
    assert result["pii_risk"] is False


# Issue 14: Model error handling
@patch("app.services.intelligence.get_classifier")
def test_analyze_text_model_error_returns_degraded(mock_get_classifier):
    mock_pipeline = MagicMock()
    mock_pipeline.side_effect = RuntimeError("CUDA out of memory")
    mock_get_classifier.return_value = mock_pipeline

    result = analyze_text("some threatening text about fraud")

    assert result["category"] == CATEGORY_ERROR
    assert result["confidence"] == 0.0
    # Entities should still be extracted even when classification fails
    assert isinstance(result["entities"], dict)
    assert "pii_risk" in result


# ======================================================================
# Integration test — NLP Celery task calls analyze_text
# ======================================================================


@pytest.mark.asyncio
@patch("app.services.intelligence.analyze_text")
async def test_nlp_task_calls_analyze_text(mock_analyze_text):
    """The NLP Celery task must fetch raw_text and invoke analyze_text."""
    expected_text = "Send BTC to 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa @scammer"
    content_id = str(uuid.uuid4())

    mock_analyze_text.return_value = {
        "entities": {
            "usernames": ["@scammer"],
            "urls": [],
            "domains": [],
            "emails": [],
            "phones": [],
            "ips": [],
            "crypto_wallets": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
            "invite_links": [],
        },
        "category": "fraud",
        "confidence": 0.92,
        "pii_risk": True,
    }

    # Mock the async DB session to return the expected raw_text
    mock_scalar_result = MagicMock()
    mock_scalar_result.scalar_one_or_none.return_value = expected_text

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_scalar_result

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_db

    with patch("app.db.session.async_session_maker", return_value=mock_session_ctx):
        from app.tasks.nlp import _run_nlp_analysis

        result = await _run_nlp_analysis(content_id)

    # Core assertion: analyze_text was called with the exact raw_text
    mock_analyze_text.assert_called_once_with(expected_text)

    # Verify the result structure matches the nlp_flags JSONB schema
    assert result["stage"] == "nlp"
    assert result["content_id"] == content_id
    assert result["model_version"] == MODEL_NAME
    assert result["flags"]["status"] == "completed"
    assert result["flags"]["category"] == "fraud"
    assert result["flags"]["confidence"] == 0.92
    assert result["flags"]["pii_risk"] is True
    assert "entities" in result["flags"]
