# Note 2: Writing Dockerfiles for Python AI Applications

## Dockerfile Instruction Reference

A Dockerfile is a text file containing instructions to build a Docker image. Each instruction creates a layer.

```dockerfile
# Comments start with #
INSTRUCTION arguments
```

### Core Instructions

|Instruction|Purpose|Example|
|---|---|---|
|`FROM`|Set base image|`FROM python:3.11-slim`|
|`WORKDIR`|Set working directory|`WORKDIR /app`|
|`COPY`|Copy files into image|`COPY requirements.txt .`|
|`RUN`|Execute command (build time)|`RUN pip install -r requirements.txt`|
|`ENV`|Set environment variable|`ENV PYTHONUNBUFFERED=1`|
|`EXPOSE`|Document exposed port|`EXPOSE 8000`|
|`CMD`|Default command (runtime)|`CMD ["python", "main.py"]`|
|`ENTRYPOINT`|Fixed command prefix|`ENTRYPOINT ["python"]`|
|`ARG`|Build-time variable|`ARG PYTHON_VERSION=3.11`|
|`USER`|Set user for subsequent commands|`USER appuser`|

### Instruction Details

**FROM — Base Image Selection**

```dockerfile
# Start from an existing image
FROM python:3.11-slim

# Pin to specific digest for reproducibility (production)
FROM python:3.11-slim@sha256:abc123...

# Multi-stage: name the stage
FROM python:3.11-slim AS builder
```

**WORKDIR — Set Working Directory**

```dockerfile
# Creates directory if it doesn't exist
# All subsequent commands run from here
WORKDIR /app

# Relative paths are relative to WORKDIR
COPY . .  # Copies to /app/
```

**COPY — Copy Files Into Image**

```dockerfile
# Copy single file
COPY requirements.txt .

# Copy directory
COPY src/ ./src/

# Copy multiple files
COPY requirements.txt pyproject.toml ./

# Copy with ownership (avoids extra chown layer)
COPY --chown=appuser:appgroup src/ ./src/
```

**RUN — Execute Commands at Build Time**

```dockerfile
# Shell form (uses /bin/sh -c)
RUN pip install -r requirements.txt

# Exec form (no shell)
RUN ["pip", "install", "-r", "requirements.txt"]

# Combine commands to reduce layers
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    pip install -r requirements.txt && \
    apt-get purge -y gcc && \
    rm -rf /var/lib/apt/lists/*
```

**ENV — Set Environment Variables**

```dockerfile
# Set single variable
ENV PYTHONUNBUFFERED=1

# Set multiple (modern syntax)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production
```

**EXPOSE — Document Ports**

```dockerfile
# Documentation only — doesn't actually publish the port
# Port must be published at runtime with -p flag
EXPOSE 8000
EXPOSE 8000/tcp 8001/udp
```

**CMD vs ENTRYPOINT**

This distinction matters for how your container starts:

```dockerfile
# CMD — Default command, can be overridden at runtime
CMD ["python", "main.py"]

# Running: docker run myimage           → python main.py
# Running: docker run myimage bash      → bash (CMD overridden)


# ENTRYPOINT — Fixed prefix, CMD becomes arguments
ENTRYPOINT ["python"]
CMD ["main.py"]

# Running: docker run myimage           → python main.py
# Running: docker run myimage other.py  → python other.py
# Running: docker run myimage bash      → python bash (probably not what you want)
```

**When to use which:**

|Pattern|Use Case|
|---|---|
|`CMD` only|General purpose, flexible|
|`ENTRYPOINT` + `CMD`|CLI tools where you want fixed executable but flexible args|
|`ENTRYPOINT` only|Strict execution, no flexibility|

For most AI applications, **`CMD` only** is the right choice:

