# Note 3: Docker Compose for Multi-Service Development

## What Docker Compose Solves

Your Research Assistant isn't just a Python application. It's a system:

```
┌─────────────────────────────────────────────────────────────┐
│                   RESEARCH ASSISTANT STACK                   │
│                                                              │
│  ┌─────────────────┐                                         │
│  │  FastAPI App    │ ← Your code                            │
│  │  (Port 8000)    │                                         │
│  └────────┬────────┘                                         │
│           │                                                  │
│     ┌─────┴─────┐                                            │
│     ▼           ▼                                            │
│  ┌──────────┐  ┌──────────┐                                  │
│  │  Redis   │  │  Qdrant  │  ← External services             │
│  │  (6379)  │  │  (6333)  │                                  │
│  └──────────┘  └──────────┘                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

Without Compose, starting this requires:

```bash
# Terminal 1
docker run -d --name redis -p 6379:6379 redis:7

# Terminal 2
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant

# Terminal 3
docker run -d --name research-assistant \
  -p 8000:8000 \
  -e REDIS_HOST=redis \
  -e QDRANT_HOST=qdrant \
  --link redis --link qdrant \
  research-assistant:v1.0

# And you need to remember all this, every time, in the right order
```

With Compose:

```bash
docker compose up
```

That's it. One command. Every time.

### What Compose Provides

|Problem|Compose Solution|
|---|---|
|Multiple containers to start|`docker compose up` starts everything|
|Configuration scattered across commands|Single `compose.yaml` file|
|Port mappings, volumes, env vars|Declared once, used always|
|Container networking|Automatic DNS between services|
|Startup order|`depends_on` with health checks|
|Environment consistency|Same config for all team members|

---

## Compose File Anatomy

A Compose file is YAML that declares your entire application stack.

### Modern Compose (No Version Required)

As of Docker Compose v1.27.0+, the `version` field is **optional and ignored**. Modern Compose uses the Compose Specification, which auto-detects features based on your configuration.

```yaml
# compose.yaml (preferred filename, also accepts docker-compose.yml)

services:        # Container definitions (required)
  app:
    # ... service config
  redis:
    # ... service config

volumes:         # Persistent storage definitions (optional)
  app_data:

networks:        # Custom network definitions (optional)
  backend:
```

### Top-Level Elements

|Element|Purpose|Required?|
|---|---|---|
|`services`|Define containers|Yes|
|`volumes`|Define named volumes|Optional|
|`networks`|Define custom networks|Optional|
|`configs`|External configuration|Optional|
|`secrets`|Sensitive data|Optional|

---

## Service Configuration

Each service under `services:` defines how to run a container.

### Core Service Options

```yaml
services:
  research-assistant:
    # ─────────────────────────────────────────────────
    # IMAGE SOURCE (choose one)
    # ─────────────────────────────────────────────────
    
    # Option A: Build from Dockerfile
    build:
      context: .              # Build context directory
      dockerfile: Dockerfile  # Dockerfile path (default: Dockerfile)
      target: runtime         # Multi-stage build target (optional)
    
    # Option B: Use existing image
    image: myregistry/research-assistant:v1.0
    
    # Option C: Both (build and tag)
    build: .
    image: research-assistant:latest
    
    # ─────────────────────────────────────────────────
    # PORT MAPPING
    # ─────────────────────────────────────────────────
    ports:
      - "8000:8000"           # HOST:CONTAINER
      - "8001:8001"           # Multiple ports allowed
    
    # ─────────────────────────────────────────────────
    # ENVIRONMENT VARIABLES
    # ─────────────────────────────────────────────────
    environment:
      APP_ENV: development
      LOG_LEVEL: debug
      # Reference from .env file
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    
    # ─────────────────────────────────────────────────
    # VOLUMES (persistent storage)
    # ─────────────────────────────────────────────────
    volumes:
      - ./data:/app/data             # Bind mount: host path → container
      - app_logs:/app/logs           # Named volume
      - ./config:/app/config:ro      # Read-only mount
    
    # ─────────────────────────────────────────────────
    # DEPENDENCIES
    # ─────────────────────────────────────────────────
    depends_on:
      redis:
        condition: service_healthy   # Wait for health check
      qdrant:
        condition: service_started   # Just wait for container start
    
    # ─────────────────────────────────────────────────
    # HEALTH CHECK
    # ─────────────────────────────────────────────────
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    
    # ─────────────────────────────────────────────────
    # RESOURCE LIMITS (optional)
    # ─────────────────────────────────────────────────
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
    
    # ─────────────────────────────────────────────────
    # RESTART POLICY
    # ─────────────────────────────────────────────────
    restart: unless-stopped
