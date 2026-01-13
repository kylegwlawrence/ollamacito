# 🚀 Deployment Guide - Ollama Chat Application

## Overview

This guide covers deploying the Ollama Chat Application to a remote server with:
- **Frontend**: React/TypeScript interface
- **Backend**: FastAPI server
- **PostgreSQL**: Database for chat persistence
- **Multiple Ollama Servers**: Connect to 3+ remote Ollama instances via Tailscale

## Architecture

```
Remote Deployment Server              Ollama Servers (Tailscale Network)
┌─────────────────────┐              ┌──────────────────┐
│  Frontend (Port 80) │              │ Ollama Server 1  │
│    nginx/caddy      │              │  Tailscale URL   │
└─────────────────────┘              └──────────────────┘
┌─────────────────────┐              ┌──────────────────┐
│  Backend (Port 8000)│◄────────────►│ Ollama Server 2  │
│      FastAPI        │              │  Tailscale URL   │
└─────────────────────┘              └──────────────────┘
┌─────────────────────┐              ┌──────────────────┐
│ PostgreSQL (5432)   │              │ Ollama Server 3  │
│    Database         │              │  Tailscale URL   │
└─────────────────────┘              └──────────────────┘
```

## 📦 What's Deployed

### Frontend
- React + TypeScript single-page application
- Real-time streaming chat interface
- Server management UI
- Served via nginx in production

### Backend
- FastAPI with async support
- RESTful API with streaming endpoints
- Multi-server health monitoring
- Automatic model discovery

### PostgreSQL Database
- Chat history persistence
- Message storage
- Server configuration
- Health check logs

### Ollama Server Integration
- Connect multiple Ollama servers via Tailscale
- Automatic health monitoring
- Load balancing across servers
- Per-server model management

## 📋 Prerequisites

### Remote Deployment Server
- Ubuntu 22.04 or newer (recommended)
- Docker & Docker Compose installed
- 4GB+ RAM, 20GB+ disk space
- Public IP or domain name
- Ports 80, 443, 8000 accessible
- SSH access with sudo privileges

### Ollama Servers (3 machines)
- Ollama installed and running on each
- At least one model pulled per server
- Tailscale installed and configured
- Joined to same Tailscale network
- Each server accessible via Tailscale URL

### Local Development Machine
- SSH client
- Git installed
- Tailscale CLI (optional, for testing)

### Network Setup
- All machines on same Tailscale network
- Deployment server can reach Ollama servers via Tailscale
- Verify connectivity between all nodes

### Verify Prerequisites

On deployment server:
```bash
# Check Docker
docker --version
docker-compose --version

# Check Tailscale
sudo tailscale status

# Test connectivity to Ollama servers
curl http://TAILSCALE_IP_1:11434/api/tags
curl http://TAILSCALE_IP_2:11434/api/tags
curl http://TAILSCALE_IP_3:11434/api/tags
```

On each Ollama server:
```bash
# Check Ollama is running
ollama list
curl http://localhost:11434/api/tags

# Check Tailscale
sudo tailscale status
```

## 🚀 Deployment Steps

### Step 1: Prepare Remote Server

SSH into your deployment server:

```bash
ssh user@your-server-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker if not present
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Install Tailscale if not present
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Create project directory
mkdir -p ~/ollama_gui_app
cd ~/ollama_gui_app
```

### Step 2: Transfer Project Files

From your local machine:

```bash
# Option A: Using Git (recommended)
ssh user@your-server-ip
cd ~/ollama_gui_app
git clone https://github.com/yourusername/ollama_gui_app.git .

# Option B: Using SCP
cd /path/to/local/ollama_gui_app
scp -r * user@your-server-ip:~/ollama_gui_app/
```

### Step 3: Configure Environment

On the remote server, create `.env` file:

```bash
cd ~/ollama_gui_app
nano .env
```

Add the following configuration:

