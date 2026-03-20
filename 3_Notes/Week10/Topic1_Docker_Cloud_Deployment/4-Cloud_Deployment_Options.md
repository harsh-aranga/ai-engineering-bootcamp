# Note 4: Cloud Deployment Options — Choosing the Right Platform

## Platform Categories

Cloud deployment options exist on a spectrum from "fully managed, zero control" to "full control, maximum complexity":

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT PLATFORM SPECTRUM                          │
│                                                                          │
│  SIMPLICITY                                              CONTROL         │
│  ◄─────────────────────────────────────────────────────────────────►    │
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   PaaS   │  │ Container│  │Serverless│  │ Managed  │  │  Self-   │  │
│  │ (Simple) │  │ Services │  │          │  │   K8s    │  │ Managed  │  │
│  ├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤  │
│  │ Railway  │  │ Cloud Run│  │  Lambda  │  │   GKE    │  │ Your K8s │  │
│  │ Render   │  │ Fargate  │  │ Cloud    │  │   EKS    │  │ on VMs   │  │
│  │ Fly.io   │  │ App Svc  │  │ Functions│  │   AKS    │  │          │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                                          │
│  Minutes to      Hours to      Hours to      Days to       Weeks to     │
│  deploy          deploy        deploy        deploy        deploy       │
│                                                                          │
│  $5-50/mo        $20-200/mo    Pay-per-use   $100+/mo      Variable     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Category Breakdown

**PaaS (Platform as a Service) — Simple**

- Railway, Render, Fly.io, Heroku
- Git push → deployed
- Minimal configuration
- Best for: Getting started, small teams, MVPs

**Container Services — Medium Complexity**

- AWS ECS/Fargate, Google Cloud Run, Azure Container Apps
- Deploy Docker containers
- More configuration options
- Best for: Production workloads, scaling needs

**Serverless Functions**

- AWS Lambda, Google Cloud Functions, Azure Functions
- Pay per invocation
- Cold starts are a concern
- Best for: Event-driven, sporadic traffic

**Managed Kubernetes**

- AWS EKS, Google GKE, Azure AKS
- Full container orchestration
- Significant learning curve
- Best for: Large scale, complex systems, multi-service architectures

---

## Platform Comparison Table

|Platform|Category|Complexity|Cost Model|Cold Starts|GPU|Best For|
|---|---|---|---|---|---|---|
|**Railway**|PaaS|Very Low|Usage-based (~$5-20/mo)|No (always-on)|No|Prototypes, MVPs|
|**Render**|PaaS|Low|Per-service ($7-25/mo)|Yes (free tier)|No|Production web apps|
|**Fly.io**|PaaS|Low-Medium|Usage-based (~$5-30/mo)|Optional|No|Global/edge apps|
|**Cloud Run**|Container|Medium|Per-request + compute|Yes (configurable)|Yes|Scalable APIs|
|**AWS Fargate**|Container|Medium-High|vCPU + memory hours|No (always-on)|No|AWS ecosystem|
|**AWS Lambda**|Serverless|Medium|Per-invocation|Yes (seconds)|No|Event-driven|
|**AWS EKS**|Kubernetes|High|Cluster + nodes|No|Yes|Large scale|
|**GKE**|Kubernetes|High|Cluster + nodes|No|Yes|Large scale|

### Key Trade-offs

|Factor|PaaS (Railway/Render)|Container Services|Kubernetes|
|---|---|---|---|
|**Time to deploy**|Minutes|Hours|Days|
|**Learning curve**|Minimal|Moderate|Steep|
|**Scaling control**|Limited|Good|Full|
|**Cost at scale**|Higher per-unit|Moderate|Lower at scale|
|**Vendor lock-in**|Moderate|Low-Moderate|Low|
|**Team size needed**|1 developer|1-2 developers|DevOps team|

---

## PaaS Platforms (Recommended for Starting)

For your Research Assistant, start here. You can always migrate to more complex platforms later.

### Railway

**Overview:**

- Visual dashboard + CLI
- GitHub integration with auto-deploy
- Built-in databases (PostgreSQL, Redis)
- Preview environments per PR
- Usage-based billing

**Pricing (2025-2026):**

- No free tier (shut down in 2023)
- Starts at $5/month base
- Usage: ~$0.000463/min for 1 vCPU, ~$0.000231/GB RAM/min
- Typical AI app: $10-25/month