```

### Service Configuration Reference

|Option|Purpose|Example|
|---|---|---|
|`build`|Build from Dockerfile|`build: .` or `build: {context: ., dockerfile: Dockerfile.prod}`|
|`image`|Use existing image|`image: redis:7-alpine`|
|`ports`|Port mapping|`- "8000:8000"`|
|`environment`|Environment variables|`APP_ENV: production`|
|`volumes`|Mount storage|`- ./data:/app/data`|
|`depends_on`|Startup order|`depends_on: [redis, db]`|
|`healthcheck`|Container health monitoring|See below|
|`restart`|Restart policy|`no`, `always`, `on-failure`, `unless-stopped`|
|`command`|Override CMD|`command: ["python", "worker.py"]`|
|`entrypoint`|Override ENTRYPOINT|`entrypoint: ["/entrypoint.sh"]`|
|`working_dir`|Override WORKDIR|`working_dir: /app/src`|

---

## depends_on and Health Checks

The `depends_on` option controls startup order, but by default it only waits for the container to **start**, not for the service to be **ready**.

### The Problem

```yaml
# BAD: App starts before database is ready
services:
  app:
    depends_on:
      - db        # Only waits for container to start, not for PostgreSQL to accept connections
  db:
    image: postgres:16
```

Your app crashes with "connection refused" because PostgreSQL needs 5-10 seconds to initialize.

### The Solution: Health Check Conditions

```yaml
# GOOD: App waits for database to be healthy
services:
  app:
    depends_on:
      db:
        condition: service_healthy    # Waits for health check to pass
  
  db:
    image: postgres:16
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
```

### Health Check Options

|Option|Purpose|Example|
|---|---|---|
|`test`|Command to run|`["CMD", "curl", "-f", "http://localhost/health"]`|
|`interval`|Time between checks|`30s`|
|`timeout`|Max time for check to complete|`10s`|
|`retries`|Failures before unhealthy|`3`|
|`start_period`|Grace period before counting failures|`40s`|

### Dependency Conditions

|Condition|Behavior|
|---|---|
|`service_started`|Wait for container to start (default)|
|`service_healthy`|Wait for health check to pass|
|`service_completed_successfully`|Wait for container to exit with code 0|

### Common Health Check Commands

```yaml
# Redis
redis:
  image: redis:7
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 5s
    retries: 5

# PostgreSQL
postgres:
  image: postgres:16
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 30s

# FastAPI / HTTP service
app:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s

# If curl not installed, use Python
app:
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
    interval: 30s
    timeout: 10s
    retries: 3
```

---

## Typical AI Application Stack

Here's a complete `compose.yaml` for a Research Assistant with Redis (caching) and Qdrant (vector DB):

```yaml
# compose.yaml
# Research Assistant - Local Development Stack
# Docs: https://docs.docker.com/compose/

services:
  # ═══════════════════════════════════════════════════════════
  # MAIN APPLICATION
  # ═══════════════════════════════════════════════════════════
  research-assistant:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=development
      - LOG_LEVEL=debug
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      # Secrets from .env file (not committed to git)
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      # Persist data directory
      - ./data:/app/data
      # Live reload: mount source code (development only)
      - ./src:/app/src
    depends_on:
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped

  # ═══════════════════════════════════════════════════════════
  # REDIS - Caching, Rate Limiting, Session Storage
  # ═══════════════════════════════════════════════════════════
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # ═══════════════════════════════════════════════════════════
  # QDRANT - Vector Database
  # ═══════════════════════════════════════════════════════════
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"    # REST API
      - "6334:6334"    # gRPC
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    restart: unless-stopped

