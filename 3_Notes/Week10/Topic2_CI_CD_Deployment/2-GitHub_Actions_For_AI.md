# GitHub Actions for AI Applications

## Core Concepts

GitHub Actions is GitHub's built-in CI/CD platform. Before diving into syntax, understand the building blocks:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GITHUB ACTIONS HIERARCHY                              │
│                                                                              │
│   WORKFLOW (deploy.yml)                                                      │
│   └── JOB (test)                                                            │
│       └── STEP (Run pytest)                                                 │
│           └── ACTION or COMMAND                                             │
│                                                                              │
│   └── JOB (build)                                                           │
│       └── STEP (Build Docker image)                                         │
│       └── STEP (Push to registry)                                           │
│                                                                              │
│   └── JOB (deploy)                                                          │
│       └── STEP (Deploy to production)                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

|Concept|Definition|Analogy|
|---|---|---|
|**Workflow**|YAML file defining the entire automation|The recipe|
|**Job**|Set of steps that run on the same runner|A cooking station|
|**Step**|Individual command or action|One instruction|
|**Runner**|Machine that executes jobs|The kitchen|
|**Action**|Reusable unit from marketplace|A pre-made ingredient|

### Workflow

A workflow is a YAML file that defines what happens when a trigger fires. You can have multiple workflows:

```
.github/
└── workflows/
    ├── test.yml        # Run tests on every PR
    ├── deploy.yml      # Deploy on push to main
    └── nightly.yml     # Run evaluation suite nightly
```

### Job

Jobs run on separate runners (machines). By default, jobs run in parallel. Use `needs` to create dependencies.

```yaml
jobs:
  test:           # Runs first
    ...
  build:
    needs: test   # Waits for test to pass
    ...
  deploy:
    needs: build  # Waits for build to complete
    ...
```

### Step

Steps run sequentially within a job. Each step is either:

- A shell command: `run: pytest tests/`
- A reusable action: `uses: actions/checkout@v4`

### Runner

The machine executing your job. GitHub provides hosted runners:

|Runner|OS|Use Case|
|---|---|---|
|`ubuntu-latest`|Ubuntu 22.04|Most common, use by default|
|`ubuntu-24.04`|Ubuntu 24.04|Newer packages|
|`macos-latest`|macOS|iOS/macOS builds|
|`windows-latest`|Windows|Windows-specific testing|

### Action

Actions are reusable units from the GitHub Marketplace. Format: `owner/repo@version`

```yaml
# Common actions you'll use
- uses: actions/checkout@v4        # Clone your repo
- uses: actions/setup-python@v5    # Install Python
- uses: docker/build-push-action@v5  # Build and push Docker images
```

---

## Workflow File Structure

Every workflow file follows this structure:

```yaml
# .github/workflows/deploy.yml

name: Deploy Research Assistant    # Display name in GitHub UI

on:                                 # Trigger conditions
  push:
    branches: [main]

env:                                # Workflow-level environment variables
  PYTHON_VERSION: '3.11'

jobs:                               # Job definitions
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
```

Let's examine each section.

---

## Triggers: The `on` Block

Triggers define when your workflow runs.

### Push to Branch

```yaml
on:
  push:
    branches: [main]           # Only main branch
    
on:
  push:
    branches: [main, develop]  # Multiple branches
    
on:
  push:
    branches:
      - 'release/**'           # Pattern matching: release/v1, release/v2
```

### Pull Request

```yaml
on:
  pull_request:
    branches: [main]           # PRs targeting main
    
on:
  pull_request:
    types: [opened, synchronize, reopened]  # Specific PR events
```

### Manual Trigger

```yaml
on:
  workflow_dispatch:           # Adds "Run workflow" button in GitHub UI
    inputs:
      environment:
        description: 'Target environment'
        required: true
        default: 'staging'
        type: choice
        options:
          - staging
          - production
```

Access input in steps: `${{ github.event.inputs.environment }}`

### Scheduled

```yaml
on:
  schedule:
    - cron: '0 2 * * *'        # Daily at 2 AM UTC
    - cron: '0 */6 * * *'      # Every 6 hours
```

Cron format: `minute hour day-of-month month day-of-week`

### Combined Triggers

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
  schedule:
    - cron: '0 2 * * *'
