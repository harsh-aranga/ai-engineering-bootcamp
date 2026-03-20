# Note 5: Environment and Secrets Management

## Why Secrets Management Matters

Secrets (API keys, database passwords, tokens) are the keys to your kingdom. Mishandling them causes real damage:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    WAYS SECRETS GET LEAKED                               │
│                                                                          │
│  ┌──────────────────┐                                                   │
│  │ Hardcoded in     │ → Committed to git → Pushed to GitHub            │
│  │ source code      │   → Scraped by bots within minutes               │
│  │                  │   → Your OpenAI account charged $10,000          │
│  └──────────────────┘                                                   │
│                                                                          │
│  ┌──────────────────┐                                                   │
│  │ ENV in Dockerfile│ → Baked into image → Pushed to registry          │
│  │ (build time)     │   → Anyone with image access sees it             │
│  │                  │   → docker history reveals it                     │
│  └──────────────────┘                                                   │
│                                                                          │
│  ┌──────────────────┐                                                   │
│  │ Logged in        │ → Sent to logging service → Indexed/searchable   │
│  │ debug output     │   → Stored for months/years                       │
│  │                  │   → Accessible to support staff                   │
│  └──────────────────┘                                                   │
│                                                                          │
│  ┌──────────────────┐                                                   │
│  │ .env file in     │ → Copied into Docker image → Leaked              │
│  │ Docker context   │   → Common mistake with COPY . .                  │
│  └──────────────────┘                                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Real-World Impact

**Leaked OpenAI API key:** Crypto miners spin up thousands of requests. Your monthly bill: $50,000+.

**Leaked database credentials:** Data breach. Regulatory fines. Customer trust destroyed.

**Leaked cloud provider keys:** Attacker spins up GPU instances for mining. Bill: unlimited.

The fundamental rule: **Secrets should never be in code, images, or logs.**

---

## Environment Variable Basics

Environment variables are the standard way to pass configuration to containers. But there's a critical distinction between build-time and runtime.

### Build Time vs Runtime

```dockerfile
# ═══════════════════════════════════════════════════════════════════
# BUILD TIME — These go INTO the image (visible to anyone with image)
# ═══════════════════════════════════════════════════════════════════

# ENV: Set in Dockerfile, baked into image
ENV APP_ENV=production          # OK for non-secrets
ENV OPENAI_API_KEY=sk-abc123    # NEVER DO THIS — leaked in image

# ARG: Build argument, also baked into image history
ARG DATABASE_URL                # NEVER DO THIS — visible in docker history


# ═══════════════════════════════════════════════════════════════════
# RUNTIME — These are injected when container starts (NOT in image)
# ═══════════════════════════════════════════════════════════════════

# Passed via -e flag
docker run -e OPENAI_API_KEY=sk-abc123 myapp    # Better — not in image

# Passed via compose environment:
services:
  app:
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}        # Better — injected at runtime
```

### The Danger of ARG and ENV

```bash
# You might think ARG is safe because it's "build time only"
docker build --build-arg SECRET=abc123 -t myapp .

# But anyone with the image can see it:
docker history myapp

# Output reveals:
# ARG SECRET=abc123
```

**Rule:** Never use `ARG` or `ENV` in Dockerfile for secrets. Always inject at runtime.

### Safe Pattern

```dockerfile
# Dockerfile — NO secrets here
FROM python:3.11-slim
WORKDIR /app

# Non-sensitive configuration is fine
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Secrets will be injected at runtime via -e or compose
# The application reads them from os.environ
CMD ["python", "main.py"]
```

```python
# main.py — Read secrets from environment at runtime
import os

# These are injected when container starts, not built into image
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable required")
```

---

## The Configuration Hierarchy

