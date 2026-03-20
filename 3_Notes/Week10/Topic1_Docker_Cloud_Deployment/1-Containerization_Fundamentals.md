# Note 1: Containerization Fundamentals — Images, Containers, and Layers

## The Problem Containers Solve

Before containers, deploying software looked like this:

```
Developer's Laptop          Production Server
┌─────────────────┐        ┌─────────────────┐
│ Python 3.11.4   │        │ Python 3.9.2    │  ← Different version
│ numpy 1.24.0    │        │ numpy 1.21.0    │  ← Different version
│ macOS 14        │        │ Ubuntu 22.04    │  ← Different OS
│ M2 chip         │        │ x86_64          │  ← Different arch
└─────────────────┘        └─────────────────┘

"It works on my machine" → Doesn't work in production
```

This creates four distinct problems:

**1. "Works on My Machine" Syndrome** Your Research Assistant runs perfectly locally. You deploy to a server. It crashes because the server has Python 3.9 instead of 3.11, and you used a walrus operator (`:=`) that didn't exist in 3.9.

**2. Dependency Conflicts Between Projects** Project A needs `langchain==0.1.0`. Project B needs `langchain==0.2.0`. Both on the same machine. Virtual environments help, but they don't isolate system libraries, and they're fragile.

**3. Environment Drift** Dev has debug logging on, staging has it off, production has a different Redis version. Over time, environments diverge. Bugs appear in production that you can't reproduce locally.

**4. Deployment Reproducibility** Six months later, you need to deploy the same application to a new server. What versions did you use? What system packages were installed? What environment variables were set? If it's not captured somewhere, you're reverse-engineering your own system.

Containers solve all four problems with one mechanism: **package your application AND its entire runtime environment into a single, immutable artifact**.

---

## Container vs Virtual Machine

Both containers and VMs provide isolation, but they work at fundamentally different levels:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         VIRTUAL MACHINES                                 │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                      │
│  │    App A    │  │    App B    │  │    App C    │                      │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤                      │
│  │  Libraries  │  │  Libraries  │  │  Libraries  │                      │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤                      │
│  │  Guest OS   │  │  Guest OS   │  │  Guest OS   │  ← Full OS per VM    │
│  │  (Ubuntu)   │  │  (Debian)   │  │  (Alpine)   │     (GBs each)       │
│  └─────────────┘  └─────────────┘  └─────────────┘                      │
│  ─────────────────────────────────────────────────                      │
│                        HYPERVISOR                                        │
│  ─────────────────────────────────────────────────                      │
│                        HOST OS                                           │
│  ─────────────────────────────────────────────────                      │
│                       HARDWARE                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                          CONTAINERS                                      │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                      │
│  │    App A    │  │    App B    │  │    App C    │                      │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤                      │
│  │  Libraries  │  │  Libraries  │  │  Libraries  │  ← Only app + deps   │
│  └─────────────┘  └─────────────┘  └─────────────┘     (MBs each)       │
│  ─────────────────────────────────────────────────                      │
│                     CONTAINER RUNTIME (Docker)                           │
│  ─────────────────────────────────────────────────                      │
│                        HOST OS KERNEL                                    │  ← Shared kernel
│  ─────────────────────────────────────────────────                      │
│                       HARDWARE                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

|Aspect|Virtual Machine|Container|
|---|---|---|
|**Isolation level**|Hardware virtualization|Process isolation|
|**Size**|GBs (full OS)|MBs (app + deps only)|
|**Startup time**|Minutes|Seconds|
|**Resource overhead**|High (runs entire OS)|Low (shares host kernel)|
|**Isolation strength**|Stronger (separate kernel)|Weaker (shared kernel)|
|**Use case**|Multi-tenant hosting, security isolation|Application deployment, microservices|

**The key insight**: Containers are not lightweight VMs. They're **process isolation with a private filesystem**. A container is still a process running on the host OS — it just can't see other processes or the host filesystem (unless you explicitly allow it).

This is why containers are fast: there's no OS boot, no kernel initialization. `docker run` is closer to starting a program than starting a computer.

---

## Core Concepts

### Images: The Immutable Blueprint

An **image** is a read-only template containing:

- A base operating system (usually minimal Linux)
- Your application code
- All dependencies (system packages, Python libraries, etc.)
- Configuration (environment variables, working directory)
- Instructions for what to run on startup

```
IMAGE: research-assistant:v1.0
┌─────────────────────────────────────────────┐
│  Layer 5: CMD ["python", "main.py"]         │  ← Startup command
│  Layer 4: COPY src/ ./src/                  │  ← Your code
│  Layer 3: RUN pip install -r requirements   │  ← Python deps
│  Layer 2: COPY requirements.txt .           │  ← Dependency list
│  Layer 1: FROM python:3.11-slim             │  ← Base OS + Python
└─────────────────────────────────────────────┘
```

**Key properties of images:**

1. **Immutable**: Once built, an image never changes. This is critical for reproducibility. `research-assistant:v1.0` today is identical to `research-assistant:v1.0` six months from now.
    