```

---

## Environment Variables

Set variables at workflow, job, or step level:

```yaml
env:                              # Workflow level
  PYTHON_VERSION: '3.11'
  REGISTRY: ghcr.io

jobs:
  build:
    env:                          # Job level
      IMAGE_NAME: research-assistant
    steps:
      - name: Build
        env:                      # Step level
          BUILD_TARGET: production
        run: |
          echo "Python: $PYTHON_VERSION"
          echo "Image: $IMAGE_NAME"
          echo "Target: $BUILD_TARGET"
```

### GitHub Context Variables

GitHub provides built-in context:

```yaml
- run: |
    echo "Repository: ${{ github.repository }}"    # owner/repo
    echo "SHA: ${{ github.sha }}"                  # Full commit SHA
    echo "Branch: ${{ github.ref_name }}"          # Branch name
    echo "Actor: ${{ github.actor }}"              # User who triggered
    echo "Run ID: ${{ github.run_id }}"            # Unique run identifier
```

---

## Job Configuration

### Basic Job

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "Hello"
```

### Job Dependencies

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/

  build:
    needs: test                  # Only runs if test passes
    runs-on: ubuntu-latest
    steps:
      - run: docker build .

  deploy:
    needs: [test, build]         # Needs multiple jobs
    runs-on: ubuntu-latest
    steps:
      - run: ./deploy.sh
```

### Conditional Execution

```yaml
jobs:
  deploy:
    if: github.ref == 'refs/heads/main'   # Only on main branch
    runs-on: ubuntu-latest
    steps:
      - run: ./deploy.sh
      
  notify:
    if: failure()                          # Only if previous job failed
    needs: deploy
    runs-on: ubuntu-latest
    steps:
      - run: ./notify-slack.sh
```

Common conditions:

- `github.ref == 'refs/heads/main'` — on main branch
- `github.event_name == 'pull_request'` — triggered by PR
- `success()` — previous steps succeeded
- `failure()` — previous steps failed
- `always()` — run regardless of status

---

## Steps: Commands and Actions

### Running Shell Commands

```yaml
steps:
  - name: Single command
    run: pytest tests/
    
  - name: Multiple commands
    run: |
      pip install -r requirements.txt
      pytest tests/
      python -m mypy src/
      
  - name: With working directory
    run: pytest
    working-directory: ./backend
```

### Using Actions

```yaml
steps:
  - name: Checkout code
    uses: actions/checkout@v4
    
  - name: Setup Python
    uses: actions/setup-python@v5
    with:
      python-version: '3.11'
      cache: 'pip'                  # Cache pip dependencies
      
  - name: Setup Node
    uses: actions/setup-node@v4
    with:
      node-version: '20'
```

### Step Outputs

Steps can produce outputs for later steps:

```yaml
steps:
  - name: Get version
    id: version
    run: echo "version=$(cat VERSION)" >> $GITHUB_OUTPUT
    
  - name: Use version
    run: echo "Deploying version ${{ steps.version.outputs.version }}"
```

---

## Secrets Management

Secrets are encrypted values stored in repository settings.

### Storing Secrets

1. Go to repository → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Add name (e.g., `OPENAI_API_KEY`) and value

### Using Secrets

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Run tests
        run: pytest tests/
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

### Security Properties

- **Masked in logs**: If a secret value appears in output, it shows `***`
- **Not available in forks**: PRs from forks can't access secrets (security)
- **Scoped**: Repository secrets, environment secrets, organization secrets

### Common Secrets for AI Applications

|Secret|Purpose|
|---|---|
|`OPENAI_API_KEY`|LLM API calls in tests|
|`ANTHROPIC_API_KEY`|Alternative LLM provider|
|`DOCKER_USERNAME`|Push to Docker Hub|
|`DOCKER_PASSWORD`|Push to Docker Hub|
|`GITHUB_TOKEN`|Auto-provided for GitHub operations|

Note: `GITHUB_TOKEN` is automatically available—you don't need to create it.

---

## Complete Workflow Example

Here's a production-ready workflow for an AI application:

```yaml
# .github/workflows/deploy.yml
name: Test, Build, and Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Deploy environment'
        required: true
        default: 'staging'
        type: choice
        options:
          - staging
          - production

