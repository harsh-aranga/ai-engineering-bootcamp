# CI/CD Pipeline Anatomy: From Push to Production

## What Problem Does CI/CD Solve?

Manual deployment follows a familiar, painful pattern:

```
SSH into server → git pull → pip install → restart service → pray
```

This approach has predictable failure modes:

|Problem|Symptom|
|---|---|
|**Error-prone**|Forgot to run migrations. Missed an environment variable. Wrong branch.|
|**Slow**|Each deployment takes 15-30 minutes of human attention|
|**Scary**|"Last time I deployed, it broke for 2 hours"|
|**Unauditable**|"Who deployed this? When? What changed?"|
|**Inconsistent**|Developer A deploys differently than Developer B|

CI/CD replaces this with automation:

```
Push code → Tests run automatically → Deploy if tests pass → Monitor
```

Every deployment becomes:

- **Reproducible**: Same process every time
- **Fast**: Minutes, not hours
- **Auditable**: Git history + pipeline logs = complete record
- **Reversible**: Rollback is one click (or automatic)

---

## CI vs CD: Two Distinct Concepts

These terms are often conflated, but they solve different problems.

### Continuous Integration (CI)

**Goal**: Catch bugs before they reach production.

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONTINUOUS INTEGRATION                       │
│                                                                  │
│   Developer A ──┐                                                │
│                 │      ┌─────────┐     ┌─────────┐              │
│   Developer B ──┼─────▶│  BUILD  │────▶│  TEST   │──▶ Pass/Fail │
│                 │      └─────────┘     └─────────┘              │
│   Developer C ──┘                                                │
│                                                                  │
│   Everyone integrates frequently. No "big bang" merges.         │
└─────────────────────────────────────────────────────────────────┘
```

CI answers: "Does this code work with everyone else's code?"

Key practices:

- Every push triggers build + test
- Tests must pass before merge
- Integration happens daily (not monthly)
- Broken builds are fixed immediately

### Continuous Delivery vs Continuous Deployment (CD)

These two terms differ in one critical way:

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTINUOUS DELIVERY                           │
│                                                                  │
│   Tests Pass ──▶ Deploy to Staging ──▶ [MANUAL APPROVAL] ──▶ Prod│
│                                              │                   │
│                              Human decides when to release       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   CONTINUOUS DEPLOYMENT                          │
│                                                                  │
│   Tests Pass ──▶ Deploy to Staging ──▶ Deploy to Production     │
│                                                                  │
│                      Fully automated. No human gate.             │
└─────────────────────────────────────────────────────────────────┘
```

|Aspect|Continuous Delivery|Continuous Deployment|
|---|---|---|
|Staging deploy|Automatic|Automatic|
|Production deploy|Manual approval|Automatic|
|Release frequency|When business decides|Every passing commit|
|Risk tolerance|Lower|Higher|
|Typical adopters|Enterprises, regulated industries|SaaS, startups|

**Progression path**: Most teams start with Continuous Delivery (manual prod gate), then move to Continuous Deployment as confidence grows.

---

## Pipeline Stages: The Assembly Line

A CI/CD pipeline is a series of stages, each with a specific purpose:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CI/CD PIPELINE STAGES                             │
│                                                                              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐   │
│  │  CODE   │───▶│  BUILD  │───▶│  TEST   │───▶│ DEPLOY  │───▶│ MONITOR │   │
│  │         │    │         │    │         │    │         │    │         │   │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘   │
│                                                                              │
│  Developer      Create         Run tests     Push to       Verify           │
│  pushes to      artifacts      and lint      environment   health           │
│  branch                                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Stage 1: Code

**Trigger**: Developer pushes to repository.

This is the entry point. The pipeline activates based on configured triggers.

### Stage 2: Build

**Purpose**: Create deployable artifacts.

For a Python AI application:

- Install dependencies
- Build Docker image
- Tag with version identifier

```dockerfile
# What gets built
FROM python:3.11-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ /app/src/
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0"]
```

The output is an **artifact**—a versioned, immutable package ready for deployment.

### Stage 3: Test

**Purpose**: Validate correctness before deployment.

Test types in order of execution:

|Test Type|What It Validates|Speed|Flakiness|
|---|---|---|---|
|**Linting**|Code style, syntax|Seconds|None|
|**Unit tests**|Individual functions|Seconds|Low|
|**Integration tests**|Components together|Minutes|Medium|
|**End-to-end tests**|Full user flows|Minutes|Higher|

