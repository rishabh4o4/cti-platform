import logging
import uuid
import time
import re
from typing import Any

from asgiref.sync import async_to_sync

from app.domain.enums import RiskLabel, SourceType
from app.services.alerts import create_alert_if_needed
from app.services.analysis import create_analysis_result
from app.tasks.alerts import dispatch_alert_notification
from app.tasks.celery_app import celery_app
from app.services.risk_scoring import RiskScoringEngine
from app.schemas.risk import RiskScoringInput

logger = logging.getLogger(__name__)

# Basic keyword heuristic
KEYWORDS = {"scam", "hack", "leak", "dump", "buy", "sell", "cc", "cvv", "stolen", "carding", "fraud", "phishing", "malware", "virus", "botnet", "exploit", "weapon", "drugs"}

from neo4j.exceptions import ServiceUnavailable

@celery_app.task(
    name="app.tasks.scoring.run_scoring",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TimeoutError, ConnectionError, ServiceUnavailable),
    retry_backoff=True,
)
def run_scoring(self, upstream_results: list[dict[str, Any]], content_id: str) -> dict[str, Any]:
    return async_to_sync(_run_scoring)(upstream_results, content_id)


async def _run_scoring(upstream_results: list[dict[str, Any]], content_id: str) -> dict[str, Any]:
    start_time = time.time()
    from app.db.session import async_session_maker

    nlp_result = next((r for r in upstream_results if r.get("stage") == "nlp"), {})
    vision_result = next((r for r in upstream_results if r.get("stage") == "vision"), {})
    
    nlp_flags = nlp_result.get("flags", {})
    vision_flags = vision_result.get("flags", {})

    async with async_session_maker() as db:
        from app.services.content import get_content_by_id
        content_item = await get_content_by_id(db, uuid.UUID(content_id))

        if not content_item:
            logger.error(f"Content {content_id} not found.")
            return {"status": "error"}

        channel_username = ""
        if content_item.metadata_:
            channel_username = content_item.metadata_.get("channel", content_item.author_handle or "")
        else:
            channel_username = content_item.author_handle or ""
        
        channel_username = channel_username.lstrip("@").lower()

        # Initialize inputs and mask
        confidence_mask = {
            "keyword_density": 1.0,
            "graph_centrality": 0.0,
            "member_count": 0.0,
            "growth_velocity": 0.0,
            "cross_link_count": 0.0,
            "ioc_density": 1.0,
            "nlp_threat_confidence": 1.0
        }

        # 1. nlp_threat_confidence
        category = nlp_flags.get("category", "safe")
        nlp_confidence = nlp_flags.get("confidence", 0.0)
        if category == "uncertain":
            nlp_confidence = 0.0
            confidence_mask["nlp_threat_confidence"] = 0.0
        
        # 2. ioc_density
        entities = nlp_flags.get("entities", {})
        ioc_tokens = set()
        ioc_count = 0
        for k in ["urls", "domains", "emails", "phones", "ips", "crypto_wallets", "invite_links"]:
            items = entities.get(k, [])
            ioc_count += len(items)
            for item in items:
                ioc_tokens.update(re.findall(r'\b\w+\b', item.lower()))
                
        raw_text = content_item.raw_text or ""
        words = re.findall(r'\b\w+\b', raw_text.lower())
        word_count = len(words)
        ioc_density = float(ioc_count) / max(word_count, 1)

        # 3. keyword_density
        # exclude tokens already counted as IOCs
        keyword_hits = 0
        for w in words:
            if w in KEYWORDS and w not in ioc_tokens:
                keyword_hits += 1
        keyword_density = float(keyword_hits) / max(word_count, 1)

        # 4. member_count
        member_count = 0
        if content_item.metadata_ and "member_count" in content_item.metadata_:
            member_count = int(content_item.metadata_.get("member_count", 0))
            confidence_mask["member_count"] = 1.0
        
        # 5. growth_velocity
        # Since we don't have historical data readily available here, mask it out
        growth_velocity = 0.0
        
        graph_centrality = 0.0
        cross_link_count = 0

        if content_item.source == SourceType.TELEGRAM:
            from app.services.graph_discovery import GraphDiscoveryEngine
            import asyncio
            
            engine = GraphDiscoveryEngine()
            
            # Run Graph Update Synchronously BEFORE scoring
            try:
                await asyncio.to_thread(engine.process_message, content_item)
            except Exception:
                logger.exception(f"Graph update failed for {content_id}")

            # 6. cross_link_count
            try:
                query = "MATCH (c:Channel {username: $username})-[r:FORWARDED_FROM|SHARES_DOMAIN]->() RETURN count(r) as cl_count"
                with engine._driver.session() as session:
                    result = session.run(query, username=channel_username)
                    record = result.single()
                    if record:
                        cross_link_count = int(record["cl_count"])
                        confidence_mask["cross_link_count"] = 1.0
            except Exception:
                logger.warning("Failed to fetch cross_link_count from Neo4j.")
                confidence_mask["cross_link_count"] = 0.0

            # 7. graph_centrality
            try:
                centralities = await asyncio.to_thread(engine.degree_centrality)
                if not centralities:
                    # Genuinely new channel or empty graph
                    graph_centrality = 0.0
                    confidence_mask["graph_centrality"] = 1.0
                else:
                    graph_centrality = centralities.get(channel_username, 0.0)
                    confidence_mask["graph_centrality"] = 1.0
            except Exception:
                logger.warning("Failed to fetch graph_centrality from Neo4j.")
                confidence_mask["graph_centrality"] = 0.0

        # Calculate Risk Score
        risk_input = RiskScoringInput(
            keyword_density=keyword_density,
            graph_centrality=graph_centrality,
            member_count=member_count,
            growth_velocity=growth_velocity,
            cross_link_count=cross_link_count,
            ioc_density=ioc_density,
            nlp_threat_confidence=nlp_confidence,
            confidence_mask=confidence_mask
        )

        scoring_result = RiskScoringEngine.calculate_score(risk_input)

        # Update DB
        analysis = await create_analysis_result(
            db,
            content_id=uuid.UUID(content_id),
            risk_score=scoring_result.score,
            risk_label=RiskLabel(scoring_result.severity.value.lower()),
            nlp_flags=nlp_flags,
            vision_flags=vision_flags,
            score_breakdown=scoring_result.details,
            model_version=_model_version_from_results(upstream_results),
            engine_version=scoring_result.engine_version,
            weights_snapshot=scoring_result.weights_snapshot,
            data_confidence=scoring_result.data_confidence,
        )

        alert = await create_alert_if_needed(
            db,
            content_id=uuid.UUID(content_id),
            risk_score=scoring_result.score,
            content_item=content_item,
            analysis_result=analysis,
        )

    if alert:
        dispatch_alert_notification.apply_async(args=[str(alert.id)], queue="alerts")

    elapsed_time = time.time() - start_time
    logger.info(f"_run_scoring completed in {elapsed_time:.3f} seconds for content_id {content_id}.")

    return {
        "content_id": content_id,
        "analysis_id": str(analysis.id),
        "risk_score": scoring_result.score,
        "risk_label": scoring_result.severity.value,
        "alert_created": alert is not None,
    }

def _model_version_from_results(results: list[dict[str, Any]]) -> str:
    """Extract model_version from the NLP stage result, if available."""
    for result in results:
        if result.get("stage") == "nlp" and result.get("model_version"):
            return result["model_version"]
    return "skeleton-no-models-v0"
