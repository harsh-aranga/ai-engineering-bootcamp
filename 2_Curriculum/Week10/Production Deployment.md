# Week 10: Production Deployment & Operations

> **Track:** Deployment & Operations (Optional) **Time:** 2 hours/day **Goal:** Understand how to deploy AI systems to production, implement safe deployment strategies, and manage model/prompt versioning for AI applications.

---

## Overview

|Days|Topic|Output|
|---|---|---|
|1-2|Docker + Cloud Deployment|Containerization + cloud deployment concepts|
|3-4|CI/CD + Deployment Strategies|Pipeline concepts + safe rollout patterns|
|5-6|Model Migration & Versioning|AI-specific production patterns|
|7|Buffer|Review / optional hands-on|

---

## Days 1-2: Docker + Cloud Deployment

### Why This Matters

"It works on my machine" is not a deployment strategy.

Your Research Assistant has:

- Python dependencies (specific versions)
- Environment variables (API keys, configs)
- Vector database files
- Specific Python version requirements

Without containerization, deploying means:

- Manually installing dependencies on a server
- Debugging "missing library" errors
- Different behavior in prod vs. dev
- Nightmare when you need to deploy to a second server

Docker solves this: Package your app + all dependencies into a single container. Runs the same everywhere.

### What to Learn

**Core Concepts:**

**Containerization Fundamentals:**

```
┌─────────────────────────────────────────────────────────────┐
│                     YOUR LAPTOP                              │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    DOCKER                            │    │
│  │                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐                 │    │
│  │  │  Container 1 │  │  Container 2 │                 │    │
│  │  │              │  │              │                 │    │
│  │  │ Research     │  │  PostgreSQL  │                 │    │
│  │  │ Assistant    │  │              │                 │    │
│  │  │ Python 3.11  │  │              │                 │    │
│  │  │ + deps       │  │              │                 │    │
│  │  └──────────────┘  └──────────────┘                 │    │
│  │                                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘

Container = Isolated environment with its own:
- File system
- Dependencies
- Environment variables
- Network (can expose ports)

NOT a VM — shares host OS kernel, much lighter
```

**Docker Key Terms:**

```
IMAGE
- Blueprint/template for containers
- Built from Dockerfile
- Immutable — once built, doesn't change
- Versioned with tags (myapp:v1.0, myapp:latest)

CONTAINER
- Running instance of an image
- Can have multiple containers from same image
- Ephemeral — data lost when container stops (unless using volumes)

DOCKERFILE
- Recipe for building an image
- Specifies base image, dependencies, commands
- Each instruction creates a layer (cached for speed)

VOLUME
- Persistent storage that survives container restarts
- Mount host directory into container
- Essential for databases, vector stores

DOCKER COMPOSE
- Define multi-container applications
- One YAML file describes all services
- `docker-compose up` starts everything
```

**Dockerfile Anatomy:**

```dockerfile
# Base image — start from existing image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Copy dependency file first (layer caching optimization)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production

# Expose port (documentation + allows port mapping)
EXPOSE 8000

# Command to run when container starts
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Layer Caching — Why Order Matters:**

```dockerfile
# BAD — any code change invalidates pip install cache
COPY . .
RUN pip install -r requirements.txt

# GOOD — dependencies cached unless requirements.txt changes
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
```

**Cloud Deployment Options:**

|Platform|Complexity|Cost|Best For|
|---|---|---|---|
|Railway|Very Low|$5-20/mo|Quick deploys, small projects|
|Fly.io|Low|$5-20/mo|Edge deployment, global|
|Render|Low|$7-25/mo|Simple web apps|
|AWS ECS/Fargate|Medium|Variable|Production, scaling|
|GCP Cloud Run|Medium|Variable|Serverless containers|
|AWS Lambda|Medium|Pay-per-use|Sporadic traffic|
|Kubernetes|High|Variable|Large scale, complex|

**For AI Applications — Special Considerations:**

```
COLD START PROBLEM
- Serverless (Lambda, Cloud Run) spins down when idle
- First request loads model, dependencies — slow (5-30s)
- Solutions: Keep-warm pings, provisioned concurrency, dedicated instances

MEMORY REQUIREMENTS
- Embedding models need RAM (500MB-2GB)
- Vector DBs need RAM
- Lambda max 10GB, often not enough
- Dedicated instances more predictable

GPU ACCESS
- Most platforms don't offer GPU
- GPU needed for: local embedding models, local LLMs
- If using OpenAI/Anthropic APIs: no GPU needed
- GPU platforms: AWS EC2 GPU, GCP GPU, Modal, Replicate

SECRETS MANAGEMENT
- Never hardcode API keys in Docker image
- Use platform's secrets/environment variables
- Injected at runtime, not build time
```

**Environment Management:**

```
ENVIRONMENT HIERARCHY

┌─────────────────┐
│   PRODUCTION    │  Real users, real data
│   (prod)        │  Most stable config
└────────┬────────┘
         │