Configuration should flow from least specific to most specific, with later values overriding earlier ones.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CONFIGURATION OVERRIDE ORDER                          │
│                                                                          │
│  LOWEST PRIORITY                                         HIGHEST         │
│  ◄─────────────────────────────────────────────────────────────────►    │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│
│  │   Code       │  │   Config     │  │    .env      │  │   Runtime    ││
│  │   Defaults   │  │   Files      │  │    File      │  │   Env Vars   ││
│  ├──────────────┤  ├──────────────┤  ├──────────────┤  ├──────────────┤│
│  │ LOG_LEVEL=   │  │ config/      │  │ .env (local) │  │ -e flag      ││
│  │   "info"     │  │ prod.yaml    │  │ gitignored   │  │ compose env  ││
│  │              │  │              │  │              │  │ platform UI  ││
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘│
│                                                                          │
│  These provide      Structure for    Developer's      Platform injects  │
│  sensible fallbacks complex config   local overrides  at deploy time    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Practical Implementation

```python
# config.py — Configuration with override hierarchy
import os
from pathlib import Path
import yaml

def load_config():
    # 1. Start with code defaults
    config = {
        "log_level": "info",
        "cache_ttl": 3600,
        "max_retries": 3,
    }
    
    # 2. Load from config file based on environment
    app_env = os.environ.get("APP_ENV", "development")
    config_path = Path(f"config/{app_env}.yaml")
    
    if config_path.exists():
        with open(config_path) as f:
            file_config = yaml.safe_load(f)
            config.update(file_config)
    
    # 3. Environment variables override everything
    # (Secrets should ONLY come from here, never from files)
    env_overrides = {
        "log_level": os.environ.get("LOG_LEVEL"),
        "openai_api_key": os.environ.get("OPENAI_API_KEY"),  # Secret
        "database_url": os.environ.get("DATABASE_URL"),       # Secret
    }
    
    # Only apply non-None overrides
    for key, value in env_overrides.items():
        if value is not None:
            config[key] = value
    
    return config
```

### Environment-Specific Config Files

```
config/
├── development.yaml    # Local dev settings
├── staging.yaml        # Staging environment
└── production.yaml     # Production settings
```

```yaml
# config/development.yaml
log_level: debug
cache_ttl: 60              # Short cache for dev
vector_db_path: ./data/chroma_dev
enable_debug_endpoints: true

# NO SECRETS HERE — they come from .env or env vars
```

```yaml
# config/production.yaml
log_level: warning
cache_ttl: 3600            # Long cache for prod
vector_db_path: /data/chroma
enable_debug_endpoints: false

# NO SECRETS HERE — they come from platform secrets
```

**Key principle:** Config files contain non-sensitive settings. Secrets always come from environment variables.

---

## Platform Secrets Management

Each deployment platform has its own way to manage secrets securely.

### Railway

```
Dashboard → Your Project → Variables

Add variables:
- OPENAI_API_KEY = sk-...
- DATABASE_URL = postgresql://...
- ANTHROPIC_API_KEY = sk-ant-...

These are:
- Encrypted at rest
- Injected at runtime
- Never in your image
- Not visible in logs
```

Railway also supports variable references and environments:

```
Production: OPENAI_API_KEY = sk-prod-...
Staging:    OPENAI_API_KEY = sk-staging-...
```

### Render

```
Dashboard → Your Service → Environment

Add environment variables:
- Key: OPENAI_API_KEY
- Value: sk-...
- Sync: No (manual entry, not from file)

Features:
- Secret files (mounted as files, not env vars)
- Environment groups (share across services)
- Sync from .env (be careful with this)
```

### Fly.io

```bash
# Set secrets via CLI (never in fly.toml)
fly secrets set OPENAI_API_KEY=sk-...
fly secrets set DATABASE_URL=postgresql://...

# List secrets (values hidden)
fly secrets list

# Secrets are:
# - Encrypted
# - Injected at runtime
# - Accessible via os.environ
```

```toml
# fly.toml — Non-sensitive config only
[env]
  APP_ENV = "production"
  LOG_LEVEL = "warning"
  # NEVER put secrets here
```