2. **Versioned with tags**: Tags are human-readable labels pointing to specific image versions.
    
    - `myapp:v1.0.0` — Specific version (recommended for production)
    - `myapp:latest` — Most recent build (dangerous for production — it changes!)
    - `myapp:abc123` — Git commit hash (precise but less readable)
3. **Stored in registries**: Images live in registries (like Git repositories for containers):
    
    - **Docker Hub** — Public default, free for public images
    - **GitHub Container Registry (GHCR)** — Integrated with GitHub Actions
    - **AWS ECR / GCP GCR / Azure ACR** — Cloud-provider registries

### Containers: Running Instances

A **container** is a running (or stopped) instance of an image. Think of it like this:

```
Image = Class definition
Container = Object instance

class ResearchAssistant:      # Image
    def __init__(self):
        self.model = load_model()
        
assistant1 = ResearchAssistant()  # Container 1
assistant2 = ResearchAssistant()  # Container 2
assistant3 = ResearchAssistant()  # Container 3
```

You can run multiple containers from the same image, each with:

- Its own isolated filesystem (copy-on-write from image)
- Its own network interface
- Its own process space
- Its own environment variables

**Ephemeral by default**: When a container stops, any data written inside it is lost (unless you use volumes). This is intentional — containers should be disposable. Need to update? Don't modify the running container; build a new image and replace.

```bash
# Create and run a container from an image
docker run -d --name my-assistant research-assistant:v1.0

# List running containers
docker ps

# Stop a container (data inside is lost)
docker stop my-assistant

# Remove the container entirely
docker rm my-assistant
```

### Layers: Efficient Storage and Caching

Each instruction in a Dockerfile creates a **layer**. Layers are the secret to Docker's efficiency.

```
Dockerfile                          Resulting Layers
─────────────────────────────────────────────────────────────
FROM python:3.11-slim          →    Layer 1: Base Python image (shared)
COPY requirements.txt .        →    Layer 2: requirements.txt file
RUN pip install -r req...      →    Layer 3: Installed packages (~500MB)
COPY src/ ./src/               →    Layer 4: Your source code (~1MB)
CMD ["python", "main.py"]      →    Layer 5: Metadata (startup command)
```

**Why layers matter:**

1. **Sharing**: If two images use the same base (`python:3.11-slim`), that layer is stored once on disk, shared between both images.
    
2. **Caching**: When rebuilding, Docker reuses unchanged layers. If only Layer 4 (your source code) changed, Layers 1-3 are cached.
    
3. **Network efficiency**: When pulling an image, Docker only downloads layers you don't already have.
    

---

## Layer Caching Explained

Layer caching is why Docker builds are fast after the first build — but only if you structure your Dockerfile correctly.

**The rule**: Docker caches layers from top to bottom. When any layer changes, that layer AND ALL LAYERS BELOW IT are invalidated.

```
BAD ORDER — Cache invalidated on every code change
─────────────────────────────────────────────────────────────
FROM python:3.11-slim
COPY . .                        ← Code changes? Invalidates this layer
RUN pip install -r requirements.txt  ← Must reinstall ALL packages

Change one line of Python → 5-minute rebuild (reinstalling everything)


GOOD ORDER — Dependencies cached separately
─────────────────────────────────────────────────────────────
FROM python:3.11-slim
COPY requirements.txt .         ← Only changes when deps change
RUN pip install -r requirements.txt  ← Cached unless requirements changed
COPY . .                        ← Code changes only invalidate this layer

Change one line of Python → 10-second rebuild (deps cached)
```

**Cache invalidation cascade:**

```
Layer 1: FROM python:3.11       ✓ Cached (didn't change)
Layer 2: COPY requirements.txt  ✓ Cached (file unchanged)
Layer 3: RUN pip install        ✓ Cached (layer 2 unchanged)
Layer 4: COPY src/ ./src/       ✗ CHANGED (you edited main.py)
Layer 5: RUN pytest             ✗ REBUILD (layer 4 changed)
Layer 6: CMD ["python"...]      ✗ REBUILD (layer 5 changed)
```

**Practical impact for AI applications:**

Your `requirements.txt` might include:

- `langchain` (installs 50+ transitive dependencies)
- `openai` (installs httpx, pydantic, etc.)
- `chromadb` (installs numpy, scipy, etc.)

Installing these takes 3-10 minutes. With proper layer ordering, you only pay this cost when you actually change dependencies — not every time you fix a typo in your code.

---

## Volumes: Persistent Storage

By default, container filesystems are ephemeral. This is a problem for:

- Vector databases (ChromaDB data)
- Logs you want to analyze
- Cache files you want to survive restarts
- User uploads

**Volumes** solve this by mounting host directories (or Docker-managed storage) into the container:

