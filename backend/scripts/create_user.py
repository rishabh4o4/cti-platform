import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import structlog
from app.db.session import async_session_maker
from app.models.user import User
from app.domain.enums import Role
from app.core.security import hash_password

logger = structlog.get_logger()

async def create_user(username: str, password: str, role: str, force: bool):
    try:
        role_enum = Role(role.lower())
    except ValueError:
        logger.error("Invalid role", role=role)
        sys.exit(1)

    if len(username) < 3:
        logger.error("Username must be at least 3 characters long.")
        sys.exit(1)
        
    if len(password) < 6:
        logger.error("Password must be at least 6 characters long.")
        sys.exit(1)

    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if user:
            if not force:
                logger.error("User already exists", username=username)
                sys.exit(1)
            else:
                user.hashed_password = hash_password(password)
                user.role = role_enum
                user.is_active = True
                await db.commit()
                logger.info("User updated successfully", username=username)
        else:
            new_user = User(
                username=username,
                hashed_password=hash_password(password),
                role=role_enum,
                is_active=True,
            )
            db.add(new_user)
            await db.commit()
            logger.info("User created successfully", username=username)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update a user.")
    parser.add_argument("username", type=str, help="The username for the new user")
    parser.add_argument("password", type=str, help="The password for the new user")
    parser.add_argument("--role", type=str, default="viewer", help="The role of the user (admin, analyst, viewer)")
    parser.add_argument("--force", action="store_true", help="Update password and role if user already exists")

    args = parser.parse_args()

    asyncio.run(create_user(args.username, args.password, args.role, args.force))
