import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.telegram import TelegramCollector
from app.tasks.telegram import _collect_telegram_data
from app.schemas.content import ContentIngestRequest
from app.domain.enums import SourceType

@pytest.fixture
def mock_telethon():
    with patch("app.services.telegram.TelegramClient") as mock_client_cls, \
         patch("app.services.telegram.StringSession") as mock_session_cls:
        client_instance = AsyncMock()
        mock_client_cls.return_value = client_instance
        mock_session_cls.return_value = MagicMock()
        
        client_instance.is_user_authorized.return_value = True
        
        mock_channel = MagicMock()
        mock_channel.id = 12345
        client_instance.get_entity.return_value = mock_channel
        
        mock_message1 = MagicMock()
        mock_message1.id = 1
        mock_message1.sender.username = "test_user"
        mock_message1.text = "Hello from Telegram!"
        mock_message1.date = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
        mock_message1.media = None
        
        mock_message2 = MagicMock()
        mock_message2.id = 2
        mock_message2.sender = None
        mock_message2.text = "Message with media"
        mock_message2.date = datetime(2023, 1, 1, 12, 5, tzinfo=timezone.utc)
        mock_message2.media = MagicMock()
        
        async def mock_iter_messages(*args, **kwargs):
            yield mock_message1
            yield mock_message2
            
        client_instance.iter_messages = mock_iter_messages
        
        async def mock_download_media(message, file):
            file.write(b"fake_media_bytes")
            return file
        client_instance.download_media = mock_download_media
        
        yield mock_client_cls

@pytest.fixture
def mock_minio():
    with patch("app.services.telegram.Minio") as mock_minio_cls:
        minio_instance = MagicMock()
        mock_minio_cls.return_value = minio_instance
        minio_instance.bucket_exists.return_value = True
        yield mock_minio_cls

@pytest.fixture
def mock_redis():
    import app.services.telegram
    app.services.telegram._redis_client = None
    with patch("app.services.telegram.Redis.from_url") as mock_redis_cls:
        redis_instance = AsyncMock()
        mock_redis_cls.return_value = redis_instance
        redis_instance.get.return_value = None
        yield redis_instance
    app.services.telegram._redis_client = None

@pytest.mark.asyncio
async def test_telegram_collector_parsing(mock_telethon, mock_minio, mock_redis):
    from app.core.config import settings
    settings.telegram_channels = ["test_channel"]
    settings.telegram_api_id = 123
    settings.telegram_api_hash = "hash"
    settings.telegram_session_string = "dummy_session"
    
    collector = TelegramCollector()
    items, errors = await collector.process_channels()
    
    assert not errors
    assert len(items) == 2
    
    msg1 = items[0]
    assert isinstance(msg1, ContentIngestRequest)
    assert msg1.source == SourceType.TELEGRAM
    assert msg1.source_id == "12345_1"
    assert msg1.author_handle == "test_user"
    assert msg1.raw_text == "Hello from Telegram!"
    assert msg1.collected_at == datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert not msg1.media_urls
    
    msg2 = items[1]
    assert msg2.source_id == "12345_2"
    assert msg2.author_handle == "test_channel"
    assert msg2.raw_text == "Message with media"
    assert len(msg2.media_urls) == 1
    assert msg2.media_urls[0].startswith("s3://")

@pytest.mark.asyncio
async def test_collect_telegram_data_task(mock_telethon, mock_minio, mock_redis):
    with patch("app.tasks.telegram.group") as mock_group:
        from app.core.config import settings
        settings.telegram_channels = ["test_channel"]
        settings.telegram_api_id = 123
        settings.telegram_api_hash = "hash"
        settings.telegram_session_string = "dummy_session"
        
        result = await _collect_telegram_data()
        
        assert result["status"] == "completed"
        assert result["items_fetched"] == 2
        assert not result["errors"]
        assert mock_group.call_count == 1
        
        mock_redis.set.assert_called_with("telegram:last_seen:test_channel", "2")