**Deployment:**

```bash
# Install CLI
npm install -g @railway/cli

# Login and link project
railway login
railway link

# Deploy from local
railway up

# Or connect GitHub for auto-deploy
```

**Best for:** Quick prototypes, solo developers, startups wanting minimal ops

**Limitations:** Limited scaling controls, no GPU support, usage costs can spike with traffic

---

### Render

**Overview:**

- Heroku-like experience
- Managed PostgreSQL with backups
- Background workers and cron jobs
- Zero-downtime deploys
- Per-service pricing (predictable)

**Pricing (2025-2026):**

- Free tier (with limitations, services spin down)
- Starter: $7/month per service
- Standard: $25/month per service (more resources)
- Bandwidth: $30 per 100GB beyond included

**Deployment:**

```yaml
# render.yaml (Infrastructure as Code)
services:
  - type: web
    name: research-assistant
    runtime: docker
    dockerfilePath: ./Dockerfile
    envVars:
      - key: OPENAI_API_KEY
        sync: false  # Set in dashboard
    healthCheckPath: /health
```

**Best for:** Teams wanting stability, managed databases, predictable costs

**Limitations:** Services on free tier sleep after inactivity, less flexible than Railway

---

### Fly.io

**Overview:**

- Edge deployment (30+ global regions)
- Lightweight VMs (not containers)
- Low latency for global users
- CLI-first workflow
- Persistent volumes supported

**Pricing (2025-2026):**

- Pay-as-you-go (small free allowances)
- Shared CPU VMs start ~$2/month
- Dedicated CPU: ~$31/month for 1 CPU, 2GB RAM
- Bandwidth: 100GB free, then $0.02/GB

**Deployment:**

```bash
# Install CLI
curl -L https://fly.io/install.sh | sh

# Launch app (creates fly.toml)
fly launch

# Deploy
fly deploy

# Scale to multiple regions
fly scale count 2 --region iad,lhr
```

**Best for:** Latency-sensitive apps, global user base, edge computing

**Limitations:** CLI-only (no GUI for deploys), steeper learning curve, requires Docker knowledge

---

### Quick Comparison

|Aspect|Railway|Render|Fly.io|
|---|---|---|---|
|**Ease of use**|⭐⭐⭐⭐⭐|⭐⭐⭐⭐|⭐⭐⭐|
|**Pricing model**|Usage-based|Per-service|Usage-based|
|**Free tier**|No|Yes (limited)|Yes (limited)|
|**Global regions**|Limited|Single region|30+ regions|
|**Managed databases**|Yes|Yes (excellent)|Yes|
|**GUI dashboard**|Excellent|Good|Minimal|
|**Auto-deploy from Git**|Yes|Yes|Via GitHub Actions|
|**Preview environments**|Yes (built-in)|Yes (paid)|Manual|

---

## AI Application Specific Concerns

AI applications have unique deployment requirements that affect platform choice.

### Cold Start Problem

**What is it?** Serverless platforms (Lambda, Cloud Run with scale-to-zero) shut down containers when idle. The first request after idle triggers:

1. Container startup (1-5 seconds)
2. Python interpreter initialization (1-2 seconds)
3. Dependency loading (2-10 seconds)
4. Model loading if local (5-30 seconds)

**Total cold start for AI app: 5-30+ seconds**

```
REQUEST TIMELINE WITH COLD START
────────────────────────────────────────────────────────────────────

User Request 1 (after idle):
├─── Container start ────────┤ 3s
├─────── Python init ────────┤ 2s
├───────── Load deps ────────────────┤ 5s
├─────────── Load model ─────────────────────┤ 10s
├─────────────────── Process request ────────┤ 1s
└──────────────────────────────────────────────────────────────────►
                                                          21 seconds

User Request 2 (container warm):
├── Process request ──┤
└─────────────────────►
        1 second
```

**Solutions:**

|Solution|How It Works|Platform Support|
|---|---|---|
|**Keep-warm pings**|Scheduled requests prevent idle|Any (use external cron)|
|**Min instances**|Always keep N containers running|Cloud Run, Fargate|
|**Provisioned concurrency**|Pre-warmed Lambda instances|Lambda|
|**Always-on services**|Never scale to zero|Railway, Fly.io, Render (paid)|

**For Cloud Run:**

