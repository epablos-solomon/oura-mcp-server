import hashlib
import hmac


def verify_oura_signature(timestamp: str, body: bytes, signature: str, client_secret: str) -> bool:
    if not timestamp or not signature or not client_secret:
        return False
    mac = hmac.new(client_secret.encode(), digestmod=hashlib.sha256)
    mac.update(timestamp.encode() + body)
    expected = mac.hexdigest().upper()
    return hmac.compare_digest(expected, signature)
