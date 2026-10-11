"""Signed webhook delivery engine for ScholarPilot application events."""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import logger
from app.core.security import sign_webhook_payload
from app.db.models import Webhook


class WebhookDeliveryResult:
    def __init__(self, webhook_id: uuid.UUID, url: str, success: bool, status_code: Optional[int] = None, error: Optional[str] = None):
        self.webhook_id = webhook_id
        self.url = url
        self.success = success
        self.status_code = status_code
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "webhook_id": str(self.webhook_id),
            "url": self.url,
            "success": self.success,
            "status_code": self.status_code,
            "error": self.error,
        }


async def dispatch_user_webhooks(
    user_id: uuid.UUID,
    event_type: str,
    payload: Dict[str, Any],
    session: AsyncSession,
    max_retries: int = 3,
    client: Optional[httpx.AsyncClient] = None,
) -> List[Dict[str, Any]]:
    """Delivers HMAC-SHA256 signed event payload to all matching active webhooks for a user."""
    # Find all webhooks for this user that subscribe to this event or to '*'
    stmt = select(Webhook).where(Webhook.user_id == user_id)
    result = await session.execute(stmt)
    webhooks = result.scalars().all()

    matching_webhooks = [
        wh for wh in webhooks
        if not wh.events_subscribed or event_type in wh.events_subscribed or "*" in wh.events_subscribed
    ]

    if not matching_webhooks:
        return []

    delivery_package = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": str(user_id),
        "data": payload,
    }
    payload_bytes = json.dumps(delivery_package, sort_keys=True).encode("utf-8")

    results: List[Dict[str, Any]] = []
    own_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=5.0)
        own_client = True

    try:
        for wh in matching_webhooks:
            signature = sign_webhook_payload(payload_bytes, wh.secret)
            headers = {
                "Content-Type": "application/json",
                "X-ScholarPilot-Signature": signature,
                "X-ScholarPilot-Event": event_type,
                "User-Agent": "ScholarPilot-Webhook-Dispatcher/1.0",
            }

            delivered = False
            last_err = None
            status_code = None

            for attempt in range(1, max_retries + 1):
                try:
                    resp = await client.post(wh.url, content=payload_bytes, headers=headers)
                    status_code = resp.status_code
                    if 200 <= status_code < 300:
                        delivered = True
                        break
                    else:
                        last_err = f"HTTP {status_code}: {resp.text[:100]}"
                except Exception as e:
                    last_err = str(e)

            if delivered:
                logger.info(f"Webhook {wh.id} successfully delivered for event {event_type} to {wh.url}")
                results.append(WebhookDeliveryResult(wh.id, wh.url, True, status_code).to_dict())
            else:
                logger.warning(f"Webhook {wh.id} failed after {max_retries} attempts: {last_err}")
                wh.failure_count += 1
                await session.commit()
                results.append(WebhookDeliveryResult(wh.id, wh.url, False, status_code, last_err).to_dict())

    finally:
        if own_client:
            await client.aclose()

    return results
