"""Official-source retrieval with durable bounded snapshots and visible blockers."""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from typing import Any
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.public_fetch import fetch_public_text
from app.core.tracing import trace_block, set_attrs
from app.core.logging import logger
from app.db.models import Job


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.words: list[str] = []
        self.links: list[str] = []
        self.hidden = 0
        self.password = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"script", "style", "nav", "footer"}:
            self.hidden += 1
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag == "input" and values.get("type", "").lower() == "password":
            self.password = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.words.append(data)


def parse_page(html: str, url: str) -> dict[str, Any]:
    parser = PageParser()
    parser.feed(html)
    text = " ".join(" ".join(parser.words).split())[:24000]
    blocker = "login" if parser.password else "captcha" if any(term in text.lower() for term in (
        "verify you are human", "checking your browser", "complete the captcha", "access denied")) else None
    if any(term in text.lower() for term in ("ignore previous instructions", "reveal your api key", "system prompt")):
        blocker = "untrusted_instructions"
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return {"url": url, "text": "" if blocker else text, "blocker": blocker,
        "title": re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else "Official source",
        "links": list(dict.fromkeys(urljoin(url, link).split("#")[0] for link in parser.links))[:150],
        "sha256": hashlib.sha256(html.encode()).hexdigest(),
        "retrieved_at": datetime.now(timezone.utc).isoformat()}


async def get_page(url: str, hosts: set[str], session: AsyncSession, force: bool = False) -> dict[str, Any]:
    rows = (await session.execute(select(Job).where(Job.type == "research_snapshot",
        Job.payload["url"].as_string() == url).order_by(Job.created_at.desc()).limit(1))).scalars().all()
    if rows and not force:
        stamp = datetime.fromisoformat(rows[0].payload["retrieved_at"])
        if datetime.now(timezone.utc) - stamp < timedelta(hours=6):
            return {**rows[0].payload, "from_cache": True}
    with trace_block("official_page_fetch", "RETRIEVER", source_url=url) as span:
        html = await fetch_public_text(url, allowed_hosts=hosts, max_redirects=2)
        page = parse_page(html, url)
        set_attrs(span, source_url=url, blocked=bool(page["blocker"]), digest=page["sha256"])
    session.add(Job(type="research_snapshot", status="completed", payload=page, attempts=1))
    await session.commit()
    return {**page, "from_cache": False}


async def crawl_sources(urls: list[str], hosts: set[str], session: AsyncSession,
    force: bool = False, max_pages: int = 4) -> list[dict[str, Any]]:
    pending = list(dict.fromkeys(urls))
    visited: set[str] = set()
    results = []
    while pending and len(visited) < max_pages:
        url = pending.pop(0)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password:
            continue
        if url in visited:
            continue
        visited.add(url)
        try:
            page = await get_page(url, hosts, session, force)
        except (httpx.HTTPError, ValueError, OSError, TimeoutError):
            logger.warning("Official source retrieval failed", extra={"source_url": url, "outcome": "unavailable"})
            results.append({"url": url, "text": "", "blocker": "unavailable", "links": []})
            continue
        results.append(page)
        if page["blocker"]:
            continue
        pending.extend(link for link in page["links"] if any(term in urlsplit(link).path.lower()
            for term in ("scholarship", "funding", "courses/directory", "requirements"))
            and not link.lower().endswith((".pdf", ".jpg", ".png")))
    return results