### AWS Secrets Manager

For AWS deployments (ECS, Fargate, Lambda):

```python
# Fetch secrets from AWS Secrets Manager
import boto3
import json

def get_secret(secret_name: str) -> dict:
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])

# Usage
secrets = get_secret("research-assistant/production")
openai_key = secrets["OPENAI_API_KEY"]
```

For ECS/Fargate, secrets can be injected directly:

```json
// Task definition
{
  "containerDefinitions": [{
    "secrets": [{
      "name": "OPENAI_API_KEY",
      "valueFrom": "arn:aws:secretsmanager:region:account:secret:name"
    }]
  }]
}
```

### How Secrets Are Injected at Runtime

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SECRET INJECTION FLOW                                 │
│                                                                          │
│  1. You store secrets in platform                                        │
│     ┌─────────────────┐                                                 │
│     │ Railway/Render  │                                                 │
│     │ Dashboard       │ ── Encrypted storage                            │
│     └────────┬────────┘                                                 │
│              │                                                           │
│  2. Platform fetches secrets at container start                          │
│              │                                                           │
│              ▼                                                           │
│     ┌─────────────────┐                                                 │
│     │ Container       │                                                 │
│     │ Startup         │ ── Platform injects as env vars                 │
│     └────────┬────────┘                                                 │
│              │                                                           │
│  3. Your application reads from os.environ                               │
│              │                                                           │
│              ▼                                                           │
│     ┌─────────────────┐                                                 │
│     │ os.environ[     │                                                 │
│     │ "OPENAI_API_KEY"│ ── Available to your code                       │
│     │ ]               │                                                 │
│     └─────────────────┘                                                 │
│                                                                          │
│  Secrets never touch:                                                    │
│  ✗ Source code                                                          │
│  ✗ Docker image                                                         │
│  ✗ Git repository                                                       │
│  ✗ Build logs                                                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Preventing Secret Leakage

Secrets can leak through many vectors. Here's how to prevent each.

### Never Log Environment Variables

```python
# ═══════════════════════════════════════════════════════════════════
# DANGEROUS — Common debugging mistake
# ═══════════════════════════════════════════════════════════════════

import os
import logging

# This logs ALL environment variables, including secrets
logging.info(f"Environment: {os.environ}")  # NEVER DO THIS

# This also leaks secrets
print(dict(os.environ))  # NEVER DO THIS

# Debugging that accidentally includes secrets
logging.debug(f"Config: {config}")  # Dangerous if config contains secrets


# ═══════════════════════════════════════════════════════════════════
# SAFE — Log only what you need, redact sensitive values
# ═══════════════════════════════════════════════════════════════════

def safe_config_for_logging(config: dict) -> dict:
    """Return config with sensitive values redacted."""
    sensitive_keys = {"api_key", "secret", "password", "token", "key"}
    
    redacted = {}
    for key, value in config.items():
        if any(s in key.lower() for s in sensitive_keys):
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value
    return redacted

# Safe to log
logging.info(f"Config: {safe_config_for_logging(config)}")
```

### Sanitize Error Messages

```python
# ═══════════════════════════════════════════════════════════════════
# DANGEROUS — Error message includes secrets
# ═══════════════════════════════════════════════════════════════════

try:
    response = openai.chat.completions.create(...)
except Exception as e:
    # Error message might include API key in URL or headers
    logging.error(f"OpenAI error: {e}")  # Could leak key
    raise


# ═══════════════════════════════════════════════════════════════════
# SAFE — Sanitize before logging
# ═══════════════════════════════════════════════════════════════════

import re

def sanitize_error(error: str) -> str:
    """Remove potential secrets from error messages."""
    patterns = [
        (r'sk-[a-zA-Z0-9]{20,}', 'sk-***REDACTED***'),           # OpenAI key
        (r'sk-ant-[a-zA-Z0-9-]{20,}', 'sk-ant-***REDACTED***'),  # Anthropic key
        (r'password=[^&\s]+', 'password=***REDACTED***'),         # URL password
        (r'token=[^&\s]+', 'token=***REDACTED***'),               # URL token
    ]
    
    sanitized = str(error)
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized

try:
    response = openai.chat.completions.create(...)
except Exception as e:
    logging.error(f"OpenAI error: {sanitize_error(str(e))}")
    raise
```

