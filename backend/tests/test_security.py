from cryptography.fernet import Fernet

from app.config import Settings
from app.security import SessionCodec, TokenCipher


def test_token_cipher_round_trip() -> None:
    settings = Settings(token_encryption_key=Fernet.generate_key().decode())
    cipher = TokenCipher(settings)
    encrypted = cipher.encrypt("secret-token-cache")
    assert encrypted != "secret-token-cache"
    assert cipher.decrypt(encrypted) == "secret-token-cache"


def test_session_codec_round_trip() -> None:
    codec = SessionCodec(Settings(session_secret="test-secret"))
    value = codec.dumps({"user_id": "abc"})
    assert codec.loads(value) == {"user_id": "abc"}
