# Ollama Chat

A desktop chat application for interacting with locally-installed Ollama models. Built with FastAPI, React, and PostgreSQL, all running in Docker containers.

## Features

- **Projects**: Organize chats into projects with custom instructions
- **Chat Management**: Create, rename, and delete conversations
- **Multiple Models**: Switch between any Ollama model installed on your machine
- **Streaming Responses**: Real-time AI responses with stop capability
- **Persistent Storage**: All chats and projects saved in PostgreSQL
- **Error Handling**: Graceful error boundaries prevent app crashes
- **Accessibility**: Full keyboard navigation and screen reader support
- **Toast Notifications**: User-friendly feedback for all actions
- **Dark Mode UI**: Clean, modern interface

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [Ollama](https://ollama.ai/) running locally with at least one model installed
- 4GB+ RAM recommended

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ollama_gui_app
   ```

2. **Create your environment file**
   ```bash
   cp .env.example .env
   ```

3. **Configure `.env`** (required):
   ```
   POSTGRES_PASSWORD=your_password_here
   ```

4. **Start the application**
   ```bash
   make dev
   ```

5. **Open the app**
   - Frontend: http://localhost:5173
   - API docs: http://localhost:8000/docs

## Configuration

Edit `.env` to customize:

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | Database username | `postgres` |
| `POSTGRES_PASSWORD` | Database password | *required* |
| `POSTGRES_DB` | Database name | `ollama_chat` |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://host.docker.internal:11434` |
| `DEFAULT_MODEL` | Default model for new chats | `qwen2.5-coder:14b` |
| `DEBUG` | Enable debug mode | `true` |

## Available Commands

```bash
make dev        # Start with hot reload (development)
make up         # Start in production mode
make down       # Stop all services
make clean      # Stop and remove all data (including database)
make test       # Run backend tests
make logs       # View container logs
make shell-db   # Open PostgreSQL shell
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│     Backend     │────▶│    PostgreSQL   │
│   React/Vite    │     │    FastAPI      │     │                 │
│   Port 5173     │     │   Port 8000     │     │   Port 5432     │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │     Ollama      │
                        │  (host machine) │
                        │   Port 11434    │
                        └─────────────────┘
```

## Usage

### Projects
1. Click **"+ Create Project"** to create a new project
2. Navigate to project settings to add custom instructions
3. Create chats within a project - they will automatically use the project's custom instructions
4. Delete projects to remove all associated chats

### Standalone Chats
1. Click **"+ New Chat"** in the header to create a standalone chat
2. Select a model from the dropdown before creating the chat
3. Standalone chats appear in the "Chats" section, separate from projects

### Keyboard Shortcuts
- `Enter`: Send message or activate focused item
- `Shift + Enter`: New line in message input
- `Tab`: Navigate between interactive elements
- `Escape`: Cancel editing (when renaming chats)

## Troubleshooting

**Ollama connection failed**
- Ensure Ollama is running: `ollama serve`
- Check that you have at least one model: `ollama list`

**Database connection error**
- Run `make clean` to reset the database
- Ensure `POSTGRES_PASSWORD` is set in `.env`

**Port already in use**
- Stop other services using ports 5173, 8000, or 5432
- Or modify the port mappings in `docker-compose.yml`

## License

MIT