### Redact in Observability Tools

If using LangSmith, LangFuse, or other observability tools:

```python
# Many tools auto-redact, but verify your configuration
# LangSmith example — check docs for current API

# Ensure API keys aren't logged in traces
# Most tools redact by default, but double-check:
# - Request headers (Authorization)
# - API key parameters
# - Database connection strings
```

### Secret Scanning in CI

Catch secrets before they're committed:

```yaml
# .github/workflows/security.yaml
name: Security Scan

on: [push, pull_request]

jobs:
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for scanning
      
      - name: TruffleHog Secret Scan
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}
          head: HEAD
```

Pre-commit hook (local protection):

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

### .dockerignore Protection

```dockerignore
# .dockerignore — Prevent secrets from entering image

# Environment files with secrets
.env
.env.*
*.env

# Local config with potential secrets
config/local.yaml
config/*.local.yaml

# IDE files that might contain secrets
.idea/
.vscode/

# Git (might contain secrets in history)
.git/
```

---

## Environment Parity

**The Twelve-Factor App principle:** Dev, staging, and production should be as similar as possible.

### Same Image, Different Config

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ENVIRONMENT PARITY                                    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    SAME DOCKER IMAGE                             │    │
│  │                 research-assistant:v1.2.3                        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│           │                    │                    │                   │
│           ▼                    ▼                    ▼                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │   DEVELOPMENT   │  │     STAGING     │  │   PRODUCTION    │         │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤         │
│  │ APP_ENV=dev     │  │ APP_ENV=staging │  │ APP_ENV=prod    │         │
│  │ LOG_LEVEL=debug │  │ LOG_LEVEL=info  │  │ LOG_LEVEL=warn  │         │
│  │ OPENAI_KEY=test │  │ OPENAI_KEY=stg  │  │ OPENAI_KEY=prod │         │
│  │ DB_URL=local    │  │ DB_URL=staging  │  │ DB_URL=prod     │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                          │
│  Different environment variables, same code behavior                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Parity Matters

|Without Parity|With Parity|
|---|---|
|"Works on staging, breaks in prod"|Same image everywhere|
|Different Python versions|Identical runtime|
|Different dependency versions|Same container|
|Debugging production issues locally is hard|Reproduce issues exactly|

### Achieving Parity

```yaml
# compose.yaml — Same structure for all environments

services:
  research-assistant:
    image: research-assistant:${VERSION:-latest}  # Same image
    environment:
      - APP_ENV=${APP_ENV:-development}
      - LOG_LEVEL=${LOG_LEVEL:-info}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DATABASE_URL=${DATABASE_URL}
```

```bash
# Development
APP_ENV=development LOG_LEVEL=debug docker compose up

# Staging (different env vars, same image)
APP_ENV=staging LOG_LEVEL=info docker compose up

# Production (platform injects env vars)
# Same image, production secrets from platform
```

### Minimal Environment Differences

|Acceptable Differences|Problematic Differences|
|---|---|
|API keys (test vs prod)|Different Python versions|
|Database URLs|Different dependency versions|
|Log levels|Different base images|
|Cache TTLs|Code changes between envs|
|Feature flags|Manual config edits|

---

## .env File Best Practices

The `.env` file is for local development only. It should never be deployed.

### File Structure

```
project/
├── .env              # Real secrets (NEVER committed)
├── .env.example      # Template (committed, no real values)
├── .env.test         # Test environment (may be committed if no secrets)
└── .gitignore        # Must include .env
```

