# 🚀 Deployment Guide - Ollama Chat Application

## ✅ Phase 3 Complete!

Your full-stack Ollama Chat Application is now ready to deploy.

## 📦 What's Included

### Backend (100% Complete)
- ✅ FastAPI with async support
- ✅ Real-time streaming via Server-Sent Events
- ✅ PostgreSQL database with migrations
- ✅ Complete API with 20+ endpoints
- ✅ Automated backups
- ✅ Docker configuration

### Frontend (100% Complete)
- ✅ React + TypeScript + Vite
- ✅ Real-time streaming chat interface
- ✅ Dark/light theme with CSS variables
- ✅ Responsive sidebar with chat history
- ✅ Markdown message rendering
- ✅ Docker configuration

## 🎯 Quick Start

```bash
# 1. Navigate to the project
cd /path/to/ollama_gui_app

# 2. Create .env file (copy from .env.example and update as needed)
cp .env.example .env

# 3. Start all services
make dev

# 4. Watch the logs
docker-compose logs -f

# 5. Open in browser
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/docs
```

That's it! 🎉

## 📋 Prerequisites

### Local Machine Requirements:
- ✅ Docker & Docker Compose installed
- ✅ Ollama installed and running (`ollama serve`)
- ✅ At least one Ollama model pulled
- ✅ 4GB+ RAM recommended

### Verify Prerequisites:

```bash
# Check Docker
docker --version
docker-compose --version

# Check Ollama
ollama list
curl http://localhost:11434/api/tags

# Check available models
ollama list
```

## 🔧 Configuration

### Create .env File

Copy from `.env.example` and customize:

```env
# PostgreSQL
POSTGRES_DB=ollama_chat
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password

# Backend
DEBUG=false
LOG_LEVEL=info

# Ollama (running locally outside Docker)
OLLAMA_BASE_URL=http://host.docker.internal:11434
DEFAULT_MODEL=qwen2.5-coder:14b

# Frontend
VITE_API_URL=http://localhost:8000

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Start Services

```bash
# Development mode (with hot reload)
make dev

# Or production mode
make up

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## 🧪 Testing Your Deployment

### 1. Backend Health Check

```bash
curl http://localhost:8000/health
```

### 2. Check Ollama Connection

```bash
curl http://localhost:8000/api/v1/ollama/status
```

### 3. API Documentation

Open: `http://localhost:8000/docs`

Try the interactive Swagger UI to test endpoints.

### 4. Frontend Access

Open browser: `http://localhost:5173`

You should see:
- Sidebar with "Ollama Chat" title
- "+ New Chat" button
- Theme toggle (☀️/🌙) in top right
- Empty state message

### 5. Create First Chat

1. Click "+ New Chat"
2. Type a message in the input box
3. Press Enter or click "Send"
4. Watch the response stream in real-time!

## 🐛 Troubleshooting

### Issue: Cannot access the application

**Solution: Check Docker Services**
```bash
docker-compose ps
# All services should be "Up"

docker-compose logs -f
# Check for any errors
```

### Issue: Backend can't connect to Ollama

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# If not running
pkill ollama
ollama serve &

# Check logs
docker-compose logs backend | grep -i ollama
```

### Issue: Frontend shows connection error

```bash
# Check VITE_API_URL in .env
cat .env | grep VITE_API_URL

# Should be: VITE_API_URL=http://localhost:8000

# Rebuild frontend if changed
docker-compose up -d --build frontend
```

### Issue: Streaming not working

```bash
# Check backend logs
docker-compose logs -f backend

# Try direct streaming test
curl "http://localhost:8000/api/v1/chats/CHAT_ID/stream?message=test"

# Check browser console for errors
# Open DevTools → Console
```

### Issue: Database connection error

```bash
# Check PostgreSQL
docker-compose ps postgres
docker-compose logs postgres

# Restart if needed
docker-compose restart postgres

# Check connection from backend
docker exec -it ollama_backend psql -h postgres -U postgres -d ollama_chat
```

## 📊 Monitoring

### Check Service Status

```bash
# All services
docker-compose ps

# Resource usage
docker stats

# Logs for specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
```

### Check Application Health

```bash
# Backend health
curl http://YOUR_IP:8000/health

# Database connection
docker exec ollama_postgres pg_isready -U postgres

# Ollama status
curl http://YOUR_IP:8000/api/v1/ollama/status
```

## 💾 Backups

### Automatic Backups

Backups run daily at 2 AM automatically. Check:

```bash
ls -lh backups/
```

### Manual Backup

```bash
# Create backup
make backup

# Or directly
docker exec -t ollama_postgres pg_dump -U postgres ollama_chat > backups/manual_backup_$(date +%Y%m%d).sql
```

### Restore from Backup

```bash
# Stop services
docker-compose down

# Start only database
docker-compose up -d postgres

# Restore
docker exec -i ollama_postgres psql -U postgres -d ollama_chat < backups/backup_file.sql

# Start all services
docker-compose up -d
```

## 🔒 Production Checklist

Before using in production:

- [ ] Change default passwords in `.env`
- [ ] Generate strong SECRET_KEY: `openssl rand -hex 32`
- [ ] Set `DEBUG=false`
- [ ] Set `LOG_LEVEL=warning`
- [ ] Configure HTTPS (nginx reverse proxy + Let's Encrypt)
- [ ] Restrict CORS to specific domains only
- [ ] Set up regular backup monitoring
- [ ] Configure firewall rules (only allow specific IPs if possible)
- [ ] Consider VPN for remote access
- [ ] Enable log rotation
- [ ] Set up monitoring/alerting

## 🎨 Customization

### Change Default Model

Edit `.env`:
```env
DEFAULT_MODEL=your-preferred-model
```

Then restart:
```bash
docker-compose restart backend
```

### Adjust Theme Colors

Edit `frontend/src/styles/theme.css` to customize colors.

### Add More Models

```bash
# Pull new model
ollama pull mistral:7b

# Restart to refresh model list
docker-compose restart backend
```

## 🚦 Access URLs

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:5173 | Main chat interface |
| Backend API | http://localhost:8000 | REST API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Database | localhost:5432 | PostgreSQL |

## 📞 Support

### Useful Commands

```bash
# View all commands
make help

# Stop everything
docker-compose down

# Clean everything (including data!)
docker-compose down -v

# Restart a service
docker-compose restart backend

# Rebuild after code changes
docker-compose up -d --build

# View real-time logs
docker-compose logs -f

# Check disk usage
docker system df
```

### Common Issues

1. **"Cannot connect to Docker daemon"**
   - Start Docker Desktop
   - Wait for it to fully initialize

2. **"Port already in use"**
   - Change ports in `docker-compose.yml`
   - Or stop conflicting service

3. **"Out of memory"**
   - Increase Docker memory limit
   - Close other applications
   - Use smaller Ollama models

4. **"Slow performance"**
   - Use faster Ollama model (smaller size)
   - Increase Docker CPU allocation
   - Check system resources: `docker stats`

## 🎉 Success Criteria

Your deployment is successful when:

✅ You can access frontend at `http://YOUR_IP:5173`
✅ Theme toggle works (sun/moon icon)
✅ You can create a new chat
✅ You can send a message
✅ Response streams in real-time (not all at once)
✅ Messages persist after page refresh
✅ Chat history shows in sidebar
✅ Can switch between chats

Congratulations! Your Ollama Chat Application is live! 🚀
