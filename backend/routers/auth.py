from fastapi import APIRouter, HTTPException
from ..models.schemas import UserCreate, UserLogin, Token
from ..services.database import db
from ..services.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token)
def register(data: UserCreate):
    if db.get_user_by_email(data.email):
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    hashed = hash_password(data.password)
    user = db.create_user(data.name, data.email, hashed, data.role)
    token = create_access_token({"sub": user["id"], "role": user["role"]})
    return Token(access_token=token, token_type="bearer",
                 user_id=user["id"], name=user["name"], role=user["role"])


@router.post("/login", response_model=Token)
def login(data: UserLogin):
    user = db.get_user_by_email(data.email)
    if not user or not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos")
    token = create_access_token({"sub": user["id"], "role": user["role"]})
    return Token(access_token=token, token_type="bearer",
                 user_id=user["id"], name=user["name"], role=user["role"])
