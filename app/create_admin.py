"""
Script to create the initial admin user.
Run: python -m app.create_admin

The admin credentials can also be set via environment variables:
  ADMIN_EMAIL, ADMIN_USERNAME, ADMIN_PASSWORD

If no env vars are set, it will prompt for credentials interactively.
"""

import os
import sys

from app.database import SessionLocal, init_db
from app.models import User
from app.auth import hash_password


def create_admin():
    """Create the first admin user."""
    init_db()
    db = SessionLocal()

    try:
        # Check if any admin already exists
        existing_admin = db.query(User).filter(User.is_admin == True).first()
        if existing_admin:
            print(f"Admin user already exists: {existing_admin.username} ({existing_admin.email})")
            return

        # Get admin credentials
        email = os.getenv("ADMIN_EMAIL", "")
        username = os.getenv("ADMIN_USERNAME", "")
        password = os.getenv("ADMIN_PASSWORD", "")

        if not email or not username or not password:
            print("No ADMIN_EMAIL/ADMIN_USERNAME/ADMIN_PASSWORD environment variables set.")
            print("Enter credentials for the initial admin user:")
            email = input("Email: ").strip()
            username = input("Username: ").strip()
            password = input("Password: ").strip()

        if not email or not username or not password:
            print("Error: Email, username, and password are required.")
            sys.exit(1)

        if len(password) < 6:
            print("Error: Password must be at least 6 characters.")
            sys.exit(1)

        # Check for existing user with same email/username
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            # Promote existing user to admin
            existing.is_admin = True
            db.commit()
            print(f"Promoted existing user '{existing.username}' to admin.")
            return

        # Create admin user
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            is_admin=True,
        )
        db.add(user)
        db.commit()
        print(f"Admin user '{username}' created successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
