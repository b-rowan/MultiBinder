from datetime import timedelta
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from app.schemas.user import UserCreate, UserLogin, UserOut, Token
from app.models.user import User
from app.services.auth import (
    get_password_hash,
    create_access_token,
    authenticate_user,
    get_current_user,
)
from app import templates
from app.config import settings
from fastapi import Depends

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")


@router.post("/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    # Check if username exists
    existing_user = await User.filter(username=user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email exists
    existing_email = await User.filter(email=user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    hashed_password = get_password_hash(user_data.password)
    user = await User.create(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
    )

    # Create token
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/auth/login", response_model=Token)
async def login(user_data: UserLogin):
    user = await authenticate_user(user_data.username, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/auth/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
    )