┌────────┴────────┐
│    STAGING      │  Production-like, for final testing
│    (staging)    │  Same infra, fake/anonymized data
└────────┬────────┘
         │
┌────────┴────────┐
│   DEVELOPMENT   │  Local or shared dev environment
│   (dev)         │  Faster iteration, debug mode
└─────────────────┘

CONFIGURATION STRATEGY

Option A: Environment Variables (Recommended)
- Set per environment
- Platform manages them
- Never in code

Option B: Config Files per Environment
- config/production.yaml
- config/staging.yaml
- config/development.yaml
- Select via ENV variable

Option C: Feature Flags
- Same code, behavior toggled
- More complex, more flexible
```

**Docker Compose for Local Development:**

```yaml
# docker-compose.yml
version: '3.8'

services:
  research-assistant:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - APP_ENV=development
    volumes:
      - ./data:/app/data  # Persist vector DB
      - ./logs:/app/logs  # Persist logs
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

**Practical Skills:**

- Write a Dockerfile for your application
- Understand layer caching and optimization
- Use Docker Compose for multi-service apps
- Choose appropriate cloud platform
- Manage environment variables and secrets

### Resources

**Primary:**

- Docker Documentation: https://docs.docker.com/get-started/
- Docker Compose: https://docs.docker.com/compose/
- Railway Docs: https://docs.railway.app/
- Fly.io Docs: https://fly.io/docs/

**Secondary:**

- Search: "Dockerfile best practices Python"
- Search: "deploy FastAPI Docker"
- Search: "Railway vs Fly.io comparison"

### Day 1 Tasks (2 hours)

**Hour 1 — Learn:**

1. Read Docker overview — understand images, containers, volumes (20 min)
2. Study Dockerfile syntax — understand each instruction (20 min)
3. Read about layer caching — why order matters (10 min)
4. Review Docker Compose basics (10 min)

**Hour 2 — Analyze + Design:**

1. Analyze your Research Assistant:
    - What Python version?
    - What dependencies (requirements.txt)?
    - What files need to be in the container?
    - What environment variables needed?
    - What ports exposed?
    - What data needs to persist (volumes)?