```env
# PostgreSQL Configuration
POSTGRES_DB=ollama_chat
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password_here

# Backend Configuration
DEBUG=false
LOG_LEVEL=info
DEFAULT_MODEL=qwen2.5-coder:14b

# IMPORTANT: Leave OLLAMA_BASE_URL empty for multi-server setup
# Servers are configured via the UI after deployment
OLLAMA_BASE_URL=

# Frontend Configuration
# Replace with your domain or server IP
VITE_API_URL=http://your-server-ip:8000

# CORS Configuration
# Replace with your domain or server IP
CORS_ORIGINS=http://your-server-ip,https://your-domain.com

# Secret Key (generate with: openssl rand -hex 32)
SECRET_KEY=your_generated_secret_key_here
```

### Step 4: Deploy Services

```bash
# Build and start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

Expected output:
```
NAME              STATUS      PORTS
ollama_postgres   Up          0.0.0.0:5432->5432/tcp
ollama_backend    Up          0.0.0.0:8000->8000/tcp
ollama_frontend   Up          0.0.0.0:5173->80/tcp
```

### Step 5: Configure Ollama Servers

Once the application is running, configure your Ollama servers through the UI:

1. Open browser: `http://your-server-ip:5173`
2. Navigate to Settings or Servers section
3. Add each Ollama server:

**Server 1:**
```
Name: GPU Server 1
Tailscale URL: http://100.x.x.x:11434
Description: Primary GPU server
```

**Server 2:**
```
Name: GPU Server 2
Tailscale URL: http://100.y.y.y:11434
Description: Secondary GPU server
```

**Server 3:**
```
Name: CPU Server
Tailscale URL: http://100.z.z.z:11434
Description: Fallback CPU server
```

Or configure via API:

```bash
# Add Server 1
curl -X POST http://your-server-ip:8000/api/v1/ollama-servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GPU Server 1",
    "tailscale_url": "http://100.x.x.x:11434",
    "description": "Primary GPU server",
    "is_active": true
  }'

# Add Server 2
curl -X POST http://your-server-ip:8000/api/v1/ollama-servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GPU Server 2",
    "tailscale_url": "http://100.y.y.y:11434",
    "description": "Secondary GPU server",
    "is_active": true
  }'

# Add Server 3
curl -X POST http://your-server-ip:8000/api/v1/ollama-servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CPU Server",
    "tailscale_url": "http://100.z.z.z:11434",
    "description": "Fallback CPU server",
    "is_active": true
  }'

# Verify servers
curl http://your-server-ip:8000/api/v1/ollama-servers
```

## 🧪 Testing Your Deployment

### 1. Health Check

Verify all services are running:

```bash
# Backend health
curl http://your-server-ip:8000/health

# Expected response:
# {"status":"healthy","timestamp":"2026-01-13T..."}
```

### 2. Verify Ollama Server Connectivity

```bash
# List all servers
curl http://your-server-ip:8000/api/v1/ollama-servers

# Check server health
curl http://your-server-ip:8000/api/v1/ollama-servers/health

# Expected: All servers show "online" status
```

### 3. Test Database Connection

```bash
# Check PostgreSQL
docker exec ollama_postgres pg_isready -U postgres

# Should output: "accepting connections"
```

### 4. API Documentation

Open in browser: `http://your-server-ip:8000/docs`

Test these endpoints:
- `GET /api/v1/ollama-servers` - List all servers
- `GET /api/v1/models` - List models from all servers
- `POST /api/v1/chats` - Create a test chat

### 5. Frontend Access

Open browser: `http://your-server-ip:5173`

You should see:
- Ollama Chat interface
- Sidebar with server status indicators
- "+ New Chat" button
- Theme toggle in top right

### 6. Test Chat Functionality

1. Click "+ New Chat"
2. Select a model from any of your configured servers
3. Type a message: "Hello, are you working?"
4. Press Enter or click Send
5. Verify response streams in real-time
6. Check that chat persists after page refresh

### 7. Test Multi-Server Setup

```bash
# Get models from all servers
curl http://your-server-ip:8000/api/v1/models

# You should see models from all 3 Ollama servers
# Each model will show which server it's from
```

### 8. Verify Server Failover

Test what happens when a server goes offline:

```bash
# On one Ollama server, stop the service
sudo systemctl stop ollama

# Wait 30 seconds for health check
sleep 30

# Check server status
curl http://your-server-ip:8000/api/v1/ollama-servers

# The stopped server should show "offline" status
# Other servers should still be "online"
# Chat should still work using remaining servers
```

