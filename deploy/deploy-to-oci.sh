#!/bin/bash
# ============================================================
# AudioToText - Deploy to OCI Compute Instance
# ============================================================
# This script automates deployment to an OCI compute instance.
# It copies the project files, builds Docker images, and starts
# the application.
#
# Prerequisites:
#   - OCI compute instance running Ubuntu 24.04
#   - SSH key to access the instance
#   - Docker and Docker Compose installed on the instance
#
# Usage:
#   ./deploy-to-oci.sh <instance-ip> <ssh-key-path>
#
# Example:
#   ./deploy-to-oci.sh 129.146.xxx.xxx ~/.ssh/oci-key.pem
# ============================================================

set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 <instance-ip> <ssh-key-path>"
    echo "Example: $0 129.146.xxx.xxx ~/.ssh/oci-key.pem"
    exit 1
fi

INSTANCE_IP="$1"
SSH_KEY="$2"
REMOTE_USER="${3:-ubuntu}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "============================================"
echo "  Deploying AudioToText to OCI Instance"
echo "============================================"
echo "  Instance IP: $INSTANCE_IP"
echo "  SSH Key:     $SSH_KEY"
echo "  Project:     $PROJECT_DIR"
echo ""

# Step 1: Create project directory on remote instance
echo "[1/5] Creating project directory on remote instance..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$REMOTE_USER@$INSTANCE_IP" \
    "mkdir -p ~/audiototext"

# Step 2: Copy project files (excluding unnecessary files)
echo "[2/5] Copying project files..."
rsync -avz --delete \
    --exclude='.env' \
    --exclude='*.db' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='uploads/*' \
    --exclude='test_*.py' \
    --exclude='login.json' \
    -e "ssh -i $SSH_KEY" \
    "$PROJECT_DIR/" \
    "$REMOTE_USER@$INSTANCE_IP:~/audiototext/"

# Step 3: Create .env file on remote instance
echo "[3/5] Creating .env file (you'll need to edit this)..."
ssh -i "$SSH_KEY" "$REMOTE_USER@$INSTANCE_IP" \
    "cp ~/audiototext/.env.example ~/audiototext/.env"

echo ""
echo "============================================"
echo "  Files copied successfully!"
echo "============================================"
echo ""
echo "Next steps:"
echo ""
echo "1. SSH into the instance:"
echo "   ssh -i $SSH_KEY $REMOTE_USER@$INSTANCE_IP"
echo ""
echo "2. Edit the .env file with your OCI credentials:"
echo "   nano ~/audiototext/.env"
echo ""
echo "3. Start the application:"
echo "   cd ~/audiototext && docker compose up -d"
echo ""
echo "4. Check the logs:"
echo "   docker compose logs -f"
echo ""
echo "5. Access the app at:"
echo "   http://$INSTANCE_IP"
echo ""