```yaml
# Prevent scale-to-zero
apiVersion: serving.knative.dev/v1
kind: Service
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"  # Always keep 1 instance
```

**For your Research Assistant:** If using OpenAI/Anthropic APIs (no local models), cold start is less severe (~5-10 seconds). If you need sub-second response, use always-on platforms (Railway, Render paid tier).

---

### Memory Requirements

AI applications need more RAM than typical web apps:

|Component|Memory|Notes|
|---|---|---|
|Python + FastAPI + Uvicorn|100-150MB|Baseline|
|LangChain / LangGraph|50-100MB|Framework overhead|
|ChromaDB (in-memory)|100MB-2GB|Depends on collection size|
|Embedding model (small)|200-500MB|e.g., all-MiniLM-L6-v2|
|Embedding model (large)|500MB-2GB|e.g., BGE-large|
|OpenAI client (no local model)|~50MB|API calls only|

**Typical Research Assistant (API-based):** 500MB-1GB **With local embedding model:** 1-2GB **With local LLM:** 4GB+ (usually not on PaaS)

**Platform Memory Limits:**

|Platform|Max Memory|Notes|
|---|---|---|
|AWS Lambda|10GB|Still may hit limits with large models|
|Cloud Run|32GB|Good for most AI apps|
|Railway|32GB (Pro)|8GB on Hobby|
|Render|4GB (standard)|Can request more|
|Fargate|120GB|Most flexible|

**Recommendation:** For API-based AI apps (OpenAI/Anthropic), 1-2GB is plenty. Size your container accordingly to save costs.

---

### GPU Access

**When do you need GPU?**

- Running local LLMs (Llama, Mistral)
- Running local embedding models (large ones)
- Image/video processing
- Training or fine-tuning

**When you DON'T need GPU:**

- Using OpenAI/Anthropic/Cohere APIs
- Using small embedding models on CPU
- Standard RAG with vector DB

**Platforms with GPU Support:**

|Platform|GPU Availability|Use Case|
|---|---|---|
|**Cloud Run**|NVIDIA GPUs (L4, A100)|Inference|
|**Modal**|Easy GPU provisioning|ML workloads|
|**Replicate**|API for GPU models|Model hosting|
|**AWS EC2 GPU**|Full control|Anything|
|**Banana/Baseten**|Serverless GPU|Inference|

**For your Research Assistant:** If using OpenAI/Anthropic APIs, you don't need GPU. Save the complexity and cost.

---

## Decision Framework

Use this flowchart to choose your platform:

```
START: What are your requirements?
│
├─► Just getting started / MVP / Learning?
│   └─► Railway or Render
│       • Minimal config
│       • Git push deploy
│       • $5-25/month
│
├─► Need global low latency?
│   └─► Fly.io
│       • Edge deployment
│       • 30+ regions
│       • CLI-based
│
├─► Need scaling + more control?
│   └─► Cloud Run or Fargate
│       • Auto-scaling
│       • Better observability
│       • $20-100+/month
│
├─► Event-driven / sporadic traffic?
│   └─► Lambda / Cloud Functions
│       • Pay per invocation
│       • Watch for cold starts
│       • Good for background jobs
│
├─► Large scale / complex system?
│   └─► Kubernetes (EKS/GKE)
│       • Full control
│       • Complex setup
│       • Need DevOps expertise
│
└─► Need GPU?
    └─► Modal, Replicate, or Cloud Run with GPU
        • Specialized platforms
        • Higher cost
        • For local model inference
```

### Quick Decision Matrix

|Your Situation|Recommended Platform|
|---|---|
|Solo developer, first deployment|Railway|
|Small team, need managed DB|Render|
|Global users, latency matters|Fly.io|
|Already on AWS, need scaling|Fargate or Cloud Run|
|Sporadic traffic, cost-sensitive|Lambda + keep-warm|
|Large team, complex microservices|Kubernetes|
|Local LLM inference|Modal or Replicate|

---

## Cost Estimation

Real costs for running an AI application in production.

### Platform Costs (Compute + Memory)

**Scenario:** Research Assistant with ~1000 requests/day, 1GB RAM, always-on

|Platform|Monthly Estimate|Notes|
|---|---|---|
|Railway|$15-25|Usage-based, varies with traffic|
|Render|$7-25|Per-service, predictable|
|Fly.io|$10-30|Depends on regions|
|Cloud Run|$20-50|Per-request + compute|
|Fargate|$30-60|Always-on compute|

