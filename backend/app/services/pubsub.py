import asyncio
import json
import logging

from app.services.cache import get_redis
from app.services.websocket import manager

logger = logging.getLogger(__name__)

import contextlib

ALERTS_CHANNEL = "alerts_channel"

async def publish_alert_to_redis(payload: dict) -> None:
    """Publish an alert payload to the Redis pub/sub channel."""
    redis = get_redis()
    await redis.publish(ALERTS_CHANNEL, json.dumps(payload, default=str))
    logger.debug("Published alert to Redis channel %s", ALERTS_CHANNEL)

async def listen_for_alerts() -> None:
    """Subscribe to the Redis pub/sub channel and broadcast to WebSockets."""
    backoff = 1
    while True:
        pubsub = None
        try:
            redis = get_redis()
            pubsub = redis.pubsub()
            await pubsub.subscribe(ALERTS_CHANNEL)
            logger.info("Started Redis pub/sub listener for alerts on channel %s", ALERTS_CHANNEL)
            backoff = 1  # reset backoff on successful connect
            
            import time
            burst_window_seconds = 5.0
            burst_threshold = 3
            current_burst = []
            burst_start_time = 0.0

            while True:
                if current_burst:
                    timeout = max(0.1, burst_window_seconds - (time.time() - burst_start_time))
                else:
                    timeout = 1.0
                    
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
                if message and message["type"] == "message":
                    try:
                        payload = json.loads(message["data"])
                        if not current_burst:
                            burst_start_time = time.time()
                        current_burst.append(payload)
                    except Exception as e:
                        logger.error("Error decoding pub/sub message: %s", e)

                if current_burst and (time.time() - burst_start_time) >= burst_window_seconds:
                    if len(current_burst) > burst_threshold:
                        has_critical = any(p.get("severity") in ("critical", "CRITICAL") for p in current_burst)
                        burst_payload = {
                            "type": "alert_burst",
                            "count": len(current_burst),
                            "max_severity": "CRITICAL" if has_critical else "HIGH"
                        }
                        await manager.broadcast_json(burst_payload)
                    else:
                        for p in current_burst:
                            await manager.broadcast_json(p)
                    current_burst = []
        except asyncio.CancelledError:
            logger.info("Redis pub/sub listener for alerts cancelled")
            break
        except Exception as e:
            logger.error("Redis pub/sub listener error, retrying in %ds: %s", backoff, e)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
        finally:
            if pubsub:
                with contextlib.suppress(Exception):
                    await pubsub.unsubscribe(ALERTS_CHANNEL)
                    await pubsub.close()