```
┌─────────────────────────────────────────────────────────────┐
│                     HOST MACHINE                             │
│                                                              │
│   /home/user/project/                                        │
│   ├── src/                                                   │
│   ├── data/               ←───────────────────┐              │
│   │   └── chroma_db/                          │              │
│   └── logs/               ←───────────────┐   │              │
│                                           │   │              │
│   ┌───────────────────────────────────────┼───┼──────────┐   │
│   │              CONTAINER                │   │          │   │
│   │                                       │   │          │   │
│   │   /app/                               │   │          │   │
│   │   ├── src/        (copied in image)   │   │          │   │
│   │   ├── data/       ←───────────────────┼───┘ VOLUME   │   │
│   │   │   └── chroma_db/  (persists!)     │              │   │
│   │   └── logs/       ←───────────────────┘    VOLUME    │   │
│   │                       (persists!)                    │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

```bash
# Mount host directory as volume
docker run -v /home/user/project/data:/app/data research-assistant:v1.0

# Multiple volumes
docker run \
  -v /home/user/project/data:/app/data \
  -v /home/user/project/logs:/app/logs \
  research-assistant:v1.0
```

**Volume types:**

|Type|Syntax|Use Case|
|---|---|---|
|**Bind mount**|`-v /host/path:/container/path`|Development (live code reload)|
|**Named volume**|`-v mydata:/container/path`|Production (Docker manages location)|
|**tmpfs**|`--tmpfs /container/path`|Temporary data (in-memory, fast)|

**For your Research Assistant:**

- Vector database (`chroma_db/`) → Named volume or bind mount
- Logs → Bind mount (easy access from host)
- Cache → Named volume (persists across restarts)
- Uploaded documents → Bind mount (easy backup)

---

## Networking Basics

Containers have isolated networks by default. They can't see the host network or other containers unless you explicitly configure it.

### Exposing Ports to Host

Your Research Assistant runs a FastAPI server on port 8000 inside the container. To access it from your browser:

```bash
# Map host port 8000 → container port 8000
docker run -p 8000:8000 research-assistant:v1.0

# Map different ports (host 80 → container 8000)
docker run -p 80:8000 research-assistant:v1.0

# Now accessible at http://localhost:80
```

The `-p` flag syntax is `HOST_PORT:CONTAINER_PORT`.

### Container-to-Container Communication

When you have multiple containers (app + Redis + PostgreSQL), they need to communicate:

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCKER NETWORK: app-network              │
│                                                              │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │ research-asst   │    │     redis       │                 │
│  │                 │───▶│                 │                 │
│  │ Connects to:    │    │ Port 6379       │                 │
│  │ redis:6379      │    │                 │                 │
│  └─────────────────┘    └─────────────────┘                 │
│                                                              │
│  Containers can reach each other by NAME (DNS)              │
│  "redis:6379" resolves to the redis container's IP          │
└─────────────────────────────────────────────────────────────┘
```

```bash
# Create a network
docker network create app-network

# Run containers on that network
docker run -d --name redis --network app-network redis:7

docker run -d --name research-assistant \
  --network app-network \
  -e REDIS_HOST=redis \
  research-assistant:v1.0

# Inside research-assistant, "redis" resolves to the redis container
# Your code connects to redis:6379, not localhost:6379
```

**Key insight**: Within a Docker network, containers use **container names** as hostnames. Your application config should use `redis` (the container name), not `localhost` or an IP address.

---

## Mental Model Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    THE DOCKER MENTAL MODEL                   │
│                                                              │
│  Dockerfile ───build───▶ Image ───run───▶ Container         │
│  (recipe)               (template)        (running instance) │
│                                                              │
│  Image = Immutable, versioned, shareable                    │
│  Container = Ephemeral, isolated, disposable                │
│  Volume = Persistent storage that survives restarts         │
│  Network = Isolated communication channel                    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              PRODUCTION PATTERN                      │    │
│  │                                                      │    │
│  │  1. Build image with specific tag (v1.2.3)          │    │
│  │  2. Push to registry                                 │    │
│  │  3. Pull on production server                        │    │
│  │  4. Run with volumes for data, env vars for config  │    │
│  │  5. To update: build new image, replace container    │    │
│  │                                                      │    │
│  │  Never modify running containers.                    │    │
│  │  Never use :latest in production.                    │    │
│  │  Containers are cattle, not pets.                    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Practical Considerations for AI Applications

|Concern|Why It Matters for AI Apps|Docker Solution|
|---|---|---|
|**Large dependencies**|ML libraries (PyTorch, TensorFlow) are GBs|Multi-stage builds, slim base images|
|**Model files**|Embedding models, fine-tuned weights|Volumes for models, or bake into image|
|**Vector DB persistence**|ChromaDB, Qdrant need persistent storage|Volumes mapped to host or managed storage|
|**API keys**|OpenAI, Anthropic keys must not be in image|Environment variables at runtime|
|**Memory usage**|Embedding models need RAM|Container memory limits, choose appropriate instance|
|**Startup time**|Loading models takes seconds|Keep-alive patterns, pre-warming|

---

## What's Next

This note covered **what containers are and why they matter**. The next note covers **how to write Dockerfiles** — the specific syntax and patterns for packaging your Research Assistant into an image.