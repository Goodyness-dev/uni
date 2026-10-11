"""Cryptographic utilities: portal credential encryption, API key hashing, HMAC webhooks."""
import base64
import hashlib
import hmac
import secrets
from cryptography.fernet import Fernet
from app.core.config import settings


def _get_fernet() -> Fernet:
    """Returns a Fernet instance using the configured ENCRYPTION_KEY."""
    # Ensure key is properly padded/formatted for Fernet (32 url-safe base64-encoded bytes)
    raw_key = settings.ENCRYPTION_KEY.encode("utf-8")
    try:
        return Fernet(raw_key)
    except Exception:
        # Fallback: derive a valid 32-byte urlsafe base64 key from sha256
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key).digest())
        return Fernet(derived)


def encrypt_credential(plain_text: str) -> str:
    """Encrypts a sensitive credential (e.g., portal password) at rest."""
    if not plain_text:
        return ""
    f = _get_fernet()
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_credential(cipher_text: str) -> str:
    """Decrypts an encrypted credential at rest."""
    if not cipher_text:
        return ""
    f = _get_fernet()
    return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")


def generate_api_key(prefix: str = "sp_live_") -> tuple[str, str]:
    """Generates a secure API key and its SHA-256 hash for database storage.
    
    Returns:
        (plain_key, hashed_key) - plain_key is returned once to the user; hashed_key is stored.
    """
    token = secrets.token_urlsafe(32)
    plain_key = f"{prefix}{token}"
    hashed_key = hash_api_key(plain_key)
    return plain_key, hashed_key


def hash_api_key(api_key: str) -> str:
    """Hashes an API key using SHA-256 for secure lookup."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Constant-time verification of an API key against its stored hash."""
    candidate_hash = hash_api_key(plain_key)
    return hmac.compare_digest(candidate_hash, hashed_key)


def sign_webhook_payload(payload_bytes: bytes, secret: str) -> str:
    """Calculates an HMAC-SHA256 signature for outgoing webhook deliveries."""
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def verify_webhook_signature(payload_bytes: bytes, secret: str, signature: str) -> bool:
    """Verifies the HMAC-SHA256 signature of an incoming webhook."""
    expected = sign_webhook_payload(payload_bytes, secret)
    return hmac.compare_digest(expected, signature)
