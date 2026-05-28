#!/bin/sh
# ============================================================
# AudioToText - Nginx Entrypoint
# ============================================================
# This script generates the nginx config at container startup
# based on whether Let's Encrypt certificates exist.
#
# If /etc/letsencrypt/live/<DOMAIN_NAME>/fullchain.pem exists,
# it uses the Let's Encrypt config. Otherwise, it falls back
# to the self-signed config.
# ============================================================

set -e

# Determine which config to use
if [ -n "${DOMAIN_NAME:-}" ] && [ -f "/etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem" ]; then
    echo "nginx-entrypoint: Let's Encrypt certificates found for ${DOMAIN_NAME}"
    echo "nginx-entrypoint: Using Let's Encrypt SSL config"

    # Generate config with domain name substituted
    sed "s/\${DOMAIN_NAME}/${DOMAIN_NAME}/g" /etc/nginx/nginx.letsencrypt.conf > /etc/nginx/nginx.conf
else
    echo "nginx-entrypoint: No Let's Encrypt certificates found"
    if [ -n "${DOMAIN_NAME:-}" ]; then
        echo "nginx-entrypoint:   DOMAIN_NAME=${DOMAIN_NAME}"
        echo "nginx-entrypoint:   Checked: /etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem"
    fi
    echo "nginx-entrypoint: Using self-signed SSL config"
    cp /etc/nginx/nginx.selfsigned.conf /etc/nginx/nginx.conf
fi

# Start nginx
exec nginx -g "daemon off;"