# ═══════════════════════════════════════════════════════════
# NAMED VOLUMES - Managed by Docker
# ═══════════════════════════════════════════════════════════
volumes:
  redis_data:
  qdrant_data:
```

### Directory Structure

```
research-assistant/
├── compose.yaml           # Docker Compose configuration
├── Dockerfile             # Application image definition
├── .env                   # Secrets (NOT in git)
├── .env.example           # Template for .env
├── .dockerignore          # Exclude from build context
├── requirements.txt
├── src/
│   ├── main.py
│   └── ...
├── data/                  # Persisted via bind mount
└── config/
```

---

## Environment Variables in Compose

Three ways to set environment variables:

### 1. Inline in compose.yaml

```yaml
services:
  app:
    environment:
      APP_ENV: development
      LOG_LEVEL: debug
      # Or list syntax
      - APP_ENV=development
      - LOG_LEVEL=debug
```

### 2. From .env File (Variable Substitution)

Compose automatically reads `.env` in the same directory:

```bash
# .env (NOT committed to git)
OPENAI_API_KEY=sk-abc123...
ANTHROPIC_API_KEY=sk-ant-abc123...
POSTGRES_PASSWORD=supersecret
```

```yaml
# compose.yaml
services:
  app:
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      # With default value
      LOG_LEVEL: ${LOG_LEVEL:-info}
```

### 3. From External env_file

```yaml
services:
  app:
    env_file:
      - .env
      - .env.local    # Overrides .env
```

### Variable Substitution Syntax

|Syntax|Behavior|
|---|---|
|`${VAR}`|Use value, error if unset|
|`${VAR:-default}`|Use default if unset or empty|
|`${VAR-default}`|Use default only if unset|
|`${VAR:?error}`|Error with message if unset|

### Best Practice: .env.example

Create a template that IS committed to git:

```bash
# .env.example
# Copy to .env and fill in values
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
```

Add `.env` to `.gitignore`:

```gitignore
# .gitignore
.env
.env.local
.env.*.local
```

---

## Volume Patterns

Two types of volumes serve different purposes:

### Bind Mounts: Host Directory → Container

```yaml
volumes:
  # Syntax: HOST_PATH:CONTAINER_PATH[:OPTIONS]
  - ./data:/app/data              # Read-write (default)
  - ./config:/app/config:ro       # Read-only
  - ./src:/app/src                # Live code reload
```

**When to use:**

- Development: Live code changes without rebuild
- Data you want easy access to from host
- Config files you edit locally

**Characteristics:**

- Path on host must exist
- Full control over location
- Easy to inspect/backup from host

### Named Volumes: Docker-Managed Storage

```yaml
services:
  db:
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:    # Defined at top level
```

**When to use:**

- Database storage (PostgreSQL, Redis, Qdrant)
- Production deployments
- Data that doesn't need direct host access

**Characteristics:**

- Docker manages location (`/var/lib/docker/volumes/...`)
- Portable across environments
- Persists across `docker compose down` (unless `-v` flag)

### Comparison

|Aspect|Bind Mount|Named Volume|
|---|---|---|
|Location|You specify|Docker manages|
|Host access|Direct|Via `docker volume` commands|
|Portability|Tied to host paths|Works anywhere|
|Performance|Same as host|Slightly better on Mac/Windows|
|Use case|Development, config|Databases, production|

---

## Common Commands

```bash
# ─────────────────────────────────────────────────────────────
# STARTING SERVICES
# ─────────────────────────────────────────────────────────────

# Start all services (attached, logs in terminal)
docker compose up

# Start in background (detached)
docker compose up -d

# Start specific service(s)
docker compose up redis qdrant

# Rebuild images before starting
docker compose up --build

# Force recreate containers
docker compose up --force-recreate


# ─────────────────────────────────────────────────────────────
# STOPPING SERVICES
# ─────────────────────────────────────────────────────────────

# Stop all services (containers remain)
docker compose stop

# Stop and remove containers, networks
docker compose down

# Stop and remove EVERYTHING including volumes (data loss!)
docker compose down -v


