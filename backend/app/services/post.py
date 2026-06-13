import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.schemas.post import PostCreate, PostUpdate


async def get_post(db: AsyncSession, post_id: uuid.UUID) -> Post | None:
    result = await db.execute(select(Post).where(Post.id == post_id))
    return result.scalar_one_or_none()


async def get_posts(db: AsyncSession, skip: int = 0, limit: int = 100) -> Sequence[Post]:
    result = await db.execute(select(Post).offset(skip).limit(limit))
    return result.scalars().all()


async def create_post(db: AsyncSession, obj_in: PostCreate) -> Post:
    db_obj = Post(**obj_in.model_dump(exclude_unset=True))
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def update_post(db: AsyncSession, db_obj: Post, obj_in: PostUpdate) -> Post:
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def delete_post(db: AsyncSession, db_obj: Post) -> None:
    await db.delete(db_obj)
    await db.commit()
