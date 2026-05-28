#!/bin/bash
# ============================================================
# AudioToText - Startup Script
# ============================================================
# This script reads the .env file and starts the appropriate
# Docker Compose services based on LETS_ENCRYPT_ENABLED.
#
# Usage:
#   ./start.sh              # Start with self-signed certs (default)
#   LETS_ENCRYPT_ENABLED=true ./start.sh  # Start with Let's Encrypt
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env file if it exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Ensure nginx.active.conf exists before Docker tries to mount it.
# Docker will create a directory instead of a file if the file doesn't exist,
# causing: "mount ... to etc/nginx/nginx.conf: Not a directory"
if [ ! -f nginx.active.conf ]; then
    cp nginx.conf nginx.active.conf
    echo "Created default nginx.active.conf (self-signed config)"
fi

# Determine which nginx config to use
if [ "${LETS_ENCRYPT_ENABLED:-false}" = "true" ]; then
    echo "============================================"
    echo "  Starting with Let's Encrypt SSL"
    echo "============================================"
    echo "  Domain: ${DOMAIN_NAME:-NOT SET}"
    echo ""

    if [ -z "${DOMAIN_NAME:-}" ]; then
        echo "ERROR: DOMAIN_NAME must be set in .env when LETS_ENCRYPT_ENABLED=true"
        exit 1
    fi

    # Generate nginx config with domain name substituted
    sed "s/\${DOMAIN_NAME}/$DOMAIN_NAME/g" nginx.letsencrypt.conf > nginx.active.conf

    # Start with Let's Encrypt profile
    docker compose --profile letsencrypt up -d

    echo ""
    echo "Let's Encrypt certificates will be obtained automatically."
    echo "Ensure port 80 is accessible from the internet for ACME challenges."
else
    echo "============================================"
    echo "  Starting with self-signed SSL certificate"
    echo "============================================"
    echo ""

    # Use the default nginx config
    cp nginx.conf nginx.active.conf

    # Start with self-signed profile
    docker compose --profile selfsigned up -d

    echo ""
    echo "Using self-signed certificate. For production, set:"
    echo "  LETS_ENCRYPT_ENABLED=true"
    echo "  DOMAIN_NAME=your-domain.com"
    echo "in your .env file and re-run this script."
fi