If any test fails, the pipeline stops. No deployment.

### Stage 4: Deploy

**Purpose**: Push artifact to target environment.

Deployment targets (in order of risk):

1. **Development**: Automatic on every push
2. **Staging**: Automatic, mirrors production
3. **Production**: Automatic or manual gate

### Stage 5: Monitor

**Purpose**: Verify the deployment is healthy.

Post-deploy checks:

- Health endpoint returns 200
- Error rate within threshold
- Latency within threshold
- Key business metrics stable

If monitoring detects problems, rollback triggers (covered in Note 4).

---

## Pipeline Triggers: When Does It Run?

Pipelines don't run continuously—they activate on specific events:

### Push to Branch

```yaml
# Trigger on any push to main
on:
  push:
    branches: [main]
```

Use for: Deploying to staging/production when code is merged.

### Pull Request

```yaml
# Trigger when PR is opened or updated
on:
  pull_request:
    branches: [main]
```

Use for: Running tests before merge. Prevents broken code from reaching main.

### Manual Trigger

```yaml
# Trigger manually from UI
on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        default: 'staging'
```

Use for: Production releases in Continuous Delivery model. Emergency deployments.

### Scheduled

```yaml
# Run nightly at 2 AM UTC
on:
  schedule:
    - cron: '0 2 * * *'
```

Use for: Nightly builds. Periodic test runs against external APIs. Dependency updates.

### Trigger Strategy for AI Applications

```
┌─────────────────────────────────────────────────────────────────┐
│                    TYPICAL TRIGGER STRATEGY                      │
│                                                                  │
│   Pull Request ──▶ Run tests (no deploy)                        │
│                                                                  │
│   Push to main ──▶ Run tests ──▶ Deploy to staging              │
│                                                                  │
│   Manual trigger ──▶ Deploy staging to production               │
│                                                                  │
│   Nightly ──▶ Run full evaluation suite                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Artifacts and Registries: Versioned Packages

### What Is an Artifact?

An artifact is the deployable output of your build stage. For containerized applications, this is typically a Docker image.

```
┌─────────────────────────────────────────────────────────────────┐
│                        BUILD ARTIFACTS                           │
│                                                                  │
│   Source Code ──▶ Build Process ──▶ Artifact                    │
│                                                                  │
│   Python app        docker build      myapp:abc123def           │
│   + Dockerfile      -t myapp:...      (Docker image)            │
│   + requirements                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Container Registries

Artifacts are stored in registries—version-controlled storage for images.

|Registry|Integrated With|Cost|
|---|---|---|
|GitHub Container Registry (ghcr.io)|GitHub|Free tier generous|
|Docker Hub|Universal|Free with limits|
|Amazon ECR|AWS|Pay per storage|
|Google Artifact Registry|GCP|Pay per storage|

### Tagging Strategy

Tags identify specific versions of your artifact:

```
myapp:latest           # ❌ Mutable. Don't use for production.
myapp:v1.2.3           # ✅ Semantic version
myapp:abc123def        # ✅ Git SHA (most common)
myapp:main-abc123def   # ✅ Branch + SHA
```

**Critical principle**: Same tag must always reference same artifact.

```
# Good: Tag with git SHA
docker build -t myapp:${GITHUB_SHA} .

# Why: If commit abc123 is deployed and breaks,
# you can redeploy abc122 and get exactly the previous state.
```

### Immutability

Once an artifact is pushed with a tag, that tag should never be overwritten.

```
# Day 1: Push myapp:v1.0.0 (contains bug)
# Day 2: Fix bug, push myapp:v1.0.0 again  ← WRONG

# Correct approach:
# Day 1: Push myapp:v1.0.0 (contains bug)
# Day 2: Fix bug, push myapp:v1.0.1        ← NEW VERSION
```

Immutability enables reliable rollback. If v1.0.1 breaks, you can deploy v1.0.0 and know exactly what you're getting.

---

## AI Application Pipeline Considerations

AI applications have unique CI/CD concerns that traditional web apps don't face.

### API Keys in Tests

Your tests may need to call LLM APIs. Options:

|Approach|Pros|Cons|
|---|---|---|
|**Mock responses**|Fast, free, deterministic|Doesn't catch API changes|
|**Real API calls**|Catches real issues|Slow, costs money, flaky|
|**Record/replay**|Fast after first run, realistic|Stale recordings|

