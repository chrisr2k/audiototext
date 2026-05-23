# AudioToText - OCI Deployment Guide

This guide covers deploying the AudioToText application to Oracle Cloud Infrastructure (OCI) using Docker containers on a compute instance.

## Architecture

```
Internet
    │
    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   OCI LB    │────▶│   Nginx     │────▶│  FastAPI    │
│ (Optional)  │     │  (Reverse   │     │   App       │
│             │     │   Proxy)    │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                      ┌────────▼──────┐
                                      │  PostgreSQL   │
                                      │   Database    │
                                      └───────────────┘

OCI Services:
  - OCI Object Storage (audio files + transcription results)
  - OCI Speech AI (transcription service)
  - OCI Container Registry (Docker images)
```

## Prerequisites

1. **OCI Account** with permissions to:
   - Create compute instances
   - Use OCI Speech AI service
   - Use OCI Object Storage
   - (Optional) Use OCI Container Registry

2. **OCI Resources** already created:
   - Object Storage bucket (for audio uploads and transcription results)
   - API signing key (for OCI SDK authentication)
   - (Optional) OCI Container Registry repository

3. **Local Tools**:
   - Docker Desktop
   - OCI CLI (`oci`)

## Quick Start (Local Testing with Docker)

```bash
# 1. Clone the repository
cd audiototext

# 2. Create .env file with your OCI credentials
cp .env.example .env
# Edit .env with your OCI credentials

# 3. Build and start with Docker Compose
docker compose up -d

# 4. Check logs
docker compose logs -f

# 5. Access the app
open http://localhost:80
```

## Deployment Options

### Option 1: OCI Compute Instance (Simple)

Deploy directly on an OCI compute instance (VM) using Docker Compose.

#### Step 1: Provision an OCI Compute Instance

Create an OCI compute instance (recommended: VM.Standard.E4.Flex with 2+ OCPUs, 16+ GB RAM):

```bash
# Using OCI CLI
oci compute instance launch \
  --compartment-id <compartment-ocid> \
  --availability-domain <ad-name> \
  --display-name audiototext-server \
  --image-id <canonical-ubuntu-24.04-image-ocid> \
  --shape VM.Standard.E4.Flex \
  --shape-config '{"ocpus":2,"memory_in_gbs":16}' \
  --subnet-id <subnet-ocid> \
  --assign-public-ip true
```

#### Step 2: Configure Security List

Add ingress rules to the VCN security list:
- Port 80 (HTTP) - from 0.0.0.0/0
- Port 443 (HTTPS) - from 0.0.0.0/0 (if using SSL)
- Port 22 (SSH) - from your IP

#### Step 3: SSH into the Instance and Deploy

```bash
# SSH into the instance
ssh -i your-key.pem ubuntu@<instance-public-ip>

# Install Docker and Docker Compose
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect

# Clone the repository
git clone <your-repo-url> audiototext
cd audiototext

# Create .env file with OCI credentials
cat > .env << 'EOF'
OCI_USER_OCID=ocid1.user.oc1..xxxxxxxxxxxx
OCI_TENANCY_OCID=ocid1.tenancy.oc1..xxxxxxxxxxxx
OCI_FINGERPRINT=xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx
OCI_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----
OCI_REGION=us-ashburn-1
OCI_NAMESPACE=your-namespace
OCI_BUCKET=your-bucket
SECRET_KEY=generate-a-random-secret-key
DEMO_MODE=false
ADMIN_EMAIL=admin@example.com
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password
POSTGRES_PASSWORD=generate-a-random-db-password
EOF

# Start the application
docker compose up -d

# Check it's running
docker compose ps
docker compose logs -f
```

### Option 2: OCI Container Registry + Compute Instance

For a more production-ready setup using OCI Container Registry.

#### Step 1: Build and Push to OCI Container Registry

```bash
# Login to OCI Container Registry
oci iam region list
# Get the region-specific registry URL (e.g., iad.ocir.io)
docker login <region>.ocir.io --username <namespace>/<username>

# Build the image
docker build -t audiototext:latest .

# Tag and push
docker tag audiototext:latest <region>.ocir.io/<namespace>/audiototext:latest
docker push <region>.ocir.io/<namespace>/audiototext:latest
```

#### Step 2: Deploy on Compute Instance

```bash
# SSH into the instance
ssh -i your-key.pem ubuntu@<instance-public-ip>

# Login to OCI Container Registry
docker login <region>.ocir.io --username <namespace>/<username>

# Create docker-compose.yml that pulls from OCI Registry
# (Modify the app service to use the registry image instead of building locally)

# Start the application
docker compose up -d
```