env:
  PYTHON_VERSION: '3.11'
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # ============================================
  # JOB 1: Test
  # ============================================
  test:
    name: Run Tests
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov mypy ruff
      
      - name: Lint with ruff
        run: ruff check src/
      
      - name: Type check with mypy
        run: mypy src/ --ignore-missing-imports
      
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=src --cov-report=xml
      
      - name: Run integration tests
        run: pytest tests/integration/ -v
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

  # ============================================
  # JOB 2: Build
  # ============================================
  build:
    name: Build Docker Image
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || github.event_name == 'workflow_dispatch'
    
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=
            type=ref,event=branch
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ============================================
  # JOB 3: Deploy
  # ============================================
  deploy:
    name: Deploy to Environment
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || github.event_name == 'workflow_dispatch'
    
    environment:
      name: ${{ github.event.inputs.environment || 'staging' }}
      url: ${{ steps.deploy.outputs.url }}
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Deploy to environment
        id: deploy
        run: |
          # Platform-specific deployment
          # Example: railway up, flyctl deploy, kubectl apply
          echo "Deploying ${{ needs.build.outputs.image_tag }}"
          echo "url=https://research-assistant-staging.example.com" >> $GITHUB_OUTPUT
        env:
          DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}
      
      - name: Verify deployment
        run: |
          # Wait for deployment to be ready
          sleep 30
          curl -f ${{ steps.deploy.outputs.url }}/health || exit 1

  # ============================================
  # JOB 4: Notify (only on failure)
  # ============================================
  notify:
    name: Notify on Failure
    needs: [test, build, deploy]
    runs-on: ubuntu-latest
    if: failure()
    
    steps:
      - name: Send Slack notification
        run: |
          curl -X POST ${{ secrets.SLACK_WEBHOOK }} \
            -H 'Content-type: application/json' \
            -d '{"text":"❌ Deployment failed for ${{ github.repository }}"}'
```

### Workflow Visualization

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WORKFLOW EXECUTION                                 │
│                                                                              │
│   ┌─────────┐                                                               │
│   │  TEST   │  Always runs (PR or push)                                     │
│   │         │  - Lint, type check                                           │
│   │         │  - Unit tests                                                 │
│   │         │  - Integration tests (with API keys)                          │
│   └────┬────┘                                                               │
│        │ needs: test                                                        │
│        ▼                                                                    │
│   ┌─────────┐                                                               │
│   │  BUILD  │  Only on main branch or manual trigger                        │
│   │         │  - Build Docker image                                         │
│   │         │  - Push to GHCR                                               │
│   │         │  - Output: image tag                                          │
│   └────┬────┘                                                               │
│        │ needs: build                                                       │
│        ▼                                                                    │
│   ┌─────────┐                                                               │
│   │ DEPLOY  │  Only on main branch or manual trigger                        │
│   │         │  - Deploy to staging/production                               │
│   │         │  - Verify health                                              │
│   └────┬────┘                                                               │
│        │ if: failure()                                                      │
│        ▼                                                                    │
│   ┌─────────┐                                                               │
│   │ NOTIFY  │  Only if any job failed                                       │
│   │         │  - Send Slack alert                                           │
│   └─────────┘                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## AI-Specific CI/CD Patterns

### Pattern 1: Integration Tests with LLM APIs

The expensive question: use real APIs or mock?

```yaml
jobs:
  test-unit:
    # Fast, free, always run
    steps:
      - name: Unit tests (mocked)
        run: pytest tests/unit/ -v
        # These tests mock LLM responses
        
  test-integration:
    # Slow, costs money, run selectively
    if: github.ref == 'refs/heads/main'  # Only on main
    steps:
      - name: Integration tests (real API)
        run: pytest tests/integration/ -v
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

**Mocking Strategy** (in your test code):

```python
# tests/unit/test_agent.py
from unittest.mock import patch

@patch('openai.OpenAI')
def test_agent_response(mock_client):
    # Configure mock
    mock_client.return_value.responses.create.return_value.output_text = "Test response"
    
    # Test your code
    result = agent.process("test query")
    assert result == "Test response"
```

### Pattern 2: Evaluation as CI Step

