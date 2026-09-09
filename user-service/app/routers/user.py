from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional
from .. import security

router = APIRouter(prefix="/api/users", tags=["users"])

# In-memory user store (keyed by email)
_fake_users: dict = {}
_next_id: int = 1


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    global _next_id
    if user.email in _fake_users:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = security.get_password_hash(user.password)
    _fake_users[user.email] = {
        "id": _next_id,
        "email": user.email,
        "full_name": user.full_name,
        "hashed_password": hashed,
    }
    _next_id += 1
    return UserOut(**{k: v for k, v in _fake_users[user.email].items() if k != "hashed_password"})


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = _fake_users.get(form_data.username)
    if not user or not security.verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token = security.create_access_token({"sub": user["email"]})
    return Token(access_token=token)


def get_current_user(token: str = Depends(security.oauth2_scheme)):
    payload = security.decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    email = payload.get("sub")
    user = _fake_users.get(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/me", response_model=UserOut)
async def read_me(current_user: dict = Depends(get_current_user)):
    return UserOut(id=current_user["id"], email=current_user["email"], full_name=current_user.get("full_name"))