## 🐛 Troubleshooting

### Issue: Cannot access the application from outside

**Problem**: Can't reach the application from your local machine.

**Solution**:
```bash
# Check firewall rules on server
sudo ufw status

# Allow required ports
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
sudo ufw allow 5173/tcp
sudo ufw allow 22/tcp

# Check Docker services
docker-compose ps
# All services should show "Up"
```

### Issue: Ollama servers showing "offline"

**Problem**: Configured Ollama servers appear offline in the UI.

**Solution**:
```bash
# On deployment server, test Tailscale connectivity
ping 100.x.x.x  # Replace with your Ollama server Tailscale IP

# Test Ollama API directly
curl http://100.x.x.x:11434/api/tags

# Check Tailscale status
sudo tailscale status

# On Ollama server, verify it's running
ssh user@ollama-server
ollama list
curl http://localhost:11434/api/tags

# Check Ollama service status
sudo systemctl status ollama

# Restart if needed
sudo systemctl restart ollama
```

### Issue: Backend can't connect to Ollama servers

**Problem**: Backend logs show connection errors to Ollama servers.

**Solution**:
```bash
# Check backend logs
docker-compose logs backend | grep -i ollama

# Verify Tailscale is working in Docker
docker exec ollama_backend ping 100.x.x.x

# If ping fails, check Tailscale on deployment server
sudo tailscale status
sudo tailscale up

# Verify servers are configured correctly
curl http://your-server-ip:8000/api/v1/ollama-servers

# Test direct connection from backend container
docker exec ollama_backend curl http://100.x.x.x:11434/api/tags
```

### Issue: Frontend shows connection error

**Problem**: Frontend can't communicate with backend.

**Solution**:
```bash
# Check VITE_API_URL in .env
cat .env | grep VITE_API_URL

# Should be: VITE_API_URL=http://your-server-ip:8000
# NOT localhost if accessing remotely

# Rebuild frontend with correct URL
docker-compose up -d --build frontend

# Check CORS configuration
cat .env | grep CORS_ORIGINS
# Should include your server IP or domain
```

### Issue: Database connection error

**Problem**: Backend can't connect to PostgreSQL.

**Solution**:
```bash
# Check PostgreSQL container
docker-compose ps postgres
docker-compose logs postgres

# Verify database is ready
docker exec ollama_postgres pg_isready -U postgres

# Restart if needed
docker-compose restart postgres

# Check connection from backend
docker exec -it ollama_backend psql -h postgres -U postgres -d ollama_chat

# If password error, verify .env file
cat .env | grep POSTGRES_PASSWORD
```

### Issue: Streaming not working

**Problem**: Messages appear all at once instead of streaming.

**Solution**:
```bash
# Check backend logs
docker-compose logs -f backend

# Test streaming directly
curl -N "http://your-server-ip:8000/api/v1/chats/CHAT_ID/stream?message=test"

# Verify Ollama server is responding
curl http://100.x.x.x:11434/api/generate -d '{
  "model": "qwen2.5-coder:14b",
  "prompt": "Hello",
  "stream": true
}'

# Check browser console for errors
# Open DevTools → Console → Network tab
```

### Issue: "No active Ollama servers"

**Problem**: Cannot send messages because no servers are available.

**Solution**:
```bash
# Check server status
curl http://your-server-ip:8000/api/v1/ollama-servers

# Verify at least one server is active and online
# If all offline, check Tailscale and Ollama on each server

# Manually activate a server
curl -X PATCH http://your-server-ip:8000/api/v1/ollama-servers/SERVER_ID \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}'

# Trigger health check
curl http://your-server-ip:8000/api/v1/ollama-servers/health
```

### Issue: Tailscale connectivity problems

**Problem**: Deployment server can't reach Ollama servers via Tailscale.

