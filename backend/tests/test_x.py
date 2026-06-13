import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.x import XCollector
from app.domain.enums import SourceType
from app.tasks.x import _collect_x_data

@pytest.fixture
def mock_redis():
    with patch("app.services.x.Redis") as mock_redis_cls:
        redis_instance = AsyncMock()
        mock_redis_cls.from_url.return_value = redis_instance
        yield redis_instance

@pytest.mark.asyncio
async def test_x_collector_parsing(mock_redis):
    from app.core.config import settings
    # Accounts must be present in the fixture
    settings.x_accounts = ["elonmusk"]
    settings.x_fetch_limit = 2
    
    mock_redis.get.return_value = "0"
    
    collector = XCollector()
    items, errors = await collector.process_accounts()
    
    assert not errors
    assert len(items) == 2
    for item in items:
        assert item.source == SourceType.X
        assert item.author_handle == "elonmusk"
        assert isinstance(item.metadata, dict)
        assert "public_metrics" in item.metadata
    
    # Assert redis set was called
    mock_redis.set.assert_called()

@pytest.mark.asyncio
async def test_x_collector_cyclic_loading(mock_redis):
    from app.core.config import settings
    # Account has 2 posts in the fixture
    settings.x_accounts = ["threatintel"]
    settings.x_fetch_limit = 5
    
    mock_redis.get.return_value = "0"
    
    collector = XCollector()
    items, errors = await collector.process_accounts()
    
    assert not errors
    # Should fetch 5 items by cycling
    assert len(items) == 5
    
    # All should be threatintel
    for item in items:
        assert item.author_handle == "threatintel"

@pytest.mark.asyncio
async def test_collect_x_data_task(mock_redis):
    with patch("app.tasks.x.group") as mock_group:
        from app.core.config import settings
        settings.x_accounts = ["news"]
        settings.x_fetch_limit = 3

        result = await _collect_x_data()

        assert result["status"] == "completed"
        assert result["items_fetched"] == 3
        assert not result["errors"]
        assert mock_group.call_count == 1
