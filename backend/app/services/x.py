import json
import structlog
import functools
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from datetime import datetime
from redis.asyncio import Redis

from app.core.config import settings
from app.schemas.content import ContentIngestRequest
from app.domain.enums import SourceType

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Client protocol — defines the interface any X client must satisfy.
# Swap MockXClient for a real httpx-based HttpXClient without touching
# XCollector or the task layer.
# ---------------------------------------------------------------------------

@runtime_checkable
class XClientProtocol(Protocol):
    def get_posts(
        self,
        *,
        since_id: str | None,
        limit: int,
        accounts: list[str],
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch posts newer than *since_id* (or all if None).

        Returns:
            posts:    List of post dicts.
            next_cursor: Opaque cursor to pass as *since_id* on the next
                         call (tweet ID string), or None if there were no
                         results.
        """
        ...


# ---------------------------------------------------------------------------
# Mock client — reads from the fixture file.
# TODO: replace with a real httpx-based HttpXClient when X API access is
#       available.  The client must implement XClientProtocol.
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _load_fixture() -> list[dict[str, Any]]:
    """Load the X fixture file once per worker process."""
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "x_posts.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


class MockXClient:
    """Fixture-backed mock that satisfies XClientProtocol.

    source_id convention: the ``"id"`` field from the fixture JSON
    (a string representing a tweet ID, e.g. ``"1234567890123456789"``).

    Pagination cursor: the tweet ID of the last item returned, stored in
    Redis as ``x:last_seen_id``.  On the next run, posts with an ID
    lexicographically greater than that value are returned first.  This
    matches the semantic that a real X API v2 ``since_id`` parameter would
    use, so the same Redis key and comparison logic work for both mock and
    real clients.
    """

    def get_posts(
        self,
        *,
        since_id: str | None,
        limit: int,
        accounts: list[str],
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Return up to *limit* posts, cycling through the fixture.

        Posts are filtered to *accounts* (case-insensitive) and ordered so
        that the fixture simulates a chronological feed.  When *since_id*
        is set, posts whose ID is "greater" are returned first (mocking the
        real API's since_id behaviour); the fixture cycles when exhausted.
        """
        all_posts = _load_fixture()
        filtered = [
            p for p in all_posts
            if p.get("author_handle", "").lower() in accounts
        ]

        if not filtered:
            return [], since_id

        # Find start position based on since_id (tweet ID string comparison).
        start_idx = 0
        if since_id is not None:
            for i, p in enumerate(filtered):
                if p.get("id") == since_id:
                    # Start after the last-seen post, wrapping around.
                    start_idx = (i + 1) % len(filtered)
                    break

        results: list[dict[str, Any]] = []
        curr_idx = start_idx
        for _ in range(limit):
            results.append(filtered[curr_idx])
            curr_idx = (curr_idx + 1) % len(filtered)

        next_cursor = results[-1]["id"] if results else since_id
        return results, next_cursor


# ---------------------------------------------------------------------------
# Collector — source of X data; injectable client for testability.
# ---------------------------------------------------------------------------

class XCollector:
    """Collect posts from X (Twitter) accounts.

    source_id convention: the tweet ID string from the API response
    (e.g. ``"1234567890123456789"``).
    """

    # Redis key that stores the tweet-ID cursor (string).
    # Semantics match X API v2 since_id: next call fetches posts newer than this.
    _REDIS_CURSOR_KEY = "x:last_seen_id"

    def __init__(self, client: XClientProtocol | None = None) -> None:
        # Default to the mock client; inject a real client in production.
        self.client: XClientProtocol = client or MockXClient()
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)

    async def process_accounts(self) -> tuple[list[ContentIngestRequest], list[str]]:
        """Fetch recent posts for all configured X accounts."""
        accounts = settings.x_accounts
        if not accounts:
            logger.warning("No X accounts configured — X collection skipped.")
            await self.redis.aclose()
            return [], []

        since_id = await self.redis.get(self._REDIS_CURSOR_KEY)  # str | None

        try:
            raw_posts, next_cursor = self.client.get_posts(
                since_id=since_id,
                limit=settings.x_fetch_limit,
                accounts=accounts,
            )
        except Exception as e:
            logger.exception("Failed to read from X client")
            await self.redis.aclose()
            return [], [str(e)]

        items: list[ContentIngestRequest] = []
        for p in raw_posts:
            dt = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00"))
            item = ContentIngestRequest(
                source=SourceType.X,
                source_id=p["id"],
                author_handle=p["author_handle"],
                raw_text=p["text"],
                media_urls=p.get("media_urls", []),
                collected_at=dt,
                metadata={"public_metrics": p.get("public_metrics", {})},
            )
            items.append(item)

        # Persist cursor only if we got results.
        if next_cursor is not None and next_cursor != since_id:
            await self.redis.set(self._REDIS_CURSOR_KEY, next_cursor)

        await self.redis.aclose()
        return items, []