# ─────────────────────────────────────────────────────────────
# VIEWING STATUS
# ─────────────────────────────────────────────────────────────

# List running services
docker compose ps

# View logs (all services)
docker compose logs

# Follow logs (stream)
docker compose logs -f

# Logs for specific service
docker compose logs -f research-assistant


# ─────────────────────────────────────────────────────────────
# BUILDING
# ─────────────────────────────────────────────────────────────

# Build images
docker compose build

# Build without cache
docker compose build --no-cache

# Build specific service
docker compose build research-assistant


# ─────────────────────────────────────────────────────────────
# EXECUTING COMMANDS
# ─────────────────────────────────────────────────────────────

# Run command in running container
docker compose exec research-assistant python -c "print('hello')"

# Open shell in running container
docker compose exec research-assistant bash

# Run one-off command (creates new container)
docker compose run --rm research-assistant pytest


# ─────────────────────────────────────────────────────────────
# HEALTH AND DEBUGGING
# ─────────────────────────────────────────────────────────────

# Check container health status
docker inspect --format='{{json .State.Health}}' <container_id> | jq

# View Docker events (health status changes)
docker events --filter 'event=health_status'
```

---

## Development vs Production Compose Files

Use multiple Compose files to separate concerns.

### Strategy: Base + Override

```
compose.yaml              # Base configuration (always applied)
compose.override.yaml     # Development additions (auto-applied)
compose.prod.yaml         # Production overrides (explicit)
```

### Base: compose.yaml

```yaml
# compose.yaml - Shared configuration
services:
  research-assistant:
    build: .
    environment:
      - REDIS_HOST=redis
      - QDRANT_HOST=qdrant
    depends_on:
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

  qdrant:
    image: qdrant/qdrant:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s

volumes:
  redis_data:
  qdrant_data:
```

### Development Override: compose.override.yaml

```yaml
# compose.override.yaml - Development additions
# Automatically merged when running `docker compose up`

services:
  research-assistant:
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=development
      - LOG_LEVEL=debug
    volumes:
      # Live code reload
      - ./src:/app/src
      - ./data:/app/data

  redis:
    ports:
      - "6379:6379"

  qdrant:
    ports:
      - "6333:6333"
      - "6334:6334"
```

### Production Override: compose.prod.yaml

```yaml
# compose.prod.yaml - Production overrides
# Applied with: docker compose -f compose.yaml -f compose.prod.yaml up

services:
  research-assistant:
    image: myregistry/research-assistant:${VERSION:-latest}
    environment:
      - APP_ENV=production
      - LOG_LEVEL=warning
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
    # No source code mounts in production

  redis:
    # No port exposure to host in production

  qdrant:
    # No port exposure to host in production
```

### Running with Overrides

```bash
# Development (compose.yaml + compose.override.yaml auto-merged)
docker compose up

# Production (explicit file selection)
docker compose -f compose.yaml -f compose.prod.yaml up -d

# Staging
docker compose -f compose.yaml -f compose.staging.yaml up -d
```

### Merge Behavior

When using multiple files, values are merged:

- **Lists** (ports, volumes): Combined
- **Scalars** (image, command): Later file wins
- **Maps** (environment): Merged, later wins for same key

---

## Quick Reference

### Minimal Compose File

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
```

### With Dependencies

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - redis
  redis:
    image: redis:7-alpine
```

### With Health Checks

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      redis:
        condition: service_healthy
  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
```

### With Volumes and Environment

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_HOST=redis
      - API_KEY=${API_KEY}
    volumes:
      - ./data:/app/data
      - app_logs:/app/logs
    depends_on:
      redis:
        condition: service_healthy
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

volumes:
  app_logs:
  redis_data:
```

---

## Docs Referenced

- Docker Compose Specification: https://docs.docker.com/compose/
- Service configuration: https://docs.docker.com/reference/compose-file/services/
- Startup order and depends_on: https://docs.docker.com/compose/how-tos/startup-order/
- Compose versioning history: https://docs.docker.com/compose/intro/history/

---

## What's Next

This note covered Docker Compose for local multi-service development. The next note covers **Cloud Deployment Options** — choosing where to host your containerized AI application and understanding the trade-offs.