```dockerfile
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Base Image Selection for Python

Choosing the right base image significantly impacts image size, build time, and compatibility.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PYTHON BASE IMAGE OPTIONS                             │
│                                                                          │
│  python:3.11          ~900MB   Full Debian + dev tools                  │
│  ───────────────────────────────────────────────────────────            │
│  python:3.11-slim     ~150MB   Minimal Debian, no dev tools             │
│  ───────────────────────────────────────────────────────────            │
│  python:3.11-alpine    ~50MB   Alpine Linux, smallest                   │
│                                                                          │
│  RECOMMENDATION: Start with -slim                                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Comparison

|Image|Size|Pros|Cons|
|---|---|---|---|
|`python:3.11`|~900MB|Everything included, easy to use|Large, slow to pull, bigger attack surface|
|`python:3.11-slim`|~150MB|Good balance, most packages work|Need to install some dev tools for compilation|
|`python:3.11-alpine`|~50MB|Tiny, fast pulls|Uses musl libc — compatibility issues with numpy, pandas, etc.|

### Alpine Compatibility Warning

Alpine uses `musl` libc instead of `glibc`. Many Python packages with C extensions (numpy, pandas, scipy, most ML libraries) either:

- Won't install at all
- Require manual compilation (slow, complex)
- Have subtle runtime bugs

**For AI applications, avoid Alpine.** The size savings aren't worth the compatibility headaches.

### Recommended Base Image Strategy

**Development / Default:**

```dockerfile
FROM python:3.11-slim
```

**Production with maximum control:**

```dockerfile
# Pin to specific Debian release and digest
FROM python:3.11-slim-bookworm@sha256:abc123...
```

**If you need system packages compiled:**

```dockerfile
# Multi-stage: build in full image, run in slim
FROM python:3.11 AS builder
# ... compile things ...

FROM python:3.11-slim AS runtime
# ... copy compiled artifacts ...
```

### Python Version Considerations

|Version|Status (as of 2026)|Recommendation|
|---|---|---|
|3.9|Security fixes only|Upgrade if possible|
|3.10|Security fixes only|Acceptable|
|3.11|Active|Good default|
|3.12|Active|Good, some packages may lag|
|3.13+|Latest|Check dependency compatibility|

**For AI applications:** 3.11 is the sweet spot — mature, fast, excellent library support.

---

## Layer Ordering for Cache Efficiency

The single most impactful optimization for build speed.

### The Problem

```dockerfile
# BAD: Any code change invalidates pip install cache
FROM python:3.11-slim
WORKDIR /app
COPY . .                              # Copies everything
RUN pip install -r requirements.txt   # Runs EVERY build

# Result: Change one line of Python → reinstall ALL packages (5-10 minutes)
```

### The Solution

```dockerfile
# GOOD: Dependencies cached separately from code
FROM python:3.11-slim
WORKDIR /app

# 1. Copy ONLY dependency specification
COPY requirements.txt .

# 2. Install dependencies (cached unless requirements.txt changes)
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy application code LAST
COPY src/ ./src/
COPY config/ ./config/

# Result: Change one line of Python → only copy new code (seconds)
```

### Why This Works

```
BUILD 1 (Initial):
Layer 1: FROM python:3.11-slim        ✓ Downloaded
Layer 2: WORKDIR /app                  ✓ Created
Layer 3: COPY requirements.txt         ✓ Copied
Layer 4: RUN pip install               ✓ Installed (5 min)
Layer 5: COPY src/                     ✓ Copied
─────────────────────────────────────────────────────
Total: 5 minutes

BUILD 2 (Changed main.py):
Layer 1: FROM python:3.11-slim        ✓ CACHED
Layer 2: WORKDIR /app                  ✓ CACHED
Layer 3: COPY requirements.txt         ✓ CACHED (file unchanged)
Layer 4: RUN pip install               ✓ CACHED (layer 3 unchanged)
Layer 5: COPY src/                     ✗ REBUILD (file changed)
─────────────────────────────────────────────────────
Total: 10 seconds

