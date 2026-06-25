import logging
import re
import threading
import time
from typing import TypedDict

from app.core.config import settings

logger = logging.getLogger(__name__)

# --- Constants ---

MAX_TEXT_LENGTH = 10_000  # Max characters for regex extraction
MAX_CLASSIFICATION_LENGTH = 2_000  # Approx. safe limit for DeBERTa-v3 512-token window
CATEGORY_UNCERTAIN = "uncertain"  # Below-threshold confidence (not a model label)
CATEGORY_ERROR = "error"  # Model inference failure (not a model label)

# --- Types ---


class EntitiesDict(TypedDict):
    usernames: list[str]
    urls: list[str]
    domains: list[str]
    emails: list[str]
    phones: list[str]
    ips: list[str]
    crypto_wallets: list[str]
    invite_links: list[str]


class IntelligenceResult(TypedDict):
    entities: EntitiesDict
    category: str
    confidence: float
    pii_risk: bool


# --- Regex Patterns ---

# Telegram usernames: @ followed by 5-32 alphanumeric or underscore characters.
# Negative lookbehind rejects @ preceded by a character valid in email local
# parts, preventing the domain portion of emails from being extracted as a
# username (e.g. ``user@example`` → ``@example`` is suppressed).
USERNAME_PATTERN = re.compile(r"(?<![a-zA-Z0-9._%+-])@[a-zA-Z0-9_]{5,32}")

# Invite links: t.me/ followed by alphanumeric or + or _
INVITE_LINK_PATTERN = re.compile(
    r"(?:https?://)?t\.me/(?:joinchat/)?[a-zA-Z0-9_\+]+"
)

# URLs — closing brackets/parens excluded via lookbehind so
# ``(https://example.com)`` does not capture the trailing ``)``
URL_PATTERN = re.compile(r"https?://[^\s]+(?<=[^.,;:!?\s\)\]\>])")

# Email addresses
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
)

# Phone numbers (international format starting with +, allows common
# separators: spaces, hyphens, dots, parentheses).  Normalized after
# extraction to strip everything except ``+`` and digits.
PHONE_PATTERN = re.compile(r"\+[1-9][\d\s\-\.()]{1,18}\d\b")

# IPv4 addresses
IPV4_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
)

# Crypto Wallets
# BTC Legacy (P2PKH, P2SH): Starts with 1 or 3, 26-35 characters, Base58
BTC_LEGACY_PATTERN = re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b")
# BTC SegWit (Bech32): lowercase only per BIP-173; excludes 1, b, i, o
BTC_BECH32_PATTERN = re.compile(r"\bbc1[ac-hj-np-z02-9]{39,59}\b")
# ETH: Starts with 0x, exactly 40 hex chars after 0x
ETH_PATTERN = re.compile(r"\b0x[a-fA-F0-9]{40}\b")

# Domain extraction — raw pattern; results are filtered post-extraction by
# ``_VALID_TLDS`` and cross-entity deduplication to remove false positives
# like ``v2.0``, ``file.txt``, or domains already part of a URL/email.
_DOMAIN_RAW_PATTERN = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"
)

# Top-level domain allowlist — covers ~95 % of real domains encountered in
# threat intelligence while rejecting common file extensions and version
# strings.  Extend as needed.
_VALID_TLDS = frozenset(
    {
        # Generic TLDs
        "com", "org", "net", "edu", "gov", "mil", "int",
        "io", "co", "me", "info", "biz", "name", "pro",
        # Major country-code TLDs
        "uk", "us", "ca", "au", "de", "fr", "ru", "cn", "in", "jp", "br",
        "nl", "se", "no", "fi", "dk", "es", "it", "pt", "pl", "cz", "at",
        "ch", "kr", "tw", "sg", "hk", "za", "mx", "ar", "cl", "nz", "ie",
        # New gTLDs popular in threat intel
        "xyz", "online", "site", "tech", "store", "app", "dev", "top",
        "club", "live", "world", "today",
        # Dark-web / crypto TLDs
        "onion", "bit", "crypto", "eth", "nft",
        # Frequently abused free-registration ccTLDs
        "tk", "ml", "ga", "cf", "gq", "cc", "su",
    }
)

# Minimum normalized phone length (``+`` + at least 7 digits) to reject
# false positives like ``+1.5`` that technically match the separator pattern.
_MIN_PHONE_LENGTH = 8

# --- Classification Pipeline ---

CATEGORIES = [
    "phishing",
    "fraud",
    "financial fraud",
    "carding",
    "malware distribution",
    "credential theft",
    "self-harm promotion",
    "extremist content",
    "drug trade",
    "weapon trade",
    "safe",
]

MODEL_NAME = "MoritzLaurer/deberta-v3-xsmall-zeroshot-v1.1-all-33"

_classifier_pipeline = None
_classifier_lock = threading.Lock()


def get_classifier():
    """Lazy, thread-safe initialization of the HuggingFace pipeline.

    Uses double-checked locking to avoid redundant model loads when
    multiple threads call this concurrently on first access.
    """
    global _classifier_pipeline

    # Fast path — no lock needed once initialized.
    if _classifier_pipeline is not None:
        return _classifier_pipeline

    with _classifier_lock:
        # Re-check under lock (another thread may have initialized while we waited).
        if _classifier_pipeline is not None:
            return _classifier_pipeline

        start_time = time.time()
        logger.info("Initializing zero-shot classification model: %s", MODEL_NAME)
        try:
            from transformers import pipeline
            import torch

            # Use CPU by default unless configured otherwise.
            device = 0 if torch.cuda.is_available() else -1
            _classifier_pipeline = pipeline(
                "zero-shot-classification",
                model=MODEL_NAME,
                device=device,
            )
            elapsed = time.time() - start_time
            logger.info(
                "Model initialized successfully in %.2f seconds.", elapsed
            )
        except ImportError as e:
            logger.error("Failed to import ML dependencies: %s", e)
            raise

    return _classifier_pipeline