2. Draft a Dockerfile for your Research Assistant (don't run yet, just write)
3. Draft a docker-compose.yml if you have multiple services
4. Document your decisions: Why this base image? Why this structure?

### Day 2 Tasks (2 hours)

**Hour 1 — Learn Cloud Options:**

1. Compare cloud platforms (see table above) — which fits your needs? (20 min)
2. Read about environment variable management in your chosen platform (15 min)
3. Understand cold start implications for AI apps (15 min)
4. Read about secrets management best practices (10 min)

**Hour 2 — Mini Challenge: Deployment Design Document**

Create a deployment design document for your Research Assistant:

```markdown
# Research Assistant Deployment Design

## Container Strategy
- Base image: [choice + reasoning]
- Multi-stage build: [yes/no + why]
- Expected image size: [estimate]

## Cloud Platform
- Platform choice: [Railway/Fly.io/AWS/etc]
- Reasoning: [cost, complexity, features]
- Region: [choice + why]

## Environment Configuration
- Environment variables needed:
  - OPENAI_API_KEY (secret)
  - APP_ENV (config)
  - [others]
- Config file strategy: [approach]

## Persistence
- Vector database: [how persisted]
- Cache: [Redis? Where hosted?]
- Logs: [where stored]

## Resource Requirements
- Memory: [estimate]
- CPU: [estimate]
- Disk: [estimate]
- GPU: [needed? why/why not]

## Cold Start Mitigation
- Strategy: [keep-warm/provisioned/dedicated]
- Acceptable cold start time: [X seconds]

## Estimated Costs
- Platform: $X/month
- LLM APIs: $X/month (from Week 8 estimates)
- Total: $X/month

## Deployment Commands
- Build: `docker build -t research-assistant .`
- Run locally: `docker run -p 8000:8000 research-assistant`
- Deploy: [platform-specific command]

## Health Check
- Endpoint: /health
- What it checks: [list]
```

**Success Criteria:**

- [ ] Dockerfile drafted (syntactically correct)
- [ ] Cloud platform chosen with reasoning
- [ ] Environment variables documented
- [ ] Persistence strategy defined
- [ ] Resource requirements estimated
- [ ] Cost estimate calculated
- [ ] Cold start strategy documented
- [ ] Design document complete and coherent

### 5 Things to Ponder

1. Your Docker image is 2GB (Python + dependencies + model files). Every deploy uploads 2GB. Every scale-up pulls 2GB. How do you reduce image size? Multi-stage builds? Smaller base image? External model storage?
    
2. You deploy to Railway. It works. You push an update. The new container starts, the old one stops. For 30 seconds during switchover, some requests fail. How do you achieve zero-downtime deployment? (Preview: Day 3-4)
    
3. Your Research Assistant needs ChromaDB (vector store). ChromaDB stores data on disk. Containers are ephemeral — disk wiped on restart. How do you persist vector data? Volume mount? External database? Rebuild index on start?
    
4. You have OPENAI_API_KEY in your environment. A developer accidentally logs `os.environ` in debug mode. The key appears in logs. Logs are stored in a logging service. Key is now leaked. How do you prevent secrets from leaking into logs?
    
5. Your app runs fine locally with 8GB RAM. You deploy to a 512MB container — it crashes. You upgrade to 2GB — works but slow. Cloud resources cost money. How do you determine the minimum viable resource allocation? Load test? Monitor and adjust?
    

---

## Days 3-4: CI/CD + Deployment Strategies

### Why This Matters

Manual deployment is:

- Error-prone (forgot a step? wrong environment?)
- Slow (SSH, pull, restart, pray)
- Scary (will this break production?)
- Unauditable (who deployed what when?)

CI/CD automates the path from code to production:

- Push code → Tests run automatically → Deploy if tests pass
- Every deployment is reproducible
- Rollback is one click (or automatic)

Deployment strategies determine _how_ new code reaches users:

- All at once? (risky)
- Gradually? (safer)
- Can you undo quickly? (essential)

### What to Learn

**Core Concepts:**

**CI/CD Pipeline:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CI/CD PIPELINE                                    │
│                                                                              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐   │
│  │  CODE   │───▶│  BUILD  │───▶│  TEST   │───▶│ DEPLOY  │───▶│ MONITOR │   │
│  │  PUSH   │    │         │    │         │    │         │    │         │   │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘   │
│                                                                              │
│  Developer      Docker        Unit tests    Push to       Watch for         │
│  pushes to      image         Integration   production    errors            │
│  main branch    created       Linting       (staged)      Rollback if bad   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

CI = Continuous Integration
- Automatically build and test on every push
- Catch bugs before they reach production
- Everyone integrates frequently

CD = Continuous Deployment/Delivery
- Deployment: Auto-deploy to production after tests pass
- Delivery: Auto-deploy to staging, manual approval for prod
```

**CI/CD Platforms:**

|Platform|Integrated With|Complexity|Cost|
|---|---|---|---|
|GitHub Actions|GitHub|Low|Free tier generous|
|GitLab CI|GitLab|Low|Free tier available|
|CircleCI|Any Git|Medium|Free tier limited|
|Jenkins|Any|High|Self-hosted (free)|
|Railway/Render|Their platform|Very Low|Included|

**GitHub Actions Example:**

```yaml
# .github/workflows/deploy.yml
name: Deploy Research Assistant

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest
      
      - name: Run tests
        run: pytest tests/ -v
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      
      - name: Build Docker image
        run: docker build -t ${{ env.IMAGE_NAME }}:${{ github.sha }} .
      
      - name: Push to registry
        run: |
          echo ${{ secrets.GITHUB_TOKEN }} | docker login ghcr.io -u ${{ github.actor }} --password-stdin
          docker push ${{ env.IMAGE_NAME }}:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to production
        run: |
          # Platform-specific deployment command
          # e.g., railway up, flyctl deploy, etc.
```

**Deployment Strategies:**

**1. Basic Deployment (Recreate)**

```
┌─────────────┐         ┌─────────────┐
│   Old v1    │   ───▶  │   New v2    │
│  (stopped)  │         │  (started)  │
└─────────────┘         └─────────────┘

Downtime: Yes (between stop and start)
Risk: High (all traffic hits new version immediately)
Rollback: Redeploy old version
Use when: Non-critical apps, can tolerate downtime
```

**2. Blue-Green Deployment**

```
                    Load Balancer
                         │
            ┌────────────┴────────────┐
            │                         │
            ▼                         ▼
     ┌─────────────┐          ┌─────────────┐
     │    BLUE     │          │   GREEN     │
     │   (v1)      │          │   (v2)      │
     │  [ACTIVE]   │          │  [STANDBY]  │
     └─────────────┘          └─────────────┘

Step 1: Blue is live, Green has new version
Step 2: Test Green thoroughly
Step 3: Switch load balancer to Green
Step 4: Blue becomes standby (instant rollback available)

Downtime: Zero
Risk: Low (can test before switching)
Rollback: Switch back to Blue (instant)
Cost: 2x infrastructure during deployment
Use when: Production systems, need instant rollback
```

**3. Canary Deployment**

```
                    Load Balancer
                         │
                    ┌────┴────┐
                    │ 90%/10% │
            ┌───────┴─────────┴───────┐
            │                         │
            ▼                         ▼
     ┌─────────────┐          ┌─────────────┐
     │    OLD      │          │   CANARY    │
     │   (v1)      │          │   (v2)      │
     │   90%       │          │   10%       │
     └─────────────┘          └─────────────┘

Step 1: Deploy new version to small % of traffic
Step 2: Monitor errors, latency, user feedback
Step 3: Gradually increase % (10→25→50→100)
Step 4: If problems, route 100% back to old

Downtime: Zero
Risk: Very low (only affects small % of users)
Rollback: Route traffic away from canary
Use when: High-risk changes, need real-world validation
```

**4. Rolling Deployment**

```
Time 0:  [v1] [v1] [v1] [v1]  ← All old
Time 1:  [v2] [v1] [v1] [v1]  ← One updated
Time 2:  [v2] [v2] [v1] [v1]  ← Two updated
Time 3:  [v2] [v2] [v2] [v1]  ← Three updated
Time 4:  [v2] [v2] [v2] [v2]  ← All new

Downtime: Zero
Risk: Medium (gradual, but mixed versions serve traffic)
Rollback: Reverse the rolling update
Use when: Multiple instances, can handle mixed versions
```

**5. Feature Flags (Complementary)**

```python
# Deployment and feature release are decoupled

def process_query(query: str, user_id: str):
    if feature_flags.is_enabled("new_rag_pipeline", user_id):
        return new_rag_pipeline(query)
    else:
        return old_rag_pipeline(query)

# Deploy code with flag OFF
# Enable flag for 1% of users
# Monitor
# Gradually increase %
# When 100%, remove flag and old code
```

**Rollback Strategies:**

```
AUTOMATIC ROLLBACK TRIGGERS
- Error rate > 5% for 2 minutes
- p95 latency > 3x baseline
- Health check failures
- Critical alerts fired

ROLLBACK MECHANISMS
1. Re-deploy previous version (slow, 2-5 min)
2. Switch load balancer (instant, blue-green)
3. Disable feature flag (instant, flag-based)
4. Database rollback (complex, may lose data)

ROLLBACK GOTCHAS
- Database migrations may not be reversible
- External state (caches, queues) may be inconsistent
- Some users saw new version — UX discontinuity
```

**AI-Specific Deployment Concerns:**

```
PROMPT CHANGES
- Prompt is code — should go through CI/CD
- Small prompt change can break behavior
- Test prompts in staging before prod

MODEL ENDPOINT CHANGES
- OpenAI sometimes changes default model versions
- Pin model versions explicitly (gpt-4o-2024-08-06)
- Test model updates before deploying

EMBEDDING CONSISTENCY
- Old embeddings + new embedding model = broken retrieval
- Never mix embedding model versions in same index
- Embedding model change = reindex everything

RESPONSE FORMAT CHANGES
- If changing structured output schema, downstream may break
- Version your API contracts
```

**Practical Skills:**

- Design a CI/CD pipeline for AI applications
- Choose appropriate deployment strategy
- Implement rollback mechanisms
- Use feature flags for safe releases

### Resources

**Primary:**

- GitHub Actions: https://docs.github.com/en/actions
- Deployment Strategies (Martin Fowler): https://martinfowler.com/bliki/BlueGreenDeployment.html
- Feature Flags: https://launchdarkly.com/blog/what-are-feature-flags/

**Secondary:**

- Search: "blue green deployment explained"
- Search: "canary deployment tutorial"
- Search: "GitHub Actions Docker deploy"

### Day 3 Tasks (2 hours)

**Hour 1 — Learn CI/CD:**

1. Understand CI vs. CD — what happens at each stage (15 min)
2. Read GitHub Actions documentation — understand workflow syntax (25 min)
3. Study the example workflow above — understand each job and step (15 min)
4. Think: What tests should run in your CI pipeline? (5 min)

**Hour 2 — Learn Deployment Strategies:**

1. Study each deployment strategy — understand the diagrams (20 min)
2. Compare strategies:
    - When would you use blue-green vs. canary?
    - What's the cost tradeoff?
    - Which allows fastest rollback?
3. Think through: Which strategy fits your Research Assistant? Why? (15 min)
4. Read about feature flags — when they complement deployment strategies (15 min)

### Day 4 Tasks (2 hours)

**Hour 1 — Design:**

1. Design your CI/CD pipeline:
    
    ```
    What triggers the pipeline? (push to main? PR?)What tests run?What is the build artifact? (Docker image?)Where is it stored? (Container registry?)What deploys it? (Platform webhook? CLI?)What monitoring confirms success?What triggers rollback?
    ```
    
2. Draft a GitHub Actions workflow (or equivalent) for your Research Assistant
3. Document rollback procedure

**Hour 2 — Mini Challenge: CI/CD Design Document**

Create a CI/CD design document:

```markdown
# Research Assistant CI/CD Design

## Pipeline Overview

[Diagram of your pipeline stages]

## Trigger Conditions
- Main branch push: [what happens]
- Pull request: [what happens]
- Manual trigger: [when/why needed]

## Test Stage
- Unit tests: [what's tested]
- Integration tests: [what's tested]
- Linting: [tools used]
- Estimated duration: [X minutes]

## Build Stage
- Artifact: Docker image
- Registry: [where stored]
- Tagging strategy: [how images are tagged]

## Deploy Stage
- Strategy: [blue-green/canary/rolling]
- Reasoning: [why this strategy]
- Staging deployment: [auto/manual]
- Production deployment: [auto/manual]

## Rollback Plan
- Automatic triggers:
  - Error rate > X%
  - Latency > Xms
  - Health check failure
- Rollback mechanism: [how]
- Rollback time: [expected duration]
- Data considerations: [any migration issues?]

## Feature Flags
- Tool: [if using]
- Flags planned: [list]
- Rollout strategy: [percentage ramp]

## Monitoring Post-Deploy
- Health endpoint: /health
- Key metrics watched: [list]
- Alert conditions: [list]
- Dashboard: [link or description]

## GitHub Actions Workflow
[Your workflow YAML]
```

**Success Criteria:**
- [ ] Pipeline stages clearly defined
- [ ] Test coverage documented
- [ ] Deployment strategy chosen with reasoning
- [ ] Rollback triggers and mechanism defined
- [ ] Feature flag strategy documented (if applicable)
- [ ] Workflow YAML drafted
- [ ] Post-deploy monitoring defined
- [ ] Document is complete and actionable

### 5 Things to Ponder

1. Your CI runs tests before deploy. But your tests mock the OpenAI API. A test passes, you deploy, and then OpenAI returns a different response format than expected. Production breaks. How do you test integrations with external APIs without hitting them in CI?

2. You use blue-green deployment. Blue is running v1, you deploy v2 to Green. You switch traffic to Green. A user was mid-conversation with v1 (Blue). Their next message goes to v2 (Green). State might be incompatible. How do you handle in-flight sessions during deployment?

3. Canary deployment routes 10% of traffic to the new version. But your traffic is low — 10% is 2 users. Not statistically significant. How do you canary test with low traffic? Longer canary period? Synthetic traffic? Different strategy?

4. Your rollback plan: redeploy v1. But v2 ran a database migration adding a column. v1 doesn't know about that column. Rollback breaks. How do you handle database migrations in a rollback-safe way?

5. Feature flags let you deploy code without releasing features. But now you have flags everywhere. `if flag_enabled()` scattered through codebase. Technical debt grows. How do you manage feature flag lifecycle? When do you clean up old flags?

---

## Days 5-6: Model Migration & Versioning

### Why This Matters

AI applications have unique versioning challenges:

**Traditional software:** Code changes → behavior changes
**AI applications:** Code, prompts, models, embeddings ALL affect behavior

You need to manage:
- **Model versions**: GPT-4o-mini today, GPT-4o-mini-2024-07-18 tomorrow, GPT-5 next year
- **Prompt versions**: Small prompt changes can dramatically change outputs
- **Embedding versions**: Can't mix embeddings from different models
- **Configuration versions**: Temperature, top_p, system prompts

Without versioning, you can't:
- Reproduce past behavior
- Debug why output changed
- Safely test new models
- Rollback when things break

### What to Learn

**Core Concepts:**

**The AI Versioning Problem:**
```

TRADITIONAL APP Code v1.2.3 → Deterministic behavior

AI APP Code v1.2.3 + Prompt v2.1 + Model gpt-4o-mini + Temperature 0.7 + Embedding model v3 + Vector DB indexed on 2024-01-15 → Probabilistic behavior (and still may vary due to model updates)

What changed when output quality dropped?

- Was it your code?
- Did OpenAI update the model?
- Did someone change the prompt?
- Did the embedding model change?
- Was the index corrupted?

Without versioning: NO IDEA With versioning: Can trace exact configuration

````

**Model Abstraction Layer:**
```python
# BAD — Model hardcoded everywhere
def generate_answer(query: str, context: str) -> str:
    response = openai.chat.completions.create(
        model="gpt-4o-mini",  # Hardcoded
        messages=[...]
    )
    return response.choices[0].message.content

# GOOD — Model abstracted
class LLMConfig:
    def __init__(self):
        self.model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1000"))

class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
    
    def generate(self, messages: list) -> str:
        response = openai.chat.completions.create(
            model=self.config.model_name,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            messages=messages
        )
        return response.choices[0].message.content

# Switch models via config, not code changes
````

**Prompt Versioning:**

```python
# Option 1: Prompts in version-controlled files
# prompts/v2.1/system_prompt.txt
# prompts/v2.1/rag_prompt.txt

class PromptManager:
    def __init__(self, version: str = "v2.1"):
        self.version = version
        self.base_path = f"prompts/{version}"
    
    def get_prompt(self, name: str) -> str:
        path = f"{self.base_path}/{name}.txt"
        with open(path) as f:
            return f.read()
    
    def get_version(self) -> str:
        return self.version

# Option 2: Prompts in database with versioning
class PromptStore:
    def get_prompt(self, name: str, version: str = None) -> str:
        """Get prompt by name, optionally at specific version."""
        if version is None:
            version = self.get_active_version(name)
        return self.db.get(name=name, version=version)
    
    def set_active_version(self, name: str, version: str):
        """Promote a version to active (what production uses)."""
        self.db.update_active(name=name, version=version)
    
    def list_versions(self, name: str) -> list:
        """See history of prompt versions."""
        return self.db.list_versions(name=name)
```

**Embedding Model Migration:**

```
PROBLEM:
- text-embedding-ada-002 produces 1536-dim vectors
- text-embedding-3-small produces 1536-dim vectors (but different!)
- Cosine similarity between them: MEANINGLESS
- Can't query ada-002 embeddings with 3-small query vector

MIGRATION STRATEGY: Blue-Green for Embeddings

Step 1: Current state
┌─────────────────────────────────────────┐
│  Vector DB (ada-002 embeddings)         │
│  ████████████████████████████████       │
│  All traffic                            │
└─────────────────────────────────────────┘

Step 2: Build new index in parallel
┌─────────────────────────────────────────┐
│  Vector DB (ada-002 embeddings)         │
│  ████████████████████████████████       │
│  All traffic                            │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  Vector DB (3-small embeddings)         │
│  ████████████████████████████████       │
│  Building... (no traffic yet)           │
└─────────────────────────────────────────┘

Step 3: Test new index
- Run eval suite against new index
- Compare retrieval quality
- Verify no regressions

Step 4: Switch traffic
┌─────────────────────────────────────────┐
│  Vector DB (ada-002 embeddings)         │
│  ████████████████████████████████       │
│  Standby (keep for rollback)            │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  Vector DB (3-small embeddings)         │
│  ████████████████████████████████       │
│  All traffic                            │
└─────────────────────────────────────────┘

Step 5: After confidence, delete old index
```

**A/B Testing Models:**

```python
class ModelABTest:
    def __init__(
        self,
        control_model: str,      # Current model
        treatment_model: str,    # New model to test
        treatment_percentage: float = 10.0,
        metrics_collector = None
    ):
        self.control = control_model
        self.treatment = treatment_model
        self.treatment_pct = treatment_percentage
        self.metrics = metrics_collector
    
    def get_model(self, user_id: str) -> tuple[str, str]:
        """
        Returns (model_name, variant) for this user.
        Consistent — same user always gets same variant.
        """
        # Hash user_id for consistent assignment
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        bucket = hash_val % 100
        
        if bucket < self.treatment_pct:
            return self.treatment, "treatment"
        else:
            return self.control, "control"
    
    def record_outcome(
        self,
        user_id: str,
        variant: str,
        latency_ms: float,
        quality_score: float,
        cost_usd: float
    ):
        """Record metrics for analysis."""
        self.metrics.record(
            experiment="model_ab_test",
            variant=variant,
            latency_ms=latency_ms,
            quality_score=quality_score,
            cost_usd=cost_usd
        )
    
    def get_results(self) -> dict:
        """Analyze A/B test results."""
        control_metrics = self.metrics.get(variant="control")
        treatment_metrics = self.metrics.get(variant="treatment")
        
        return {
            "control": {
                "avg_latency": control_metrics.avg("latency_ms"),
                "avg_quality": control_metrics.avg("quality_score"),
                "avg_cost": control_metrics.avg("cost_usd"),
                "n": control_metrics.count()
            },
            "treatment": {
                "avg_latency": treatment_metrics.avg("latency_ms"),
                "avg_quality": treatment_metrics.avg("quality_score"),
                "avg_cost": treatment_metrics.avg("cost_usd"),
                "n": treatment_metrics.count()
            },
            "statistical_significance": self._calc_significance(
                control_metrics, treatment_metrics
            )
        }
```

**Configuration Versioning:**

```python
# config/v1.0.yaml
llm:
  model: gpt-4o-mini
  temperature: 0.7
  max_tokens: 1000

embedding:
  model: text-embedding-3-small
  dimensions: 1536

retrieval:
  top_k: 10
  rerank_top_k: 5
  similarity_threshold: 0.7

prompts:
  version: v2.1
  system_prompt: prompts/v2.1/system.txt
  rag_prompt: prompts/v2.1/rag.txt

# Entire config is versioned
# Can reproduce exact behavior from any point in time
# Store config version in every log/trace
```

**Production AI Patterns:**

**Pattern 1: Shadow Mode Testing**

```
New model runs in parallel, results logged but not returned to user

┌─────────────────┐     ┌─────────────────┐
│  User Request   │────▶│   Primary       │────▶ Response to User
└─────────────────┘     │   (gpt-4o-mini) │
                        └─────────────────┘
                               │
                               │ (same request)
                               ▼
                        ┌─────────────────┐
                        │   Shadow        │────▶ Log only (not returned)
                        │   (gpt-4o)      │      Compare later
                        └─────────────────┘

Use for: Testing new models without risk
Compare: Quality, latency, cost
Duration: Until confident in new model
```

**Pattern 2: Fallback Chain**

```python
class ModelFallbackChain:
    def __init__(self, models: list[str]):
        """
        Try models in order. If one fails, try next.
        
        Example: ["gpt-4o", "gpt-4o-mini", "claude-3-haiku"]
        """
        self.models = models
    
    def generate(self, messages: list) -> tuple[str, str]:
        """Returns (response, model_used)."""
        for model in self.models:
            try:
                response = call_llm(model, messages)
                return response, model
            except (RateLimitError, TimeoutError, ServiceUnavailable):
                continue
        raise AllModelsFailedError()

# If OpenAI is down, fall back to Anthropic
# If primary model rate-limited, use backup
```

**Pattern 3: Prompt Registry**

```python
class PromptRegistry:
    """
    Central registry for all prompts.
    - Version controlled
    - A/B testable
    - Auditable
    """
    
    def __init__(self, storage):
        self.storage = storage
    
    def register(
        self,
        name: str,
        template: str,
        version: str,
        metadata: dict = None
    ):
        """Register a new prompt version."""
        self.storage.save(
            name=name,
            version=version,
            template=template,
            metadata=metadata or {},
            created_at=datetime.utcnow()
        )
    
    def get(
        self,
        name: str,
        version: str = "active"
    ) -> str:
        """Get prompt template."""
        if version == "active":
            version = self.storage.get_active_version(name)
        return self.storage.get(name, version).template
    
    def render(
        self,
        name: str,
        variables: dict,
        version: str = "active"
    ) -> str:
        """Get prompt with variables filled in."""
        template = self.get(name, version)
        return template.format(**variables)
    
    def promote(self, name: str, version: str):
        """Promote a version to active."""
        self.storage.set_active(name, version)
        self.audit_log.record(
            action="promote",
            name=name,
            version=version
        )
    
    def rollback(self, name: str):
        """Rollback to previous active version."""
        prev_version = self.storage.get_previous_active(name)
        self.promote(name, prev_version)
```

**Pattern 4: Reproducibility Logging**

```python
def log_for_reproducibility(
    request_id: str,
    query: str,
    response: str,
    config: dict
):
    """
    Log everything needed to reproduce this exact response.
    """
    log_entry = {
        "request_id": request_id,
        "timestamp": datetime.utcnow().isoformat(),
        
        # Input
        "query": query,
        
        # Configuration (pinned versions)
        "config": {
            "llm_model": config["llm"]["model"],
            "llm_temperature": config["llm"]["temperature"],
            "embedding_model": config["embedding"]["model"],
            "prompt_version": config["prompts"]["version"],
            "retrieval_config": config["retrieval"],
        },
        
        # Context used (for RAG)
        "retrieved_chunks": [...],
        "reranked_chunks": [...],
        
        # Full prompt sent to LLM
        "full_prompt": [...],
        
        # Response
        "response": response,
        "response_metadata": {
            "tokens_used": ...,
            "finish_reason": ...,
        }
    }
    
    logger.info("request_processed", **log_entry)
```

**Practical Skills:**

- Design model abstraction layer
- Implement prompt versioning
- Plan embedding model migration
- Set up A/B testing for models
- Log for reproducibility

### Resources

**Primary:**

- MLOps Principles: https://ml-ops.org/
- LangSmith Prompt Hub: https://docs.smith.langchain.com/prompt_hub
- Weights & Biases Prompts: https://docs.wandb.ai/guides/prompts

**Secondary:**

- Search: "LLM versioning best practices"
- Search: "prompt management production"
- Search: "A/B testing machine learning"

### Day 5 Tasks (2 hours)

**Hour 1 — Learn Versioning Concepts:**

1. Understand the AI versioning problem — why it's harder than traditional software (15 min)
2. Study model abstraction layer pattern (15 min)
3. Study prompt versioning approaches (15 min)
4. Understand embedding migration strategy (15 min)

**Hour 2 — Analyze Your System:**

1. Audit your Research Assistant:
    - Where are models hardcoded?
    - Where are prompts defined?
    - How are embeddings versioned?
    - Can you reproduce a past response?
2. Document what would need to change for:
    - Switching from GPT-4o-mini to Claude
    - Updating embedding model
    - Rolling back a prompt change
3. Identify versioning gaps in your current implementation

### Day 6 Tasks (2 hours)

**Hour 1 — Learn Production Patterns:**

1. Study shadow mode testing — when and how to use (15 min)
2. Study A/B testing for models — experiment design (15 min)
3. Study fallback chains — resilience through model diversity (15 min)
4. Study reproducibility logging — what to capture (15 min)

**Hour 2 — Mini Challenge: Versioning Design Document**

Create a versioning design document:

````markdown
# Research Assistant Versioning Design

## Current State Audit
- Models hardcoded in: [list files/locations]
- Prompts defined in: [list files/locations]
- Embedding model: [where configured]
- Can reproduce past response: [yes/no, why]

## Model Abstraction

### LLM Configuration
[Your LLMConfig design]

### Supported Models

|Use Case|Primary|Fallback|
|---|---|---|
|Generation|gpt-4o-mini|claude-3-haiku|
|Classification|gpt-4o-mini|-|
|Embeddings|text-embedding-3-small|-|

### Model Switching Procedure

1. Update config
2. Run eval suite
3. Deploy with canary
4. Monitor
5. Full rollout or rollback

## Prompt Versioning

### Storage Strategy

- [ ] Files in git
- [ ] Database with versions
- [ ] Prompt management tool

### Version Scheme

[e.g., semantic versioning, date-based]

### Prompt Registry Design

```python
[Your PromptRegistry or approach]
```

### Prompt Change Procedure

1. Create new version
2. Test in staging
3. A/B test in production (optional)
4. Promote to active
5. Monitor quality metrics

## Embedding Migration

### Current Embedding Model

- Model: [name]
- Dimensions: [N]
- Index size: [N vectors]

### Migration Procedure

1. Build new index with new model (parallel)
2. Run retrieval eval against both
3. Blue-green switch
4. Keep old index for rollback period
5. Delete old index after confidence

### Estimated Migration Time

- Reindex duration: [estimate]
- Testing duration: [estimate]
- Total: [estimate]

## A/B Testing Framework

### When to A/B Test

- New model releases
- Significant prompt changes
- Configuration changes

### Metrics to Compare

- Quality: [how measured]
- Latency: [p50, p95]
- Cost: [per request]

### Sample Size Requirements

- Minimum requests per variant: [N]
- Test duration: [X days]

## Reproducibility

### What to Log

- [ ] Full config (pinned versions)
- [ ] Input query
- [ ] Retrieved context
- [ ] Full prompt sent to LLM
- [ ] Raw LLM response
- [ ] Final output

### Log Retention

- Duration: [X days]
- Storage: [where]

## Rollback Procedures

### Model Rollback

1. [steps]

### Prompt Rollback

1. [steps]

### Embedding Rollback

1. [steps]

### Config Rollback

1. [steps]
   
````

**Success Criteria:**
- [ ] Current state audited (where are versions hardcoded?)
- [ ] Model abstraction layer designed
- [ ] Prompt versioning strategy defined
- [ ] Embedding migration procedure documented
- [ ] A/B testing approach outlined
- [ ] Reproducibility logging specified
- [ ] Rollback procedures for each component
- [ ] Document is actionable (could implement from this)

### 5 Things to Ponder

1. You version your prompts: v1.0, v1.1, v2.0. But what about the *combination* of prompt + model? Prompt v2.0 was optimized for GPT-4o-mini. You switch to Claude. Same prompt, different behavior. How do you version the prompt-model combination?

2. A/B testing models: You need 1000 samples per variant for statistical significance. Your app gets 100 queries/day. Test would take 20 days. Business wants to switch models this week. How do you balance statistical rigor with business speed?

3. OpenAI deprecates gpt-4o-mini with 6 months notice. You have 6 months to migrate. But you also have feature work. Migration keeps getting deprioritized. Deadline arrives, you scramble. How do you build model migration into your regular workflow, not as a crisis?

4. You log everything for reproducibility. Queries contain user data. Responses contain answers based on internal documents. Your logs are now a compliance liability. How do you balance reproducibility with privacy/security?

5. Shadow mode: new model runs in parallel, you compare outputs. But "quality" is subjective. GPT-4o gives longer answers, Claude gives more concise answers. Which is better? Your shadow test needs a quality metric, but quality is hard to define. How do you measure quality for comparison?

---

## Day 7: Buffer

Day 7 is unstructured. Use it for:

- Review and consolidate notes from Days 1-6
- Optional: Actually deploy your Research Assistant (hands-on)
- Optional: Implement CI/CD pipeline (hands-on)
- Optional: Implement model abstraction layer (hands-on)
- Catch up on anything rushed
- Prepare for portfolio phase (Week 11)

---

# WEEK 10 CHECKLIST

## Completion Criteria

- [ ] **Docker:** Understand containerization, can write Dockerfile
- [ ] **Cloud Deployment:** Know options, tradeoffs, chose platform
- [ ] **Environment Management:** Understand secrets, configs, environments
- [ ] **CI/CD:** Understand pipeline stages, can design workflow
- [ ] **Deployment Strategies:** Understand blue-green, canary, rolling
- [ ] **Rollback:** Know triggers and mechanisms
- [ ] **Model Abstraction:** Designed abstraction layer
- [ ] **Prompt Versioning:** Strategy defined
- [ ] **Embedding Migration:** Procedure documented
- [ ] **A/B Testing:** Understand experiment design for models
- [ ] **Reproducibility:** Know what to log

## Deliverables

1. Deployment Design Document (Day 2)
2. CI/CD Design Document (Day 4)
3. Versioning Design Document (Day 6)

## What's Next

**Week 11: Portfolio Projects**

Apply everything from Weeks 1-10 to new domains:
- Project 1: New domain (prove transferability)
- Project 2: Speed run (prove efficiency)
- System design practice
- Interview prep

---

# NOTES SECTION

### Days 1-2 Notes (Docker + Cloud Deployment)


### Days 3-4 Notes (CI/CD + Deployment Strategies)


### Days 5-6 Notes (Model Migration & Versioning)


### Day 7 Notes (Buffer)