### .env.example (Committed)

```bash
# .env.example
# Copy this file to .env and fill in real values
# DO NOT commit .env to git

# Required — Application will not start without these
OPENAI_API_KEY=your-openai-api-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Optional — Defaults exist in code
LOG_LEVEL=debug
CACHE_TTL=60

# For Anthropic (if using Claude)
ANTHROPIC_API_KEY=your-anthropic-key-here

# For observability (optional)
LANGSMITH_API_KEY=your-langsmith-key-here
```

### .env (Never Committed)

```bash
# .env
# This file contains real secrets — NEVER commit to git

OPENAI_API_KEY=sk-abc123...
DATABASE_URL=postgresql://harsh:realpassword@localhost:5432/research_assistant
ANTHROPIC_API_KEY=sk-ant-abc123...
```

### .gitignore

```gitignore
# .gitignore

# Environment files with secrets
.env
.env.local
.env.*.local
.env.production
.env.staging

# Keep the example
!.env.example
```

### Loading .env Files

```python
# Python — python-dotenv
from dotenv import load_dotenv
import os

# Load .env file (only in development)
if os.environ.get("APP_ENV") != "production":
    load_dotenv()

# Now os.environ contains values from .env
openai_key = os.environ.get("OPENAI_API_KEY")
```

```python
# Pydantic Settings — Better approach
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    database_url: str
    log_level: str = "info"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()  # Automatically loads from .env and environment
```

### Documenting Required Variables

```python
# config.py — Self-documenting configuration
import os
import sys

REQUIRED_VARS = [
    ("OPENAI_API_KEY", "OpenAI API key for LLM calls"),
    ("DATABASE_URL", "PostgreSQL connection string"),
]

OPTIONAL_VARS = [
    ("LOG_LEVEL", "Logging level", "info"),
    ("CACHE_TTL", "Cache time-to-live in seconds", "3600"),
]

def validate_environment():
    """Check all required environment variables are set."""
    missing = []
    for var_name, description in REQUIRED_VARS:
        if not os.environ.get(var_name):
            missing.append(f"  {var_name}: {description}")
    
    if missing:
        print("ERROR: Missing required environment variables:")
        print("\n".join(missing))
        print("\nCopy .env.example to .env and fill in values.")
        sys.exit(1)

# Call at startup
validate_environment()
```

---

## Quick Reference: Secrets Checklist

### Before Committing Code

- [ ] No hardcoded secrets in source files
- [ ] `.env` is in `.gitignore`
- [ ] `.env.example` has placeholders, not real values
- [ ] No secrets in Dockerfile `ENV` or `ARG`
- [ ] Pre-commit hooks for secret scanning

### Before Building Image

- [ ] `.dockerignore` excludes `.env` files
- [ ] No `COPY .env` in Dockerfile
- [ ] Secrets not passed as build args
- [ ] `docker history` shows no secrets

### Before Deploying

- [ ] Secrets configured in platform (Railway/Render/etc.)
- [ ] Secrets injected at runtime, not build time
- [ ] Different secrets for each environment
- [ ] Production secrets not shared with developers

### In Application Code

- [ ] Never log `os.environ` or full config
- [ ] Sanitize error messages
- [ ] Redact secrets in observability tools
- [ ] Validate required vars at startup

---

## Sources Referenced

- Docker secrets documentation: https://docs.docker.com/engine/swarm/secrets/
- Docker Compose secrets: https://docs.docker.com/compose/how-tos/use-secrets/
- Docker environment variables best practices: https://docs.docker.com/compose/how-tos/environment-variables/best-practices/
- GitGuardian secrets handling: https://blog.gitguardian.com/how-to-handle-secrets-in-docker/

---

## What's Next

This note covered environment and secrets management. The next note provides a **Deployment Design Checklist** — a practical template for planning your Research Assistant deployment, pulling together concepts from all previous notes.