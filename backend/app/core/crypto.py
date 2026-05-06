import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def _to_fernet_key(raw_key: str) -> bytes:
    key = raw_key.encode("utf-8")
    if len(key) == 44:
        return key
    digest = hashlib.sha256(key).digest()
    return base64.urlsafe_b64encode(digest)


class SecretCrypto:
    def __init__(self, encryption_key: str) -> None:
        self._fernet = Fernet(_to_fernet_key(encryption_key))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            logger.warning(
                "Decryption failed (InvalidToken) — likely caused by an "
                "ENCRYPTION_KEY rotation. The stored secret is no longer "
                "readable and must be re-entered via the Settings page."
            )
            return ""
