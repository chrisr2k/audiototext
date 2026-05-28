#!/bin/bash
# ============================================================
# AudioToText - Startup Script
# ============================================================
# This script reads the .env file and starts the appropriate
# Docker Compose services based on LETS_ENCRYPT_ENABLED.
#
# The nginx container auto-detects which SSL config to use:
#   - If DOMAIN_NAME is set and LE certs exist at
#     /etc/letsencrypt/live/<DOMAIN_NAME>/, it uses Let's Encrypt.
#   - Otherwise, it falls back to self-signed certs.
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

    # Start with Let's Encrypt profile (certbot-init + certbot-renew + nginx)
    docker compose --profile letsencrypt up -d

    echo ""
    echo "Let's Encrypt certificates will be obtained automatically."
    echo "Ensure port 80 is accessible from the internet for ACME challenges."
    echo ""
    echo "The nginx container will auto-detect the LE certs and switch to"
    echo "the Let's Encrypt SSL config once certbot obtains them."
else
    echo "============================================"
    echo "  Starting with self-signed SSL certificate"
    echo "============================================"
    echo ""

    # Start with self-signed profile (ssl-init + nginx)
    docker compose --profile selfsigned up -d

    echo ""
    echo "Using self-signed certificate. For production, set:"
    echo "  LETS_ENCRYPT_ENABLED=true"
    echo "  DOMAIN_NAME=your-domain.com"
    echo "in your .env file and re-run this script."
fi
