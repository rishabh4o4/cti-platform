import uuid
import structlog
import asyncio
from datetime import timezone
from typing import Any
from io import BytesIO

from minio import Minio
from redis.asyncio import Redis
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

from app.core.config import settings
from app.schemas.content import ContentIngestRequest
from app.domain.enums import SourceType

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Module-level singletons — created once per worker process, never per task.
# This avoids opening a fresh TCP connection to MinIO and Redis on every run.
# ---------------------------------------------------------------------------
_minio_client: Minio | None = None
_redis_client: Redis | None = None


def _get_minio() -> Minio:
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
        try:
            if not _minio_client.bucket_exists(settings.minio_bucket):
                _minio_client.make_bucket(settings.minio_bucket)
        except Exception as e:
            logger.error("Failed to initialise MinIO bucket", error=str(e))
    return _minio_client


def _get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


class TelegramCollector:
    """Collect messages from configured Telegram channels.

    source_id convention: ``"<channel_entity_id>_<message_id>"``
    (e.g. ``"-1001234567890_42"``).  The channel entity ID is the stable
    integer ID returned by Telethon, not the human-readable @username.
    """

    def __init__(self) -> None:
        self.client = None
        if not all([settings.telegram_api_id, settings.telegram_api_hash, settings.telegram_session_string]) or settings.telegram_session_string == "dummy":
            logger.warning("Telegram credentials not fully configured. Collection may fail.")
        else:
            self.client = TelegramClient(
                StringSession(settings.telegram_session_string),
                settings.telegram_api_id,
                settings.telegram_api_hash,
            )

        self.minio_client = _get_minio()
        self.redis = _get_redis()

    @property
    def is_mock(self) -> bool:
        return self.client is None

    async def upload_to_minio(self, file_bytes: bytes, file_name: str) -> str | None:
        try:
            file_size = len(file_bytes)
            if file_size > 20 * 1024 * 1024:
                logger.warning("Media file too large, skipping", file_name=file_name, size=file_size)
                return None

            object_name = f"telegram/{uuid.uuid4()}_{file_name}"
            # minio put_object is blocking; run in a thread to avoid blocking the event loop.
            await asyncio.to_thread(
                self.minio_client.put_object,
                settings.minio_bucket,
                object_name,
                BytesIO(file_bytes),
                file_size,
            )

            return f"s3://{settings.minio_bucket}/{object_name}"
        except Exception as e:
            logger.exception("Failed to upload media to MinIO", file_name=file_name)
            return None

    async def _download_and_upload_media(self, message: Any) -> str | None:
        try:
            # Telethon's download_media can return bytes if file is BytesIO
            bio = BytesIO()
            await self.client.download_media(message, file=bio)
            file_bytes = bio.getvalue()
            if not file_bytes:
                return None

            # guess extension or name
            file_name = "media_file"
            if getattr(message.media, "document", None) and getattr(message.media.document, "attributes", None):
                for attr in message.media.document.attributes:
                    if hasattr(attr, "file_name"):
                        file_name = attr.file_name
                        break

            return await self.upload_to_minio(file_bytes, file_name)
        except Exception as e:
            logger.warning("Failed to download media via Telethon", error=str(e))
            return None

    async def process_channels(self) -> tuple[list[ContentIngestRequest], list[str]]:
        if not self.client:
            import json
            from pathlib import Path
            from datetime import datetime, timezone
            fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "telegram_posts.json"
            if fixture_path.exists():
                with open(fixture_path, "r", encoding="utf-8") as f:
                    posts = json.load(f)
                items = []
                for p in posts:
                    items.append(ContentIngestRequest(
                        source=SourceType.TELEGRAM,
                        source_id=p["id"],
                        author_handle=p["author_handle"],
                        raw_text=p["text"],
                        media_urls=p.get("media_urls", []),
                        collected_at=datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")),
                        metadata={"channel": p.get("channel", "test")}
                    ))
                return items, []

            mock_item = ContentIngestRequest(
                source=SourceType.TELEGRAM,
                source_id="mock_telegram_1",
                author_handle="mock_channel",
                raw_text="This is a mock telegram message",
                media_urls=[],
                collected_at=datetime.now(timezone.utc),
                metadata={"channel": "test"}
            )
            return [mock_item], []

        if not settings.telegram_channels:
            logger.warning("No Telegram channels configured — Telegram collection skipped.")
            return [], []

        all_items = []
        errors = []

        await self.client.connect()
        try:
            if not await self.client.is_user_authorized():
                # disconnect() is safe to call even if we returned early — Telethon
                # is a no-op when the client is not in a fully connected state.
                return [], ["Telegram session is not authorized"]

            for channel_username in settings.telegram_channels:
                try:
                    redis_key = f"telegram:last_seen:{channel_username}"
                    last_seen_str = await self.redis.get(redis_key)
                    min_id = int(last_seen_str) if last_seen_str else 0

                    channel_entity = await self.client.get_entity(channel_username)

                    max_id_seen = min_id

                    async for message in self.client.iter_messages(channel_entity, limit=settings.telegram_fetch_limit, min_id=min_id):
                        if message.id > max_id_seen:
                            max_id_seen = message.id

                        # Sender name fallback
                        author_name = channel_username
                        if message.sender:
                            author_name = getattr(message.sender, "username", None) or getattr(message.sender, "title", None) or channel_username

                        raw_text = message.text or ""

                        media_urls = []
                        if message.media:
                            minio_url = await self._download_and_upload_media(message)
                            if minio_url:
                                media_urls.append(minio_url)

                        # Date is already UTC-aware from Telethon
                        collected_at = message.date

                        item = ContentIngestRequest(
                            source=SourceType.TELEGRAM,
                            # source_id: "<channel_entity_id>_<message_id>"
                            source_id=f"{channel_entity.id}_{message.id}",
                            author_handle=author_name,
                            raw_text=raw_text,
                            media_urls=media_urls,
                            collected_at=collected_at,
                            metadata={"channel": channel_username, "message_id": message.id},
                        )
                        all_items.append(item)

                    if max_id_seen > min_id:
                        await self.redis.set(redis_key, str(max_id_seen))

                except FloodWaitError as e:
                    logger.warning("FloodWaitError on Telegram", wait_seconds=e.seconds)
                    errors.append(f"FloodWaitError: waiting {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.exception("Error processing telegram channel", channel=channel_username)
                    errors.append(f"Error on {channel_username}: {str(e)}")

                await asyncio.sleep(1)  # Throttle between channels

        finally:
            # disconnect() is a no-op if the client was never fully connected,
            # so this is safe even when process_channels returned early above.
            await self.client.disconnect()

        return all_items, errors