### Option 3: OCI Container Instances (Serverless Containers)

OCI Container Instances is a serverless compute service that runs containers without managing VMs.

```bash
# Create a container instance using OCI CLI
oci container-instances container-instance create \
  --compartment-id <compartment-ocid> \
  --display-name audiototext-instance \
  --availability-domain <ad-name> \
  --shape-config '{"ocpus":2,"memory_in_gbs":8}' \
  --containers '[
    {
      "displayName": "audiototext",
      "imageUrl": "<region>.ocir.io/<namespace>/audiototext:latest",
      "environmentVariables": {
        "DATABASE_URL": "postgresql://user:password@host:5432/audiototext",
        "OCI_USER_OCID": "...",
        "OCI_TENANCY_OCID": "...",
        "OCI_FINGERPRINT": "...",
        "OCI_PRIVATE_KEY": "...",
        "OCI_REGION": "us-ashburn-1",
        "OCI_NAMESPACE": "...",
        "OCI_BUCKET": "...",
        "SECRET_KEY": "...",
        "DEMO_MODE": "false",
        "ADMIN_EMAIL": "admin@example.com",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "..."
      },
      "isResourcePrincipalDisabled": true,
      "healthChecks": [{
        "healthCheckType": "HTTP",
        "path": "/health",
        "port": 8000,
        "failureThreshold": 3,
        "successThreshold": 1,
        "intervalInSeconds": 30
      }]
    }
  ]' \
  --vnicts '[
    {
      "displayName": "primary-vnic",
      "subnetId": "<subnet-ocid>",
      "isPublicIpAssigned": true
    }
  ]'
```

## SSL/HTTPS Setup

### Using Let's Encrypt with Certbot

```bash
# SSH into the instance
ssh -i your-key.pem ubuntu@<instance-public-ip>

# Install certbot
sudo apt install -y certbot

# Get SSL certificate
sudo certbot certonly --standalone -d your-domain.com

# Update nginx.conf to uncomment the HTTPS server block
# and point to your certificate paths

# Restart nginx
docker compose restart nginx

# Set up auto-renewal
sudo crontab -e
# Add: 0 3 * * * certbot renew --quiet && docker compose restart nginx
```

### Using OCI Load Balancer with SSL

1. Create an OCI Load Balancer
2. Upload your SSL certificate to the load balancer
3. Configure the listener on port 443 with SSL
4. Point the backend set to port 80 on your compute instance
5. Update nginx.conf to trust the X-Forwarded-Proto header

## Database Backups

### Automated PostgreSQL Backup

```bash
# Create a backup script
cat > /home/ubuntu/backup-db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/home/ubuntu/db-backups
mkdir -p $BACKUP_DIR
docker compose exec -T db pg_dump -U audiototext audiototext > \
  $BACKUP_DIR/audiototext-$(date +%Y%m%d-%H%M%S).sql
# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
EOF

chmod +x /home/ubuntu/backup-db.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /home/ubuntu/backup-db.sh") | crontab -
```

## Monitoring

### Health Check

The app exposes a `/health` endpoint:
```bash
curl http://localhost/health
# Returns: {"status":"healthy","demo_mode":false,"oci_configured":true}
```

### Docker Container Monitoring

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f --tail=100

# Check resource usage
docker stats
```

### OCI Monitoring

Set up OCI Monitoring alerts for:
- CPU utilization > 80%
- Memory utilization > 80%
- Disk space > 80%

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs app

# Check if PostgreSQL is healthy
docker compose logs db

# Verify environment variables
docker compose exec app env | grep -E "OCI|DATABASE|SECRET"
```

### OCI Speech API errors

```bash
# Check OCI credentials are correct
docker compose exec app python -c "
from app.config import settings
print('User OCID:', settings.OCI_USER_OCID[:20] + '...')
print('Tenancy:', settings.OCI_TENANCY_OCID[:20] + '...')
print('Region:', settings.OCI_REGION)
print('Key exists:', bool(settings.OCI_PRIVATE_KEY_PATH))
"

# Test OCI connectivity
docker compose exec app python -c "
from app.services.oci_speech import _get_speech_client
client = _get_speech_client()
print('OCI Speech client created successfully')
"
```

### Database connection issues

```bash
# Test database connection
docker compose exec app python -c "
from app.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('Database connected:', result.scalar())
"
```

## Updating the Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker compose up -d --build

# Check for any issues
docker compose logs -f
```

## Cleanup

```bash
# Stop all containers
docker compose down

# Remove volumes (WARNING: deletes all data)
docker compose down -v

# Remove images
docker rmi audiototext-app
```
