import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from sqlalchemy import select

from app.services.reddit import RedditCollector
from app.tasks.reddit import _collect_reddit_data
from app.schemas.content import ContentIngestRequest
from app.domain.enums import SourceType
from app.services.content import ingest_content
from app.models.content import ContentItem

@pytest.fixture
def mock_praw():
    with patch("app.services.reddit.praw.Reddit") as mock_reddit:
        reddit_instance = MagicMock()
        mock_reddit.return_value = reddit_instance
        
        mock_subreddit = MagicMock()
        reddit_instance.subreddit.return_value = mock_subreddit
        
        mock_post = MagicMock()
        mock_post.id = "post123"
        mock_post.author.name = "test_user"
        mock_post.title = "Test Post"
        mock_post.selftext = "This is a test post."
        mock_post.created_utc = 1700000000
        mock_post.permalink = "/r/test/comments/post123/"
        mock_post.is_self = True
        mock_post.is_gallery = False
        mock_post.url = "https://reddit.com/r/test/comments/post123/"
        
        mock_comment = MagicMock()
        mock_comment.id = "comment456"
        mock_comment.author.name = "comment_user"
        mock_comment.body = "This is a test comment."
        mock_comment.created_utc = 1700000100
        mock_comment.permalink = "/r/test/comments/post123/-/comment456/"
        mock_comment.parent_id = "t3_post123"
        
        mock_comments_manager = MagicMock()
        mock_comments_manager.list.return_value = [mock_comment]
        mock_post.comments = mock_comments_manager
        
        mock_subreddit.new.return_value = [mock_post]
        
        yield mock_reddit

@pytest.mark.asyncio
async def test_reddit_collector_parsing(mock_praw):
    from app.core.config import settings
    settings.reddit_subreddits = ["test"]
    settings.reddit_client_id = "test_id"
    settings.reddit_client_secret = "test_secret"
    settings.reddit_user_agent = "test_ua"
    
    collector = RedditCollector()
    items, errors = collector.process_subreddits()
    
    assert not errors
    assert len(items) == 2
    
    post_item = items[0]
    assert isinstance(post_item, ContentIngestRequest)
    assert post_item.source == SourceType.REDDIT
    assert post_item.source_id == "post123"
    assert post_item.author_handle == "test_user"
    assert post_item.raw_text == "Test Post\nThis is a test post."
    assert post_item.metadata["type"] == "post"
    assert post_item.collected_at == datetime.fromtimestamp(1700000000, tz=timezone.utc)
    
    comment_item = items[1]
    assert isinstance(comment_item, ContentIngestRequest)
    assert comment_item.source_id == "comment456"
    assert comment_item.author_handle == "comment_user"
    assert comment_item.raw_text == "This is a test comment."
    assert comment_item.metadata["type"] == "comment"
    assert comment_item.collected_at == datetime.fromtimestamp(1700000100, tz=timezone.utc)

@pytest.mark.asyncio
async def test_collect_reddit_data_task(mock_praw):
    with patch("app.tasks.reddit.group") as mock_group:
        from app.core.config import settings
        settings.reddit_subreddits = ["test"]
        settings.reddit_client_id = "test_id"
        settings.reddit_client_secret = "test_secret"
        settings.reddit_user_agent = "test_ua"
        
        result = await _collect_reddit_data()
        
        assert result["status"] == "completed"
        assert result["items_fetched"] == 2
        assert not result["errors"]
        assert mock_group.call_count == 1


@pytest.mark.asyncio
async def test_ingest_content_unique_violation(db_session):
    request = ContentIngestRequest(
        source=SourceType.REDDIT,
        source_id="dup_post",
        author_handle="user1",
        raw_text="Test",
        collected_at=datetime.fromtimestamp(1700000000, tz=timezone.utc),
        metadata={"subreddit": "test"}
    )
    
    item1, created1, _ = await ingest_content(db_session, request, enqueue=False)
    assert created1 is True
    
    async def mock_get_content(*args, **kwargs):
        result = await args[0].execute(
            select(ContentItem).where(
                ContentItem.source == args[1],
                ContentItem.source_id == args[2]
            )
        )
        return result.scalar_one_or_none()

    with patch("app.services.content.get_content_by_source_id", side_effect=mock_get_content):
        # We also need to patch cache.delete_key to avoid errors during test if it's called
        with patch("app.services.cache.delete_key"):
            item2, created2, _ = await ingest_content(db_session, request, enqueue=False)
            assert created2 is False
            assert item2.id == item1.id