**Solution**:
```bash
# On deployment server, check Tailscale status
sudo tailscale status
sudo tailscale ip -4

# Verify MagicDNS is working
tailscale status | grep MagicDNS

# Test connectivity to each Ollama server
ping server1.tailnet-name.ts.net
ping server2.tailnet-name.ts.net
ping server3.tailnet-name.ts.net

# Re-authenticate if needed
sudo tailscale up --force-reauth

# Check ACLs in Tailscale admin console
# Ensure deployment server can access Ollama servers on port 11434
```

## 📊 Monitoring

### Monitor Service Health

```bash
# All Docker services
docker-compose ps

# Real-time resource usage
docker stats

# Service logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres

# Tail specific service
docker-compose logs --tail=100 -f backend
```

### Monitor Ollama Servers

```bash
# Check all server statuses
curl http://your-server-ip:8000/api/v1/ollama-servers | jq

# Get server health metrics
curl http://your-server-ip:8000/api/v1/ollama-servers/health | jq

# Monitor specific server
curl http://your-server-ip:8000/api/v1/ollama-servers/SERVER_ID | jq

# View server response times
curl http://your-server-ip:8000/api/v1/ollama-servers | jq '.servers[] | {name, status, average_response_time_ms}'
```

### Application Health Checks

```bash
# Backend health endpoint
curl http://your-server-ip:8000/health

# Database connection
docker exec ollama_postgres pg_isready -U postgres

# Check active connections
docker exec ollama_postgres psql -U postgres -d ollama_chat -c "SELECT count(*) FROM pg_stat_activity;"

# Get database size
docker exec ollama_postgres psql -U postgres -d ollama_chat -c "SELECT pg_size_pretty(pg_database_size('ollama_chat'));"
```

### Set Up Monitoring Script

Create a monitoring script on your deployment server:

```bash
nano ~/monitor_ollama.sh
```

Add the following:

```bash
#!/bin/bash

echo "=== Ollama Chat Application Monitoring ==="
echo "Date: $(date)"
echo ""

echo "--- Docker Services ---"
docker-compose -f ~/ollama_gui_app/docker-compose.yml ps
echo ""

echo "--- Resource Usage ---"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
echo ""

echo "--- Ollama Servers Status ---"
curl -s http://localhost:8000/api/v1/ollama-servers | jq -r '.servers[] | "\(.name): \(.status) - Models: \(.models_count) - Avg Response: \(.average_response_time_ms)ms"'
echo ""

echo "--- Recent Backend Errors ---"
docker-compose -f ~/ollama_gui_app/docker-compose.yml logs --tail=20 backend | grep -i error || echo "No errors found"
```

Make it executable:

```bash
chmod +x ~/monitor_ollama.sh

# Run it
~/monitor_ollama.sh

# Or add to cron for periodic checks
crontab -e
# Add: */5 * * * * ~/monitor_ollama.sh >> ~/ollama_monitor.log 2>&1
```

## 💾 Backups

### Set Up Automatic Backups

Create a backup script on your deployment server:

```bash
nano ~/backup_ollama.sh
```

Add the following:

```bash
#!/bin/bash

BACKUP_DIR=~/ollama_backups
PROJECT_DIR=~/ollama_gui_app
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
echo "Backing up database..."
docker exec ollama_postgres pg_dump -U postgres ollama_chat | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# Backup configuration
echo "Backing up configuration..."
cp $PROJECT_DIR/.env $BACKUP_DIR/env_backup_$DATE

# Remove backups older than 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
find $BACKUP_DIR -name "env_backup_*" -mtime +30 -delete

echo "Backup completed: $DATE"
```

Make it executable:

```bash
chmod +x ~/backup_ollama.sh
```

Schedule automatic backups:

```bash
crontab -e

# Add daily backup at 2 AM
0 2 * * * ~/backup_ollama.sh >> ~/backup_ollama.log 2>&1
```

### Manual Backup

```bash
# Run backup script
~/backup_ollama.sh

# Or backup directly
docker exec -t ollama_postgres pg_dump -U postgres ollama_chat | gzip > ~/backup_$(date +%Y%m%d).sql.gz

# List backups
ls -lh ~/ollama_backups/
```

### Restore from Backup

