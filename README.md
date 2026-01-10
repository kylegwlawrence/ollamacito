# Ollama Chat

A desktop chat application for interacting with locally-installed Ollama models. Built with FastAPI, React, and PostgreSQL, all running in Docker containers.

## Features

- Chat with any Ollama model installed on your machine
- Streaming responses in real-time
- Persistent chat history stored in PostgreSQL
- Per-chat settings (temperature, max tokens, system prompt)
- Archive and manage multiple conversations
- Dark mode UI

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
