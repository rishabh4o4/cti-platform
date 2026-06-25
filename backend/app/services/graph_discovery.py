import logging
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

import networkx as nx
from neo4j import Transaction

from app.core.config import settings
from app.db.neo4j_session import get_sync_neo4j_driver
from app.services.intelligence import extract_entities

logger = logging.getLogger(__name__)

# Maximum number of channel usernames to track in the depth cache.
# Prevents unbounded memory growth on long-running workers.
_MAX_DEPTH_CACHE_SIZE = 50_000

# Maximum number of message_ids stored on a single FORWARDED_FROM edge.
_MAX_MESSAGE_IDS_PER_EDGE = 100

# Maximum number of nodes to pull into NetworkX for analytics.
# Prevents OOM on large graphs — use Neo4j-native queries for full-graph analytics.
_NETWORKX_EDGE_LIMIT = 50_000


class GraphDiscoveryEngine:
    """Processes Telegram messages to build a Neo4j channel discovery graph.

    Uses a bounded in-memory depth cache backed by Neo4j as the persistent
    source of truth.  Thread-safe singleton — safe to use from multiple
    Celery threads within the same worker process.
    """

    _instance: "GraphDiscoveryEngine | None" = None
    _init_lock = threading.Lock()

    def __new__(cls) -> "GraphDiscoveryEngine":
        # Fast path — no lock if already initialised.
        if cls._instance is not None:
            return cls._instance

        with cls._init_lock:
            # Double-checked locking.
            if cls._instance is not None:
                return cls._instance

            instance = super().__new__(cls)
            instance._driver = get_sync_neo4j_driver()
            # Bounded LRU-style depth cache: username → depth.
            # OrderedDict so we can evict oldest entries when it grows too large.
            instance._depth_cache: OrderedDict[str, int] = OrderedDict()
            instance._cache_lock = threading.Lock()
            instance._load_frontier(instance)
            cls._instance = instance

        return cls._instance

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    @staticmethod
    def _load_frontier(instance: "GraphDiscoveryEngine") -> None:
        """Bootstrap the in-memory depth cache from Neo4j on startup."""
        query = """
        MATCH (c:Channel)
        WHERE c.status = 'queued'
        RETURN c.username AS username, coalesce(c.bfs_depth, 0) AS depth
        ORDER BY c.first_seen ASC
        LIMIT $limit
        """
        try:
            with instance._driver.session() as session:
                result = session.run(query, limit=_MAX_DEPTH_CACHE_SIZE)
                for record in result:
                    username = record["username"]
                    depth = record["depth"]
                    if username:
                        instance._depth_cache[username] = depth
            logger.info(
                "Loaded %d queued channels into BFS depth cache.",
                len(instance._depth_cache),
            )
        except Exception as e:
            logger.error("Failed to load BFS frontier: %s", e)

    # ------------------------------------------------------------------
    # Depth cache helpers
    # ------------------------------------------------------------------

    def _get_depth(self, username: str) -> int:
        """Return cached BFS depth for *username*, or 0 if unknown."""
        with self._cache_lock:
            depth = self._depth_cache.get(username)
            if depth is not None:
                # Move to end so recently-accessed items survive eviction.
                self._depth_cache.move_to_end(username)
            return depth if depth is not None else 0

    def _set_depth(self, username: str, depth: int) -> None:
        """Insert or update depth, evicting the oldest entry if over capacity."""
        with self._cache_lock:
            self._depth_cache[username] = depth
            self._depth_cache.move_to_end(username)
            while len(self._depth_cache) > _MAX_DEPTH_CACHE_SIZE:
                self._depth_cache.popitem(last=False)

    # ------------------------------------------------------------------
    # Message processing
    # ------------------------------------------------------------------

    def process_message(self, content_item: Any) -> None:
        """Extract graph nodes and edges from a Telegram ContentItem."""
        source_id = getattr(content_item, "source_id", "")
        if not source_id:
            return

        raw_text = getattr(content_item, "raw_text", "") or ""
        author_handle = getattr(content_item, "author_handle", "")
        metadata = getattr(content_item, "metadata_", None) or {}

        channel_username = metadata.get("channel", author_handle)
        if not channel_username:
            return

        channel_username = channel_username.lstrip("@").lower()
        message_id = metadata.get("message_id", source_id)

        forwarded_from = metadata.get("forwarded_from")
        if forwarded_from:
            forwarded_from = forwarded_from.lstrip("@").lower()

        timestamp = getattr(content_item, "collected_at", datetime.now(timezone.utc))
        timestamp_str = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)

        entities = extract_entities(raw_text)
        current_depth = self._get_depth(channel_username)

        try:
            with self._driver.session() as session:
                session.execute_write(
                    self._upsert_channel_and_edges,
                    channel_username,
                    timestamp_str,
                    entities,
                    forwarded_from,
                    message_id,
                    current_depth,
                )
        except Exception:
            logger.exception(
                "Graph processing failed for channel=%s message=%s",
                channel_username,
                message_id,
            )

    # ------------------------------------------------------------------
    # Neo4j write transaction
    # ------------------------------------------------------------------

    def _upsert_channel_and_edges(
        self,
        tx: Transaction,
        channel_username: str,
        timestamp_str: str,
        entities: dict,
        forwarded_from: str | None,
        message_id: Any,
        current_depth: int,
    ) -> None:
        # --- Upsert the source channel ---
        tx.run(
            """
            MERGE (c:Channel {username: $username})
            ON CREATE SET
                c.id = randomUUID(),
                c.first_seen = $timestamp,
                c.last_seen = $timestamp,
                c.status = 'explored',
                c.is_seed = CASE WHEN $depth = 0 THEN true ELSE false END,
                c.bfs_depth = $depth,
                c.member_count = 0
            ON MATCH SET
                c.last_seen = $timestamp,
                c.status = CASE
                    WHEN c.status IN ['unexplored', 'queued'] THEN 'explored'
                    ELSE c.status
                END
            """,
            username=channel_username,
            timestamp=timestamp_str,
            depth=current_depth,
        )

        new_channels_discovered = 0
        can_queue = current_depth < settings.max_bfs_depth

        # --- MENTIONED edges (Channel → User) ---
        for user_mention in entities.get("usernames", []):
            mention = user_mention.lstrip("@").lower()
            if mention == channel_username:
                continue
            tx.run(
                """
                MERGE (u:User {username: $mention})
                ON CREATE SET
                    u.id = randomUUID(),
                    u.first_seen = $timestamp,
                    u.last_seen = $timestamp,
                    u.message_count = 0
                ON MATCH SET
                    u.last_seen = $timestamp
                WITH u
                MATCH (c:Channel {username: $channel})
                MERGE (c)-[r:MENTIONED]->(u)
                ON CREATE SET r.count = 1, r.first_seen = $timestamp, r.last_seen = $timestamp
                ON MATCH SET r.count = r.count + 1, r.last_seen = $timestamp
                """,
                mention=mention,
                channel=channel_username,
                timestamp=timestamp_str,
            )

        # --- Discovered channels (invite links) ---
        for link in entities.get("invite_links", []):
            parts = link.split("/")
            if not parts:
                continue
            discovered = parts[-1].split("+")[-1].lower()
            if not discovered or discovered == channel_username:
                continue
            if new_channels_discovered >= settings.graph_new_channels_per_cycle:
                break

            result = tx.run(
                """
                MERGE (c2:Channel {username: $discovered})
                ON CREATE SET
                    c2.id = randomUUID(),
                    c2.first_seen = $timestamp,
                    c2.last_seen = $timestamp,
                    c2.status = 'unexplored',
                    c2.is_seed = false,
                    c2.bfs_depth = $new_depth
                """,
                discovered=discovered,
                timestamp=timestamp_str,
                new_depth=current_depth + 1,
            )
            if result.consume().counters.nodes_created > 0 and can_queue:
                new_channels_discovered += 1
                self._queue_channel(discovered, tx, current_depth + 1)

        # --- FORWARDED_FROM edge (Channel → Channel) ---
        if forwarded_from and forwarded_from != channel_username:
            # Cap message_ids list to prevent unbounded growth.
            result = tx.run(
                """
                MERGE (c2:Channel {username: $forwarded_from})
                ON CREATE SET
                    c2.id = randomUUID(),
                    c2.first_seen = $timestamp,
                    c2.last_seen = $timestamp,
                    c2.status = 'unexplored',
                    c2.is_seed = false,
                    c2.bfs_depth = $new_depth
                WITH c2
                MATCH (c:Channel {username: $channel})
                MERGE (c)-[r:FORWARDED_FROM]->(c2)
                ON CREATE SET
                    r.count = 1,
                    r.first_seen = $timestamp,
                    r.last_seen = $timestamp,
                    r.message_ids = [$message_id]
                ON MATCH SET
                    r.count = r.count + 1,
                    r.last_seen = $timestamp,
                    r.message_ids = CASE
                        WHEN size(r.message_ids) >= $max_ids THEN r.message_ids[$trim_start..] + [$message_id]
                        ELSE r.message_ids + [$message_id]
                    END
                """,
                forwarded_from=forwarded_from,
                channel=channel_username,
                timestamp=timestamp_str,
                message_id=str(message_id),
                new_depth=current_depth + 1,
                max_ids=_MAX_MESSAGE_IDS_PER_EDGE,
                trim_start=1,
            )
            if (
                result.consume().counters.nodes_created > 0
                and can_queue
                and new_channels_discovered < settings.graph_new_channels_per_cycle
            ):
                new_channels_discovered += 1
                self._queue_channel(forwarded_from, tx, current_depth + 1)

        # --- SHARES_DOMAIN edge (Channel → Domain) ---
        for domain in entities.get("domains", []):
            domain_name = domain.lower()
            tld = domain_name.rsplit(".", 1)[-1] if "." in domain_name else ""
            tx.run(
                """
                MERGE (d:Domain {domain: $domain_name})
                ON CREATE SET
                    d.tld = $tld,
                    d.first_seen = $timestamp,
                    d.last_seen = $timestamp,
                    d.threat_category = 'unknown'
                ON MATCH SET d.last_seen = $timestamp
                WITH d
                MATCH (c:Channel {username: $channel})
                MERGE (c)-[r:SHARES_DOMAIN]->(d)
                ON CREATE SET r.domain = $domain_name, r.first_seen = $timestamp
                """,
                domain_name=domain_name,
                tld=tld,
                channel=channel_username,
                timestamp=timestamp_str,
            )

    # ------------------------------------------------------------------
    # BFS queue management
    # ------------------------------------------------------------------

    def _queue_channel(self, username: str, tx: Transaction, depth: int) -> None:
        """Mark a channel as queued in Neo4j and cache its depth."""
        if self._get_depth(username) > 0:
            # Already tracked — don't re-queue.
            return

        tx.run(
            "MATCH (c:Channel {username: $username}) SET c.status = 'queued', c.bfs_depth = $depth",
            username=username,
            depth=depth,
        )
        self._set_depth(username, depth)

        # Dynamically add to Telegram collector channels so they get scraped.
        if username not in settings.telegram_channels:
            settings.telegram_channels.append(username)

        logger.debug("Queued channel %s at depth %d", username, depth)

    # ------------------------------------------------------------------
    # NetworkX analytics
    # ------------------------------------------------------------------

    def get_networkx_graph(self) -> nx.DiGraph:
        """Build a bounded NetworkX DiGraph from Neo4j.

        Uses LIMIT to prevent OOM on large graphs.  For full-graph
        analytics, prefer Neo4j-native Cypher queries.
        """
        query = """
        MATCH (n)-[r]->(m)
        RETURN
            coalesce(n.username, n.domain) AS source_name,
            labels(n)[0] AS source_label,
            coalesce(m.username, m.domain) AS target_name,
            labels(m)[0] AS target_label,
            type(r) AS edge_type
        LIMIT $limit
        """
        G = nx.DiGraph()
        with self._driver.session() as session:
            result = session.run(query, limit=_NETWORKX_EDGE_LIMIT)
            for record in result:
                src = record["source_name"]
                tgt = record["target_name"]
                if src and tgt:
                    G.add_node(src, label=record["source_label"])
                    G.add_node(tgt, label=record["target_label"])
                    G.add_edge(src, tgt, type=record["edge_type"])
        return G

    def degree_centrality(self) -> dict:
        """Compute degree centrality for the bounded subgraph."""
        G = self.get_networkx_graph()
        if len(G) == 0:
            return {}
        return nx.degree_centrality(G)

    def connected_components(self) -> list[set]:
        """Compute connected components on the undirected projection."""
        G = self.get_networkx_graph()
        return list(nx.connected_components(G.to_undirected()))

    def shortest_path(self, source: str, target: str) -> list[str]:
        """Find shortest path between two nodes in the bounded subgraph."""
        G = self.get_networkx_graph()
        try:
            return nx.shortest_path(G, source=source, target=target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