```bash
# Stop all services
cd ~/ollama_gui_app
docker-compose down

# Start only database
docker-compose up -d postgres

# Wait for database to be ready
sleep 10

# Restore from backup (adjust filename)
gunzip -c ~/ollama_backups/db_backup_20260113_020000.sql.gz | \
  docker exec -i ollama_postgres psql -U postgres -d ollama_chat

# Start all services
docker-compose up -d

# Verify
docker-compose ps
```

### Backup to Remote Storage

For production, consider backing up to remote storage:

```bash
# Install rclone for cloud backups
curl https://rclone.org/install.sh | sudo bash

# Configure rclone (follow prompts for your cloud provider)
rclone config

# Modify backup script to include cloud upload
nano ~/backup_ollama.sh

# Add at the end:
# rclone copy $BACKUP_DIR remote:ollama_backups --exclude "*.log"
```

## 🔒 Production Checklist

### Security Configuration

- [ ] Change default PostgreSQL password in `.env`
- [ ] Generate strong SECRET_KEY: `openssl rand -hex 32`
- [ ] Set `DEBUG=false` in `.env`
- [ ] Set `LOG_LEVEL=warning` or `LOG_LEVEL=error`
- [ ] Update `CORS_ORIGINS` to specific domains only (remove wildcards)
- [ ] Set up fail2ban for SSH protection
- [ ] Configure UFW firewall rules
- [ ] Keep Tailscale ACLs restrictive

### SSL/HTTPS Setup

Set up reverse proxy with SSL:

```bash
# Install nginx
sudo apt install nginx certbot python3-certbot-nginx -y

# Create nginx configuration
sudo nano /etc/nginx/sites-available/ollama_chat
```

Add configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:8000;
    }

    # Docs
    location /docs {
        proxy_pass http://localhost:8000;
    }
}
```

Enable and get SSL certificate:

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/ollama_chat /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Update .env with HTTPS URLs
nano ~/ollama_gui_app/.env
# Change VITE_API_URL=https://your-domain.com
# Change CORS_ORIGINS=https://your-domain.com

# Rebuild frontend
cd ~/ollama_gui_app
docker-compose up -d --build frontend
```

### Firewall Configuration

```bash
# Configure UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 41641/udp   # Tailscale
sudo ufw enable
```

### Monitoring and Backups

- [ ] Set up automatic backups (daily)
- [ ] Test backup restoration process
- [ ] Configure remote backup storage (S3, B2, etc.)
- [ ] Set up monitoring script (cron)
- [ ] Configure log rotation
- [ ] Set up disk space alerts
- [ ] Document recovery procedures

### Database Security

- [ ] Change PostgreSQL password
- [ ] Restrict PostgreSQL to localhost only
- [ ] Regular database maintenance
- [ ] Monitor database size

### System Hardening

- [ ] Keep system packages updated: `sudo apt update && sudo apt upgrade`
- [ ] Disable root SSH login
- [ ] Use SSH keys only (disable password auth)
- [ ] Install and configure fail2ban
- [ ] Set up automatic security updates
- [ ] Regular security audits

## 🔧 Maintenance

### Update Application

```bash
cd ~/ollama_gui_app

# Pull latest changes
git pull origin main

# Rebuild and restart services
docker-compose down
docker-compose up -d --build

# Check status
docker-compose ps
docker-compose logs -f
```

### Add Models to Ollama Servers

On each Ollama server:

```bash
# List available models
ollama list

# Pull new models
ollama pull llama3.2:3b
ollama pull mistral:7b
ollama pull codellama:13b

# Verify
ollama list
```

The backend will automatically discover new models during health checks.

### Scale Resources

If experiencing performance issues:

```bash
# Check resource usage
docker stats

# Increase Docker resources if needed
# Edit Docker daemon config
sudo nano /etc/docker/daemon.json

# Add or modify:
{
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 64000,
      "Soft": 64000
    }
  }
}

# Restart Docker
sudo systemctl restart docker
cd ~/ollama_gui_app
docker-compose up -d
```

### Database Maintenance

```bash
# Vacuum and analyze database
docker exec ollama_postgres psql -U postgres -d ollama_chat -c "VACUUM ANALYZE;"

# Check database size
docker exec ollama_postgres psql -U postgres -d ollama_chat -c "SELECT pg_size_pretty(pg_database_size('ollama_chat'));"

# Clean old messages (optional - adjust days)
docker exec ollama_postgres psql -U postgres -d ollama_chat -c "DELETE FROM messages WHERE created_at < NOW() - INTERVAL '90 days';"
```

