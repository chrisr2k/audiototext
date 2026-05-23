"""
Admin router for user management.
Only accessible by users with is_admin=True.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.auth import hash_password, security
from app.templates import templates

router = APIRouter(prefix="/admin", tags=["admin"])


async def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Dependency that ensures the current user is an admin.
    
    Checks Authorization header first, then falls back to 'token' query parameter
    (used for direct page navigation where the browser doesn't send auth headers),
    and finally checks POST form data (for HTML form submissions like disable/promote/delete).
    """
    user = None
    
    # Try Authorization header first
    if credentials is not None:
        try:
            token = credentials.credentials
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id: str = payload.get("sub")
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
        except JWTError:
            pass
    
    # Fall back to token query parameter (for direct page navigation)
    if user is None:
        token = request.query_params.get("token")
        if token:
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                user_id: str = payload.get("sub")
                if user_id:
                    user = db.query(User).filter(User.id == user_id).first()
            except JWTError:
                pass
    
    # Fall back to POST form data (for HTML form submissions like disable/promote/delete)
    if user is None:
        try:
            form = await request.form()
            token = form.get("token")
            if token:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                user_id: str = payload.get("sub")
                if user_id:
                    user = db.query(User).filter(User.id == user_id).first()
        except JWTError:
            pass
        except Exception:
            pass
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


@router.get("/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin page to manage all users."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "user": admin,
        "users": users,
        "demo_mode": settings.DEMO_MODE,
    })


@router.post("/users/create")
async def admin_create_user(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new user (admin only)."""
    form = await request.form()
    username = form.get("username", "").strip()
    email = form.get("email", "").strip()
    password = form.get("password", "")
    token = form.get("token", "")

    if not username or not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username, email, and password are required",
        )

    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters",
        )

    # Check for existing user
    existing = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists",
        )

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
    )
    db.add(user)
    db.commit()

    redirect_url = f"/admin/users?token={token}" if token else "/admin/users"
    return RedirectResponse(url=redirect_url, status_code=303)


async def _get_token_from_form(request: Request) -> str:
    """Extract the auth token from the form data.
    
    The form data may have been consumed by require_admin already,
    but Starlette caches the result so calling request.form() again
    returns the same data.
    """
    try:
        form = await request.form()
        return form.get("token", "")
    except Exception:
        return ""


@router.post("/users/{user_id}/toggle-active")
async def admin_toggle_active(
    request: Request,
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Enable or disable a user account."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent disabling yourself
    if target.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot disable your own account",
        )

    target.is_active = not target.is_active
    db.commit()

    # Preserve token from form data (the hidden input in the HTML form)
    token = await _get_token_from_form(request)
    redirect_url = f"/admin/users?token={token}" if token else "/admin/users"
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/users/{user_id}/toggle-admin")
async def admin_toggle_admin(
    request: Request,
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Grant or revoke admin privileges."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent removing admin from yourself
    if target.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own admin privileges",
        )

    target.is_admin = not target.is_admin
    db.commit()

    # Preserve token from form data (the hidden input in the HTML form)
    token = await _get_token_from_form(request)
    redirect_url = f"/admin/users?token={token}" if token else "/admin/users"
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/users/{user_id}/delete")
async def admin_delete_user(
    request: Request,
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a user and all their transcripts."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent deleting yourself
    if target.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    db.delete(target)
    db.commit()

    # Preserve token from form data (the hidden input in the HTML form)
    token = await _get_token_from_form(request)
    redirect_url = f"/admin/users?token={token}" if token else "/admin/users"
    return RedirectResponse(url=redirect_url, status_code=303)
