from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates import templates
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.auth import hash_password, verify_password, create_access_token, get_current_user, get_optional_user

router = APIRouter(prefix="/auth", tags=["auth"])


# --- API Models ---

class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


# --- Page Routes ---

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: User = Depends(get_optional_user)):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "user": user,
        "demo_mode": settings.DEMO_MODE,
    })


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page - redirects to login since self-registration is disabled."""
    return RedirectResponse(url="/auth/login")


# --- API Routes ---

@router.post("/register")
async def register():
    """Self-registration is disabled. Users can only be created by an admin."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Self-registration is disabled. Contact an administrator to create an account.",
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    # Find user by username or email
    user = db.query(User).filter(
        (User.username == data.username) | (User.email == data.username)
    ).first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Generate token
    token = create_access_token({"sub": user.id})

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