**Practical approach**: Mock for unit tests, real calls for integration tests (run less frequently).

```yaml
# Store API keys as repository secrets
env:
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

### Prompt Changes Are Code Changes

A one-word prompt change can break your entire application.

```python
# Version 1: Works
SYSTEM_PROMPT = "You are a helpful research assistant."

# Version 2: Breaks everything
SYSTEM_PROMPT = "You are a helpful research assistant. Always respond in JSON."
```

Prompts should:

- Live in version control (not databases)
- Trigger CI/CD pipeline when changed
- Be tested before deployment

### Model Files: Separate from Application

Large model files (fine-tuned weights, embedding models) shouldn't be in your Docker image:

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODEL FILE STRATEGY                           │
│                                                                  │
│   ❌ WRONG: Model in Docker image                               │
│   - Image size: 5GB+                                            │
│   - Every code change = rebuild huge image                      │
│   - Model update = rebuild and redeploy app                     │
│                                                                  │
│   ✅ RIGHT: Model in external storage                           │
│   - Image size: 200MB                                           │
│   - App pulls model at startup (or on-demand)                   │
│   - Model update = change config, no app rebuild                │
└─────────────────────────────────────────────────────────────────┘
```

For cloud-hosted models (OpenAI, Anthropic), this isn't an issue—you're calling an API.

### Evaluation Suite in CI

Traditional apps have unit tests. AI apps need evaluation:

```yaml
jobs:
  test:
    steps:
      - name: Unit tests
        run: pytest tests/unit/
      
      - name: Integration tests
        run: pytest tests/integration/
      
      # AI-specific: evaluation
      - name: Retrieval evaluation
        run: python -m evaluation.retrieval --threshold 0.7
      
      - name: Response quality evaluation
        run: python -m evaluation.response --threshold 0.8
```

**Trade-off**: Full evaluation is slow and costs money. Options:

- Run full eval nightly, minimal eval on every push
- Run full eval only on main branch
- Run full eval manually before production deploy

---

## Pipeline Platforms Overview

You don't need to master every platform. Pick one and learn it well.

|Platform|Best For|Complexity|Cost|
|---|---|---|---|
|**GitHub Actions**|GitHub repos|Low|Generous free tier|
|**GitLab CI**|GitLab repos|Low|Free tier available|
|**CircleCI**|Any Git host|Medium|Limited free tier|
|**Jenkins**|Self-hosted, complex needs|High|Free (self-hosted)|
|**Railway/Render/Fly.io**|Simple deploys|Very Low|Included with platform|

### Decision Framework

```
┌─────────────────────────────────────────────────────────────────┐
│              CHOOSING A CI/CD PLATFORM                           │
│                                                                  │
│   Using GitHub? ──▶ GitHub Actions (obvious choice)             │
│                                                                  │
│   Using GitLab? ──▶ GitLab CI (built-in)                        │
│                                                                  │
│   Need self-hosted? ──▶ Jenkins (or GitLab self-hosted)         │
│                                                                  │
│   Simple PaaS deploy? ──▶ Use platform's built-in               │
│   (Railway, Render)       (often triggered by git push)         │
│                                                                  │
│   Enterprise with existing tooling? ──▶ Use what they have      │
└─────────────────────────────────────────────────────────────────┘
```

For this bootcamp, we focus on **GitHub Actions**—it's the most common choice for new projects and has the gentlest learning curve.

---

## Key Takeaways

1. **CI/CD replaces manual deployment** with automated, reproducible pipelines
2. **CI catches bugs early** through automatic testing on every push
3. **CD automates deployment**—Delivery has a manual gate, Deployment is fully automatic
4. **Pipelines have five stages**: Code → Build → Test → Deploy → Monitor
5. **Triggers control when pipelines run**: push, PR, manual, scheduled
6. **Artifacts are immutable, versioned packages** stored in registries
7. **AI apps need special consideration**: API keys in tests, prompts as code, model file separation, evaluation suites
8. **Pick one platform and learn it well**—GitHub Actions is the default choice for most teams

---

## What's Next

Note 2 covers **GitHub Actions syntax**—the practical implementation of these concepts. You'll see how pipeline stages, triggers, and artifacts translate into workflow YAML.