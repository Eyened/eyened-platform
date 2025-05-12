from typing_extensions import deprecated
from passlib.context import CryptContext
from hashlib import pbkdf2_hmac

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, stored_hash: str):
    return pwd_context.verify(password, stored_hash)


@deprecated("Use hash_password() instead")
def password_hash(password: str, secret_key: str):
    return pbkdf2_hmac("sha256", password.encode(), secret_key.encode(), 10000)
