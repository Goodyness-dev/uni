"""Bounded public-page retrieval with DNS pinning and no redirects/proxies."""
import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit, urljoin
import httpx


async def resolve_public(host: str, port: int) -> str:
    records = await asyncio.wait_for(asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM), timeout=5)
    addresses = {record[4][0] for record in records}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("Public research cannot connect to private or mixed DNS destinations.")
    return sorted(addresses)[0]


async def fetch_public_text(url: str, allowed_hosts: set[str] | None = None, max_redirects: int = 0) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Institutional research requires a public HTTPS endpoint.")
    if allowed_hosts is not None and parsed.hostname.lower() not in allowed_hosts:
        raise ValueError("Research host is outside its official-source allowlist.")
    address = await resolve_public(parsed.hostname, 443)
    pinned = httpx.URL(url).copy_with(host=address)
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False, trust_env=False) as client:
        async with client.stream("GET", pinned, headers={"Host": parsed.hostname},
            extensions={"sni_hostname": parsed.hostname}) as response:
            if response.is_redirect and max_redirects > 0 and allowed_hosts:
                return await fetch_public_text(urljoin(url, response.headers.get("location", "")),
                    allowed_hosts=allowed_hosts, max_redirects=max_redirects - 1)
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Public research does not follow redirects.")
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > 1_000_000:
                    raise ValueError("Institutional research response exceeds its size limit.")
            if "text/" not in response.headers.get("content-type", ""):
                raise ValueError("Institutional research requires textual content.")
            return content.decode(response.encoding or "utf-8", errors="replace")
