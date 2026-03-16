"""Crypto API authentication using ED25519 request signing.

Robinhood Crypto Trading API requires ED25519 signatures for each request.
Message format: api_key + timestamp + path + method + body
"""

from __future__ import annotations

import base64
import time

import nacl.signing


def generate_keypair() -> tuple[str, str]:
    """Generate an ED25519 keypair for crypto API authentication.

    Returns:
        Tuple of (private_key_base64, public_key_base64)
    """
    signing_key = nacl.signing.SigningKey.generate()
    verify_key = signing_key.verify_key

    private_key_b64 = base64.b64encode(bytes(signing_key)).decode('ascii')
    public_key_b64 = base64.b64encode(bytes(verify_key)).decode('ascii')

    return private_key_b64, public_key_b64


def sign_request(
    api_key: str,
    private_key_base64: str,
    method: str,
    path: str,
    body: str = "",
) -> tuple[str, str, str]:
    """Sign a Crypto API request using ED25519.

    Args:
        api_key: Robinhood Crypto API key
        private_key_base64: Base64-encoded private key
        method: HTTP method (GET, POST, etc.)
        path: URL path (e.g., '/api/v2/crypto/trading/accounts/')
        body: Request body JSON string (empty for GET requests)

    Returns:
        Tuple of (api_key_header, signature_header, timestamp_header)

    Raises:
        ValueError: If private key is invalid
    """
    # Generate timestamp (valid for 30 seconds)
    timestamp = str(int(time.time()))

    # Create message to sign: api_key + timestamp + path + method + body
    message = f"{api_key}{timestamp}{path}{method}{body}"
    message_bytes = message.encode('utf-8')

    try:
        # Decode private key and create signing key
        private_key_bytes = base64.b64decode(private_key_base64)
        signing_key = nacl.signing.SigningKey(private_key_bytes)

        # Sign the message
        signed = signing_key.sign(message_bytes)
        signature_b64 = base64.b64encode(signed.signature).decode('ascii')

        return api_key, signature_b64, timestamp

    except Exception as e:
        raise ValueError(f"Failed to sign request: {e}") from e


def verify_signature_example() -> bool:
    """Verify the signature using example values from Robinhood documentation.

    This is used for testing to ensure our implementation matches their spec.

    Returns:
        True if signature matches expected value
    """
    # Example values from Robinhood docs
    private_key = "xQnTJVeQLmw1/Mg2YimEViSpw/SdJcgNXZ5kQkAXNPU="
    api_key = "rh-api-6148effc-c0b1-486c-8940-a1d099456be6"
    timestamp = "1698708981"
    expected_signature = (
        "q/nEtxp/P2Or3hph3KejBqnw5o9qeuQ+hYRnB56FaHb"
        "jDsNUY9KhB1asMxohDnzdVFSD7StaTqjSd9U9HvaRAw=="
    )

    # Create message as per spec (from Robinhood docs: cancel order example)
    path = "/api/v1/crypto/trading/orders/"
    method = "POST"
    body = (
        '{"client_order_id":"131de903-5a9c-4260-abc1-28d562a5dcf0",'
        '"side":"buy","type":"market","symbol":"BTC-USD",'
        '"market_order_config":{"asset_quantity":"0.1"}}'
    )
    message = f"{api_key}{timestamp}{path}{method}{body}"
    message_bytes = message.encode('utf-8')

    try:
        # Sign with the example private key
        private_key_bytes = base64.b64decode(private_key)
        signing_key = nacl.signing.SigningKey(private_key_bytes)
        signed = signing_key.sign(message_bytes)
        actual_signature = base64.b64encode(signed.signature).decode('ascii')

        return actual_signature == expected_signature
    except Exception:
        return False
