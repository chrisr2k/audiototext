#!/bin/bash
# ============================================================
# AudioToText - Docker Entrypoint Script
# ============================================================
set -e

echo "============================================"
echo "  AudioToText - Starting Application"
echo "============================================"

# Wait for database if using PostgreSQL
if [[ "$DATABASE_URL" == postgresql* ]]; then
    echo "Waiting for PostgreSQL to be ready..."
    # Extract host and port from DATABASE_URL
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\).*/\1/p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_PORT=${DB_PORT:-5432}
    DB_HOST=${DB_HOST:-db}

    echo "  Host: $DB_HOST, Port: $DB_PORT"
    for i in $(seq 1 30); do
        # Use python to check TCP connection (nc may not be available)
        if python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('$DB_HOST', $DB_PORT)); s.close()" 2>/dev/null; then
            echo "  Database is ready!"
            break
        fi
        echo "  Waiting... ($i/30)"
        sleep 2
    done
fi

# Initialize database tables
echo "Initializing database..."
python -c "
from app.database import init_db
init_db()
print('Database tables created successfully')
"

# Create admin user if env vars are set
if [[ -n "$ADMIN_EMAIL" && -n "$ADMIN_USERNAME" && -n "$ADMIN_PASSWORD" ]]; then
    echo "Creating admin user..."
    python -c "
import os
from app.database import SessionLocal
from app.models import User
from app.auth import hash_password

db = SessionLocal()
try:
    admin_email = os.environ.get('ADMIN_EMAIL', '')
    admin_username = os.environ.get('ADMIN_USERNAME', '')
    admin_password = os.environ.get('ADMIN_PASSWORD', '')
    
    existing = db.query(User).filter(
        (User.username == admin_username) | (User.email == admin_email)
    ).first()
    if existing:
        existing.is_admin = True
        print(f'Admin privileges granted to existing user: {existing.username}')
    else:
        user = User(
            email=admin_email,
            username=admin_username,
            hashed_password=hash_password(admin_password),
            is_admin=True,
        )
        db.add(user)
        print(f'Admin user created: {user.username}')
    db.commit()
finally:
    db.close()
"
fi

# Start the application
echo "Starting uvicorn server..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers ${UVICORN_WORKERS:-4} \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    --log-level ${LOG_LEVEL:-info}
