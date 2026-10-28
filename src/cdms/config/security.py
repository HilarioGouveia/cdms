"""Hash de senhas e tokens JWT com chave configurada fora do código."""
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import jwt
from passlib.context import CryptContext

ALGORITHM = "HS256"
ISSUER = "cdms-api"
AUDIENCE = "cdms-workspace"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto",
                          pbkdf2_sha256__default_rounds=600000)


def get_secret_key(secret_key=None):
    key = secret_key if secret_key is not None else os.getenv("CDMS_SECRET_KEY", "")
    if len(key.encode("utf-8")) < 32:
        raise RuntimeError("Configure CDMS_SECRET_KEY com pelo menos 32 bytes aleatórios.")
    if key == "cdms-super-secret-key-production-change-me":
        raise RuntimeError("A chave demonstrativa não pode ser usada pela API.")
    return key


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta=None, *, secret_key=None) -> str:
    now = datetime.now(timezone.utc)
    payload = dict(data)
    payload.update({"exp": now + (expires_delta if expires_delta is not None else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)),
                    "iat": now, "iss": ISSUER, "aud": AUDIENCE, "jti": str(uuid4())})
    payload.setdefault("token_version", 0)
    return jwt.encode(payload, get_secret_key(secret_key), algorithm=ALGORITHM)


def decode_access_token(token: str, *, secret_key=None) -> dict:
    return jwt.decode(token, get_secret_key(secret_key), algorithms=[ALGORITHM], audience=AUDIENCE,
                      issuer=ISSUER, options={"require": ["exp", "iat", "sub", "workspace_id", "token_version", "jti"]})