### LLM API Costs (From Week 8)

This often dominates your bill:

|Model|Cost per 1M tokens|1000 req/day estimate|
|---|---|---|
|GPT-4o|$2.50 input / $10 output|$15-50/month|
|GPT-4o-mini|$0.15 input / $0.60 output|$1-5/month|
|Claude Sonnet|$3 input / $15 output|$20-60/month|
|Claude Haiku|$0.25 input / $1.25 output|$2-8/month|

### Storage Costs

|Service|Cost|Notes|
|---|---|---|
|Vector DB (hosted Qdrant)|$25-100/month|Managed service|
|Vector DB (self-hosted)|$5-20/month|Part of your container|
|PostgreSQL (managed)|$7-25/month|Render, Railway built-in|
|Redis (managed)|$5-15/month|Caching layer|
|Logs (external)|$10-50/month|Datadog, LogTail, etc.|

### Total Monthly Cost Examples

**Minimal Setup (Solo developer, learning):**

```
Railway:                $15
GPT-4o-mini API:        $5
ChromaDB (in-container): $0
─────────────────────────
Total:                  $20/month
```

**Production Setup (Small team, real users):**

```
Render (Standard):      $25
Redis:                  $7
GPT-4o API:             $30
Managed Qdrant:         $25
External logging:       $15
─────────────────────────
Total:                  $102/month
```

**Scaled Setup (Growing product):**

```
Cloud Run (2 instances): $60
Managed PostgreSQL:      $50
GPT-4o API (high volume): $200
Managed Qdrant:          $100
Observability (LangSmith): $39
─────────────────────────
Total:                   $449/month
```

---

## Cloud Run vs Fargate: Detailed Comparison

If you outgrow PaaS, these are the next step.

|Aspect|Cloud Run|AWS Fargate|
|---|---|---|
|**Cold start**|Yes (configurable min instances)|No (always-on)|
|**Scaling speed**|Very fast (seconds)|Slower (~40s for new tasks)|
|**GPU support**|Yes (L4, A100)|No|
|**Pricing**|Per-request + compute|vCPU/memory hours|
|**Setup complexity**|Lower|Higher (needs ECS/EKS)|
|**Load balancer**|Built-in|Separate ALB required|
|**Best for**|HTTP APIs, variable traffic|Long-running services, AWS ecosystem|

**Cloud Run is generally better for:**

- Variable/bursty traffic
- Simpler setup
- GPU needs
- Cost optimization (scale to zero)

**Fargate is generally better for:**

- Predictable traffic patterns
- Deep AWS integration
- Longer-running processes
- When you need other AWS services

---

## Practical Recommendations

### For Your Research Assistant

**Phase 1: Learning/MVP**

```
Platform: Railway
Why: Fastest to deploy, visual dashboard, built-in Redis
Cost: ~$15-25/month
```

**Phase 2: Real Users**

```
Platform: Render
Why: Better managed databases, predictable pricing, background workers
Cost: ~$50-100/month
```

**Phase 3: Scaling**

```
Platform: Cloud Run or Fly.io
Why: Auto-scaling, multi-region, better observability
Cost: ~$100-300/month
```

### Migration Path

The beauty of Docker: you can start on Railway, then move to Cloud Run, then to Kubernetes — your container works everywhere.

```
Railway (MVP)
    │
    ├── Working well? Stay here!
    │
    ▼ Need more scaling?
Render or Fly.io (Production)
    │
    ├── Working well? Stay here!
    │
    ▼ Need enterprise features?
Cloud Run / Fargate (Scale)
    │
    ├── Working well? Stay here!
    │
    ▼ Need full control?
Kubernetes (Enterprise)
```

---

## Sources Referenced

- Railway docs and pricing: https://docs.railway.com
- Railway vs Fly.io comparison: https://docs.railway.com/platform/compare-to-fly
- Render pricing and features: https://render.com
- Fly.io documentation: https://fly.io/docs
- Cloud Run vs Fargate analysis: Various current articles (2024-2026)
- Platform comparison blogs: Northflank, Elestio, codeYaan (2025-2026)

---

## What's Next

This note covered platform selection and AI-specific deployment concerns. The next note covers **Environment Management and Secrets** — how to handle configuration and sensitive data across environments.