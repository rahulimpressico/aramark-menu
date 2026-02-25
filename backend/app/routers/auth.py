"""Authentication: login (JWT) and current user."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.auth_store import get_user_by_username, verify_password
from app.dependencies import create_access_token, get_current_user

router = APIRouter(tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    username: str


@router.post("/token", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate with username and password. Returns a JWT access token.
    Use the token in the Authorization header: Bearer <access_token>.
    """
    user = get_user_by_username(form_data.username)
    if user is None or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(sub=user["username"])
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/users/me", response_model=UserMeResponse)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """Return the current authenticated user (requires Bearer token)."""
    return UserMeResponse(username=current_user["username"])