# --- Helpers ---


def _is_valid_domain(domain: str) -> bool:
    """Return True if *domain*'s TLD is in the allowlist."""
    tld = domain.rsplit(".", 1)[-1].lower()
    return tld in _VALID_TLDS


def _normalize_phone(phone: str) -> str:
    """Strip separators, keeping only ``+`` and digits."""
    return "+" + re.sub(r"[^\d]", "", phone[1:])


def _empty_entities() -> EntitiesDict:
    """Return an ``EntitiesDict`` with all fields set to empty lists."""
    return {
        "usernames": [],
        "urls": [],
        "domains": [],
        "emails": [],
        "phones": [],
        "ips": [],
        "crypto_wallets": [],
        "invite_links": [],
    }


# --- Entity Extraction ---


def extract_entities(text: str) -> EntitiesDict:
    """Extract indicators from *text* with dedup and cross-entity cleanup.

    Processing order matters — invite links and emails are extracted first so
    that their substrings (domains, usernames) can be suppressed from later
    entity types.
    """
    # Enforce input length limit to bound regex execution time.
    if len(text) > MAX_TEXT_LENGTH:
        logger.warning(
            "Text truncated for entity extraction (original=%d, limit=%d)",
            len(text),
            MAX_TEXT_LENGTH,
        )
        text = text[:MAX_TEXT_LENGTH]

    def _dedup(items: list[str]) -> list[str]:
        return list(dict.fromkeys(items))

    # --- Extract in dependency order ---

    invite_links = _dedup(INVITE_LINK_PATTERN.findall(text))
    emails = _dedup(EMAIL_PATTERN.findall(text))
    urls_raw = _dedup(URL_PATTERN.findall(text))

    # Cross-entity dedup: remove URLs that are also invite links.
    invite_link_set = set(invite_links)
    urls = [u for u in urls_raw if u not in invite_link_set]

    # Usernames: suppress matches that look like email domain parts.
    raw_usernames = USERNAME_PATTERN.findall(text)
    email_domain_handles = {"@" + e.split("@")[1] for e in emails}
    usernames = _dedup(
        [u for u in raw_usernames if u not in email_domain_handles]
    )

    # Domains: keep only those with a recognized TLD, then remove any domain
    # that already appears inside an extracted URL, invite link, or email.
    raw_domains = _DOMAIN_RAW_PATTERN.findall(text)
    url_email_corpus = " ".join(urls + invite_links + emails)
    domains = _dedup(
        [
            d
            for d in raw_domains
            if _is_valid_domain(d) and d not in url_email_corpus
        ]
    )

    # Phones: normalize, then filter by minimum digit count.
    raw_phones = PHONE_PATTERN.findall(text)
    normalized_phones = [_normalize_phone(p) for p in raw_phones]
    phones = _dedup(
        [p for p in normalized_phones if len(p) >= _MIN_PHONE_LENGTH]
    )

    ips = _dedup(IPV4_PATTERN.findall(text))

    btc_legacy = BTC_LEGACY_PATTERN.findall(text)
    btc_bech32 = BTC_BECH32_PATTERN.findall(text)
    eth = ETH_PATTERN.findall(text)
    crypto_wallets = _dedup(btc_legacy + btc_bech32 + eth)

    return {
        "usernames": usernames,
        "urls": urls,
        "domains": domains,
        "emails": emails,
        "phones": phones,
        "ips": ips,
        "crypto_wallets": crypto_wallets,
        "invite_links": invite_links,
    }


# --- Full Analysis ---


def analyze_text(text: str) -> IntelligenceResult:
    """Extract entities and classify *text* into a threat category.

    Returns a degraded result (``category="error"``) if the model fails,
    preserving whatever entities were already extracted.
    """
    # Early exit for empty / whitespace-only input (Issue 4: before entity
    # extraction to avoid wasted regex work).
    if not text or not text.strip():
        return IntelligenceResult(
            entities=_empty_entities(),
            category="safe",
            confidence=1.0,
            pii_risk=False,
        )

    entities = extract_entities(text)

    # PII risk flag (Issue 13): flag presence of PII-bearing indicators;
    # let the dashboard layer decide display / redaction policy.
    has_pii = bool(
        entities["emails"] or entities["phones"] or entities["crypto_wallets"]
    )

    try:
        classifier = get_classifier()

        # Truncate for model input — DeBERTa-v3 tokenizer truncates at 512
        # tokens silently; capping chars keeps behaviour predictable.
        classification_text = text
        if len(text) > MAX_CLASSIFICATION_LENGTH:
            logger.info(
                "Text truncated for classification (original=%d, limit=%d)",
                len(text),
                MAX_CLASSIFICATION_LENGTH,
            )
            classification_text = text[:MAX_CLASSIFICATION_LENGTH]

        result = classifier(classification_text, CATEGORIES, multi_label=False)

        top_label = result["labels"][0]
        top_score = result["scores"][0]

        threshold = settings.intelligence_confidence_threshold

        if top_score < threshold:
            category = CATEGORY_UNCERTAIN
        else:
            category = top_label

    except Exception:
        logger.exception("Model inference failed; returning degraded result.")
        category = CATEGORY_ERROR
        top_score = 0.0

    return IntelligenceResult(
        entities=entities,
        category=category,
        confidence=top_score,
        pii_risk=has_pii,
    )
