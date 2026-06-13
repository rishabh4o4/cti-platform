import structlog
import praw
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.schemas.content import ContentIngestRequest
from app.domain.enums import SourceType

logger = structlog.get_logger()


class RedditCollector:
    def __init__(self) -> None:
        if not all([settings.reddit_client_id, settings.reddit_client_secret, settings.reddit_user_agent]) or settings.reddit_client_id == "dummy":
            logger.warning("Reddit credentials not fully configured. Collection may fail.")
            self.reddit = None
        else:
            self.reddit = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
            )

    @property
    def is_mock(self) -> bool:
        return self.reddit is None

    def extract_media_urls(self, post: Any) -> list[str]:
        """Return direct media URLs for a Reddit post.

        source_id convention: bare PRAW post/comment ID string (e.g. ``'abc123'``).
        """
        urls: list[str] = []
        if getattr(post, "is_self", False):
            # Self-posts generally have text but no primary media url
            pass
        elif getattr(post, "is_gallery", False):
            # Gallery posts
            media_metadata = getattr(post, "media_metadata", {})
            for item_data in media_metadata.values():
                if item_data.get("status") == "valid":
                    if "s" in item_data and "u" in item_data["s"]:
                        urls.append(item_data["s"]["u"].replace("&amp;", "&"))
        elif getattr(post, "url", None):
            # Image posts (i.redd.it) and external links
            urls.append(post.url)
        return urls

    def process_subreddits(self) -> tuple[list[ContentIngestRequest], list[str]]:
        """Collect recent posts (and top comments) from configured subreddits.

        Effective batch ceiling per run:
            ``reddit_fetch_limit  × (1 + reddit_comment_limit)`` items.
        """
        if not self.reddit:
            import json
            from pathlib import Path
            fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "reddit_posts.json"
            if fixture_path.exists():
                with open(fixture_path, "r", encoding="utf-8") as f:
                    posts = json.load(f)
                items = []
                for p in posts:
                    items.append(ContentIngestRequest(
                        source=SourceType.REDDIT,
                        source_id=p["id"],
                        author_handle=p["author_handle"],
                        raw_text=p["text"],
                        media_urls=p.get("media_urls", []),
                        collected_at=datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")),
                        metadata={"subreddit": p.get("subreddit", "test"), "type": p.get("type", "post")}
                    ))
                return items, []
            
            mock_item = ContentIngestRequest(
                source=SourceType.REDDIT,
                source_id="mock_reddit_1",
                author_handle="mock_user",
                raw_text="This is a mock reddit post",
                media_urls=[],
                collected_at=datetime.now(timezone.utc),
                metadata={"subreddit": "test", "type": "post"}
            )
            return [mock_item], []

        if not settings.reddit_subreddits:
            logger.warning("No subreddits configured — Reddit collection skipped.")
            return [], []

        all_items = []
        errors = []

        for sub_name in settings.reddit_subreddits:
            try:
                subreddit = self.reddit.subreddit(sub_name)
                for post in subreddit.new(limit=settings.reddit_fetch_limit):
                    author_name = post.author.name if post.author else "[deleted]"
                    raw_text = f"{post.title}\n{post.selftext}".strip()
                    media_urls = self.extract_media_urls(post)
                    collected_at = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)

                    post_item = ContentIngestRequest(
                        source=SourceType.REDDIT,
                        source_id=post.id,
                        author_handle=author_name,
                        raw_text=raw_text,
                        media_urls=media_urls,
                        collected_at=collected_at,
                        metadata={"subreddit": sub_name, "permalink": post.permalink, "type": "post"}
                    )
                    all_items.append(post_item)

                    post.comments.replace_more(limit=0)
                    comments = post.comments.list()[:settings.reddit_comment_limit]
                    for comment in comments:
                        c_author_name = comment.author.name if comment.author else "[deleted]"
                        c_collected_at = datetime.fromtimestamp(comment.created_utc, tz=timezone.utc)
                        comment_item = ContentIngestRequest(
                            source=SourceType.REDDIT,
                            source_id=comment.id,
                            author_handle=c_author_name,
                            raw_text=comment.body,
                            media_urls=[],
                            collected_at=c_collected_at,
                            metadata={"subreddit": sub_name, "permalink": comment.permalink, "parent_id": comment.parent_id, "type": "comment"}
                        )
                        all_items.append(comment_item)

            except Exception as e:
                logger.exception("Error processing subreddit", subreddit=sub_name)
                errors.append(f"Error on r/{sub_name}: {str(e)}")

        return all_items, errors