BUILD 3 (Added new dependency):
Layer 1: FROM python:3.11-slim        ✓ CACHED
Layer 2: WORKDIR /app                  ✓ CACHED
Layer 3: COPY requirements.txt         ✗ CHANGED
Layer 4: RUN pip install               ✗ REBUILD (layer 3 changed)
Layer 5: COPY src/                     ✗ REBUILD (layer 4 changed)
─────────────────────────────────────────────────────
Total: 5 minutes (expected — dependencies changed)
```

### General Ordering Principle

```
Most stable (rarely changes)     → Top of Dockerfile
│
│  FROM base-image
│  System packages (apt-get)
│  Python dependencies (pip install)
│  Configuration files
│  Application code
▼
Most volatile (changes often)    → Bottom of Dockerfile
```

---

## AI Application Specific Considerations

AI applications have unique requirements that affect Dockerfile design.

### Large Model Files

**Problem:** Embedding models, fine-tuned weights can be 100MB-10GB.

**Don't do this:**

```dockerfile
# BAD: Bakes model into image — huge image, slow pulls
COPY models/bge-large-en-v1.5/ ./models/
```

**Options:**

|Strategy|When to Use|How|
|---|---|---|
|**External API**|Using OpenAI/Anthropic|No local models needed|
|**Download at startup**|Small models (<500MB)|Script in entrypoint|
|**Volume mount**|Development, shared models|`-v /host/models:/app/models`|
|**Cloud storage**|Production, multiple instances|Download from S3/GCS at startup|

```dockerfile
# Download at startup approach
COPY scripts/download_models.py ./scripts/
RUN python scripts/download_models.py --model sentence-transformers/all-MiniLM-L6-v2
```

### GPU Support

If you need GPU for local inference:

```dockerfile
# For NVIDIA GPUs
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Install Python
RUN apt-get update && apt-get install -y python3.11 python3-pip

# Install PyTorch with CUDA support
RUN pip install torch --index-url https://download.pytorch.org/whl/cu121
```

**Note:** Most bootcamp applications use OpenAI/Anthropic APIs and don't need local GPU. Only add GPU complexity if you're running local models.

### Memory Requirements

AI applications typically need more RAM than standard web apps:

|Component|Typical Memory|
|---|---|
|Python runtime|50-100MB|
|FastAPI + Uvicorn|50-100MB|
|Embedding model (small)|200-500MB|
|Embedding model (large)|500MB-2GB|
|ChromaDB (in-memory)|100MB-1GB+|
|LangChain overhead|50-100MB|

**Set memory limits in Docker:**

```bash
# Limit container to 2GB RAM
docker run -m 2g research-assistant:v1.0
```

### Environment Variables for AI Apps

```dockerfile
# Python behavior
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Don't set secrets in Dockerfile!
# These are injected at runtime:
# OPENAI_API_KEY
# ANTHROPIC_API_KEY
# LANGCHAIN_API_KEY
```

---

## Multi-Stage Builds

Multi-stage builds reduce final image size by separating build-time dependencies from runtime.

### The Problem

Some Python packages require compilation:

- `numpy`, `scipy` need C compiler
- `psycopg2` needs PostgreSQL development headers
- `cryptography` needs Rust compiler

Installing these adds ~500MB of build tools to your image that aren't needed at runtime.

### The Solution

```dockerfile
# ============================================
# Stage 1: Builder — install and compile
# ============================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ============================================
# Stage 2: Runtime — lean production image
# ============================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime-only system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create non-root user
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Size Comparison

```
Single-stage (with gcc, build tools):  ~900MB
Multi-stage (runtime only):            ~250MB

Savings: ~650MB, ~70% smaller
```

### When Multi-Stage is Worth It

|Situation|Multi-Stage?|
|---|---|
|Production deployment|Yes — smaller images, faster pulls|
|Development iteration|Maybe — adds build complexity|
|All deps are pure Python|No — no compilation needed|
|Using pre-built wheels|Usually no — wheels are already compiled|