Run your evaluation suite as a quality gate:

```yaml
jobs:
  evaluate:
    name: Run Evaluation Suite
    needs: test
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run retrieval evaluation
        run: |
          python -m evaluation.retrieval \
            --dataset tests/fixtures/eval_dataset.json \
            --threshold 0.7
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      
      - name: Run response quality evaluation
        run: |
          python -m evaluation.response \
            --dataset tests/fixtures/response_eval.json \
            --threshold 0.8
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      
      - name: Upload evaluation report
        uses: actions/upload-artifact@v4
        with:
          name: evaluation-report
          path: evaluation_results/
```

### Pattern 3: Prompt Validation

Validate prompts don't break formatting:

```yaml
- name: Validate prompts
  run: |
    python -c "
    from src.prompts import SYSTEM_PROMPT, USER_TEMPLATE
    
    # Check prompts are valid strings
    assert isinstance(SYSTEM_PROMPT, str), 'SYSTEM_PROMPT must be string'
    assert len(SYSTEM_PROMPT) > 0, 'SYSTEM_PROMPT cannot be empty'
    
    # Check templates have required placeholders
    assert '{query}' in USER_TEMPLATE, 'USER_TEMPLATE must contain {query}'
    assert '{context}' in USER_TEMPLATE, 'USER_TEMPLATE must contain {context}'
    
    print('✅ Prompt validation passed')
    "
```

### Pattern 4: Vector DB in CI

If tests need a vector database:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      # Spin up Qdrant for tests
      qdrant:
        image: qdrant/qdrant:latest
        ports:
          - 6333:6333
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Run tests
        run: pytest tests/
        env:
          QDRANT_URL: http://localhost:6333
```

For ChromaDB (in-memory), no service needed:

```python
# tests/conftest.py
import chromadb

@pytest.fixture
def chroma_client():
    # Ephemeral in-memory client for tests
    return chromadb.Client()
```

### Pattern 5: Nightly Full Evaluation

```yaml
# .github/workflows/nightly-eval.yml
name: Nightly Evaluation

on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily

jobs:
  full-evaluation:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run full evaluation suite
        run: python -m evaluation.full_suite
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      
      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: nightly-eval-${{ github.run_id }}
          path: evaluation_results/
      
      - name: Post results to Slack
        if: always()
        run: |
          python scripts/post_eval_results.py
        env:
          SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}
```

---

## Common Patterns and Tips

### Caching Dependencies

Speed up workflows by caching:

```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'                    # Cache pip packages
    cache-dependency-path: |
      requirements.txt
      requirements-dev.txt
```

### Matrix Testing

Test across multiple Python versions:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pytest tests/
```

### Timeout

Prevent runaway jobs:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 30          # Kill job after 30 minutes
```

### Continue on Error

```yaml
steps:
  - name: Non-critical step
    continue-on-error: true      # Don't fail workflow if this fails
    run: ./optional-check.sh
```

---

## Debugging Workflows

### View Logs

1. Go to repository → Actions tab
2. Click on workflow run
3. Click on job → step to see logs

### Enable Debug Logging

Add repository secret:

- `ACTIONS_STEP_DEBUG` = `true`

### Run Locally with `act`

Test workflows locally before pushing:

```bash
# Install act
brew install act

# Run workflow
act push

# Run specific job
act -j test
```

---

## Key Takeaways

1. **Workflow structure**: `on` (triggers) → `env` (variables) → `jobs` (execution units) → `steps` (commands)
    
2. **Jobs run in parallel by default**; use `needs` to create dependencies
    
3. **Secrets are stored in GitHub Settings** and accessed via `${{ secrets.NAME }}`
    
4. **Conditional execution**: Use `if` to control when jobs/steps run
    
5. **AI-specific patterns**:
    
    - Mock LLM calls in unit tests, real calls in integration tests (selectively)
    - Run evaluation as a CI step with pass/fail thresholds
    - Validate prompts don't break formatting
    - Use nightly builds for expensive full evaluations
6. **Use caching** to speed up dependency installation
    
7. **Set timeouts** to prevent runaway jobs
    

---

## What's Next

Note 3 covers **deployment strategies**—how to actually ship your code to production safely. Blue-green, canary, rolling deployments, and when to use each.