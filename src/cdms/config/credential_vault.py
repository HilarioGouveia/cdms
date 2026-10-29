"""Criptografia de credenciais com chave própria, separada da assinatura JWT."""
import os
from cryptography.fernet import Fernet, InvalidToken


class CredentialVault:
    def __init__(self, key=None):
        try:
            self._fernet = Fernet(key or os.getenv("CDMS_CREDENTIAL_KEY", ""))
        except (ValueError, TypeError):
            raise RuntimeError("Configure CDMS_CREDENTIAL_KEY com uma chave Fernet válida.") from None

    def encrypt(self, access_token):
        return self._fernet.encrypt(access_token.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext):
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError, UnicodeError):
            raise RuntimeError("CREDENTIALS_UNAVAILABLE") from None
