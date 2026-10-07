import hashlib
import secrets

MOCK_OTP_CODE = "123456"


def generate_session_token() -> str:
    """Random 256-bit token, returned to the client once and never stored."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """What the DB stores, so a leaked database doesn't leak working sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


def is_valid_otp(code: str) -> bool:
    return secrets.compare_digest(code, MOCK_OTP_CODE)
