import logging
import asyncio

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)

_driver: AsyncDriver | None = None
_driver_lock = asyncio.Lock()


async def get_neo4j_driver() -> AsyncDriver:
    """Lazy, thread-safe initialization of the Neo4j driver."""
    global _driver
    if _driver is not None:
        return _driver

    async with _driver_lock:
        if _driver is not None:
            return _driver

        try:
            logger.info("Initializing Neo4j driver...")
            _driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                max_connection_pool_size=settings.neo4j_max_pool_size,
            )
            # Verify connectivity
            await _driver.verify_connectivity()
            logger.info("Neo4j driver initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize Neo4j driver: %s", e)
            raise

    return _driver


async def close_neo4j_driver() -> None:
    """Close the global Neo4j driver if it exists."""
    global _driver
    async with _driver_lock:
        if _driver is not None:
            await _driver.close()
            _driver = None
            logger.info("Neo4j driver closed.")


async def initialize_schema() -> None:
    """Create uniqueness constraints and performance indexes.

    Constraints double as unique indexes for MERGE lookups.
    The status index accelerates BFS frontier queries.
    """
    driver = await get_neo4j_driver()

    # Uniqueness constraints (also serve as indexes for MERGE)
    constraints = [
        "CREATE CONSTRAINT channel_username_unique IF NOT EXISTS FOR (c:Channel) REQUIRE c.username IS UNIQUE",
        "CREATE CONSTRAINT user_username_unique IF NOT EXISTS FOR (u:User) REQUIRE u.username IS UNIQUE",
        "CREATE CONSTRAINT domain_name_unique IF NOT EXISTS FOR (d:Domain) REQUIRE d.domain IS UNIQUE",
    ]

    # Performance indexes for frequent queries
    indexes = [
        "CREATE INDEX channel_status_idx IF NOT EXISTS FOR (c:Channel) ON (c.status)",
        "CREATE INDEX channel_bfs_depth_idx IF NOT EXISTS FOR (c:Channel) ON (c.bfs_depth)",
    ]

    async with driver.session() as session:
        for query in constraints + indexes:
            try:
                await session.run(query)
            except Exception as e:
                logger.error("Failed to run schema query '%s': %s", query, e)

    logger.info("Neo4j schema constraints and indexes initialized.")