**For your Research Assistant:** If all your dependencies install without errors on `python:3.11-slim`, you may not need multi-stage. Try the simple approach first.

---

## Complete Dockerfile Example

A production-ready Dockerfile for a FastAPI-based AI application:

```dockerfile
# ============================================
# Research Assistant Dockerfile
# Docs referenced: Docker best practices (docs.docker.com/build/building/best-practices)
#                  Python Docker guide (pythonspeed.com/articles/base-image-python-docker-images)
# ============================================

FROM python:3.11-slim-bookworm

# ----------------------------------------
# Environment configuration
# ----------------------------------------
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ----------------------------------------
# Install system dependencies (if needed)
# ----------------------------------------
# Uncomment if you need system packages
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     libpq5 \
#     && rm -rf /var/lib/apt/lists/*

# ----------------------------------------
# Install Python dependencies
# (Copy requirements first for layer caching)
# ----------------------------------------
COPY requirements.txt .
RUN pip install -r requirements.txt

# ----------------------------------------
# Copy application code
# ----------------------------------------
COPY src/ ./src/
COPY config/ ./config/

# ----------------------------------------
# Create non-root user (security best practice)
# ----------------------------------------
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app

USER appuser

# ----------------------------------------
# Runtime configuration
# ----------------------------------------
EXPOSE 8000

# Health check (optional but recommended)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Startup command
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## .dockerignore

The `.dockerignore` file excludes files from the build context, similar to `.gitignore`.

### Why It Matters

1. **Faster builds**: Less data to send to Docker daemon
2. **Smaller context**: Avoids copying unnecessary files
3. **Security**: Prevents secrets from accidentally being included
4. **Cache efficiency**: Changes to ignored files don't invalidate cache

### Recommended .dockerignore for Python AI Apps

```dockerignore
# Git
.git
.gitignore

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so
.eggs
*.egg-info
*.egg

# Virtual environments
venv
.venv
env
.env

# IDE
.vscode
.idea
*.swp
*.swo

# Testing
.pytest_cache
.coverage
htmlcov
.tox
.nox

# Documentation
docs
*.md
!README.md

# Docker (don't include Dockerfile in context)
Dockerfile
docker-compose*.yml
.docker

# CI/CD
.github
.gitlab-ci.yml
.travis.yml

# Local development
*.local
.env.local
.env.*.local

# Data and models (mount as volumes instead)
data/
models/
*.db
*.sqlite

# Logs
logs/
*.log

# Jupyter
.ipynb_checkpoints
*.ipynb

# OS
.DS_Store
Thumbs.db
```

### Impact Example

```
Without .dockerignore:
├── .git/              (500MB of git history)
├── venv/              (200MB of local virtualenv)
├── data/              (1GB of vector DB)
├── __pycache__/       (10MB of bytecode)
├── src/               (1MB of code)
└── requirements.txt

Build context: 1.7GB sent to Docker daemon

With .dockerignore (excluding above):
├── src/               (1MB of code)
└── requirements.txt

Build context: 1MB sent to Docker daemon
```

---

## Quick Reference: Common Patterns

### Pattern 1: Simple Python App

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Pattern 2: FastAPI with Uvicorn

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Pattern 3: With System Dependencies

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Pattern 4: Non-Root User (Production)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN adduser --system --no-create-home appuser
USER appuser
CMD ["python", "main.py"]
```

---

## Docs Referenced

- Docker official best practices: https://docs.docker.com/build/building/best-practices/
- Python base image guide (Feb 2026): https://pythonspeed.com/articles/base-image-python-docker-images/
- Docker Python development guide: https://www.docker.com/blog/containerized-python-development-part-1/
- TestDriven.io Docker best practices: https://testdriven.io/blog/docker-best-practices/

---

## What's Next

This note covered how to write Dockerfiles for Python AI applications. The next note covers **Docker Compose** — orchestrating multiple services (your app + Redis + vector DB) for local development.