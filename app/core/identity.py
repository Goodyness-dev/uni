"""Pinned-issuer RS256 identity verification; no token-derived key URLs."""
import base64
import hashlib
import json
import time
from urllib.parse import urlsplit
from typing import Any
import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from app.core.config import settings
from app.jobs.queue import get_redis_client


def decode_segment(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate identity token fields are forbidden.")
        result[key] = value
    return result


def validate_claims(claims: dict[str, Any], email: str) -> None:
    now = time.time()
    if claims.get("iss") != settings.OIDC_ISSUER or claims.get("email_verified") is not True:
        raise ValueError("Identity issuer or verified email is invalid.")
    audience = claims.get("aud")
    audiences = [audience] if isinstance(audience, str) else audience
    if not isinstance(audiences, list) or settings.OIDC_AUDIENCE not in audiences:
        raise ValueError("Identity token audience is invalid.")
    if (len(audiences) > 1 or "azp" in claims) and claims.get("azp") != settings.OIDC_AUDIENCE:
        raise ValueError("Identity token authorized party is invalid.")
    for name in ("exp", "iat"):
        if type(claims.get(name)) not in (int, float):
            raise ValueError("Identity token timestamps are missing.")
    if not now < claims["exp"] <= now + 86400 or not now - 600 <= claims["iat"] <= now + 30:
        raise ValueError("Identity token is expired or too old for key issuance.")
    if "nbf" in claims and (type(claims["nbf"]) not in (int, float) or claims["nbf"] > now):
        raise ValueError("Identity token is not yet valid.")
    if not isinstance(claims.get("sub"), str) or not 1 <= len(claims["sub"]) <= 255:
        raise ValueError("Identity subject is missing.")
    if not isinstance(claims.get("email"), str) or claims["email"].casefold() != email.casefold():
        raise ValueError("Requested email does not match the verified identity.")


async def verify_identity(token: str, email: str) -> str:
    if not all((settings.OIDC_ISSUER, settings.OIDC_AUDIENCE, settings.OIDC_JWKS_URL)):
        raise ValueError("Identity provider configuration is incomplete.")
    for url in (settings.OIDC_ISSUER, settings.OIDC_JWKS_URL):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Identity provider endpoints must use configured HTTPS URLs.")
    if len(token) > 16384:
        raise ValueError("Identity token is too large.")
    pieces = token.split(".")
    if len(pieces) != 3:
        raise ValueError("Malformed identity token.")
    header = json.loads(decode_segment(pieces[0]), object_pairs_hook=unique_object)
    claims = json.loads(decode_segment(pieces[1]), object_pairs_hook=unique_object)
    if not isinstance(header, dict) or not isinstance(claims, dict) or header.get("alg") != "RS256" or header.get("crit") or not isinstance(header.get("kid"), str):
        raise ValueError("Unsupported identity token signature.")
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        response = await client.get(settings.OIDC_JWKS_URL)
        response.raise_for_status()
        if len(response.content) > 1_000_000:
            raise ValueError("Identity key response exceeded its limit.")
        keys = response.json().get("keys", [])
    matching = [key for key in keys if key.get("kid") == header.get("kid") and key.get("kty") == "RSA"
        and key.get("use", "sig") == "sig" and key.get("alg", "RS256") == "RS256"]
    if len(matching) != 1:
        raise ValueError("Identity signing key could not be uniquely identified.")
    key = matching[0]
    modulus = int.from_bytes(decode_segment(key["n"]), "big")
    if modulus.bit_length() < 2048:
        raise ValueError("Identity signing key is too small.")
    public = rsa.RSAPublicNumbers(int.from_bytes(decode_segment(key["e"]), "big"), modulus).public_key()
    public.verify(decode_segment(pieces[2]), (pieces[0] + "." + pieces[1]).encode(), padding.PKCS1v15(), hashes.SHA256())
    validate_claims(claims, email)
    broker = await get_redis_client()
    if broker is None:
        raise ValueError("Identity replay protection is unavailable.")
    digest = hashlib.sha256(token.encode()).hexdigest()
    if not await broker.set("scholarpilot:identity_used:" + digest, "1", nx=True, ex=max(1, int(claims["exp"] - time.time()))):
        raise ValueError("Identity token was already exchanged.")
    return hashlib.sha256((claims["iss"] + "\0" + claims["sub"]).encode()).hexdigest()
