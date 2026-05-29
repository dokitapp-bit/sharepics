from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .database import db
import hashlib, os

SECRET_KEY = os.getenv("SECRET_KEY", "sharedpics-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split(":", 1)
        return hashlib.sha256(f"{salt}{plain}".encode()).hexdigest() == h
    except Exception:
        return False


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Token não fornecido")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        user = db.get_user(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expirado ou inválido")