## 🚦 Access URLs

### Without SSL (Development/Testing)

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://your-server-ip:5173 | Main chat interface |
| Backend API | http://your-server-ip:8000 | REST API |
| API Docs | http://your-server-ip:8000/docs | Interactive Swagger UI |
| Database | your-server-ip:5432 | PostgreSQL (internal) |

### With SSL (Production)

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | https://your-domain.com | Main chat interface |
| Backend API | https://your-domain.com/api | REST API |
| API Docs | https://your-domain.com/docs | Interactive Swagger UI |

## 📞 Useful Commands

### Docker Management

```bash
# Navigate to project
cd ~/ollama_gui_app

# Stop all services
docker-compose down

# Start all services
docker-compose up -d

# Restart specific service
docker-compose restart backend
docker-compose restart frontend

# View logs
docker-compose logs -f
docker-compose logs --tail=100 backend

# Rebuild after code changes
docker-compose up -d --build

# Clean everything (WARNING: deletes data!)
docker-compose down -v

# Check disk usage
docker system df

# Clean unused images/containers
docker system prune -a
```

### Service Management

```bash
# Check service status
docker-compose ps

# View resource usage
docker stats

# Enter backend container
docker exec -it ollama_backend bash

# Enter database container
docker exec -it ollama_postgres psql -U postgres -d ollama_chat

# View environment variables
docker exec ollama_backend env | grep -E 'POSTGRES|OLLAMA'
```

### Ollama Server Management

```bash
# List servers via API
curl http://your-server-ip:8000/api/v1/ollama-servers | jq

# Add server via API
curl -X POST http://your-server-ip:8000/api/v1/ollama-servers \
  -H "Content-Type: application/json" \
  -d '{"name":"New Server","tailscale_url":"http://100.x.x.x:11434","is_active":true}'

# Update server
curl -X PATCH http://your-server-ip:8000/api/v1/ollama-servers/SERVER_ID \
  -H "Content-Type: application/json" \
  -d '{"is_active":false}'

# Delete server
curl -X DELETE http://your-server-ip:8000/api/v1/ollama-servers/SERVER_ID

# Trigger health check
curl http://your-server-ip:8000/api/v1/ollama-servers/health
```

## 🎉 Success Criteria

Your deployment is successful when:

### Basic Functionality
- ✅ Frontend accessible at your server IP or domain
- ✅ Backend health check returns 200 OK
- ✅ PostgreSQL accepting connections
- ✅ All 3 Ollama servers showing "online" status

### Chat Features
- ✅ Can create a new chat
- ✅ Can select models from different servers
- ✅ Can send messages and receive responses
- ✅ Responses stream in real-time (word by word)
- ✅ Messages persist after page refresh
- ✅ Chat history displays in sidebar
- ✅ Can switch between different chats

### Multi-Server Features
- ✅ All Ollama servers listed in UI
- ✅ Can see models from each server
- ✅ Server health indicators accurate
- ✅ Failover works when server goes offline
- ✅ Can send messages to any available server

### Production Readiness (if applicable)
- ✅ HTTPS enabled with valid certificate
- ✅ Firewall configured properly
- ✅ Automatic backups running
- ✅ Monitoring script active
- ✅ Strong passwords in use
- ✅ CORS restricted to specific domains

## 🎊 Next Steps

Once deployed successfully:

1. **Add More Servers**: Scale by adding more Ollama servers via the UI
2. **Monitor Performance**: Set up monitoring dashboard with server metrics
3. **Optimize Models**: Test different models and find the best performance/quality balance
4. **Custom Configurations**: Adjust model parameters for specific use cases
5. **Team Access**: Share the application URL with your team
6. **Documentation**: Document your specific server configurations and custom settings

---

**Congratulations! Your Ollama Chat Application with multi-server support is now live!** 🚀

For issues or questions, check the troubleshooting section or review the logs with `docker-compose logs -f`.
