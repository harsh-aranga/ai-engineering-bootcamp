# Note 3: Prompt Versioning and Management

## Why Prompts Need Versioning

Prompts are deceptively simple — just text. But that text controls your application's behavior as much as code does.

**The problem:**

```python
# Version 1
SYSTEM_PROMPT = "You are a helpful assistant. Answer questions concisely."

# Version 2 — "minor" change
SYSTEM_PROMPT = "You are a helpful assistant. Answer questions concisely, with examples."

# Output: Completely different response length, structure, and style
```

A single word can break structured output:

```python
# Works: Returns valid JSON
"Respond with a JSON object containing 'answer' and 'confidence'."

# Breaks: Model adds explanation before JSON
"Respond with a JSON object containing 'answer' and 'confidence'. Be thorough."
```

**Why versioning matters:**

|Need|Without Versioning|With Versioning|
|---|---|---|
|Rollback|"What was the old prompt?"|Restore v2.1 exactly|
|Compare|"What changed?"|Diff v2.1 vs v2.2|
|Audit|"Who changed it and when?"|Full change history|
|Debug|"Why is output different?"|Trace to exact prompt version|
|Test|"Does new prompt work better?"|A/B test v2.1 vs v2.2|

**The principle:** Prompts are code. Treat them as such.

---

## Storage Approaches

Three main approaches, each with tradeoffs:

### 1. Files in Git

Store prompts as text files, versioned with your code.

```
prompts/
├── system/
│   └── assistant.txt
├── rag/
│   └── qa_prompt.txt
└── classification/
    └── intent_classifier.txt
```

**Pros:**

- Versioned with code (same commit = same prompt)
- PR review for changes
- Free, no dependencies
- Works for most teams

**Cons:**

- Changes require deployment
- Non-engineers need git access
- No hot reload

**Best for:** Teams where engineers own prompts, deployments are fast.

### 2. Database with Versions

Store prompts in a database with version tracking.

```sql
CREATE TABLE prompts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255),
    UNIQUE(name, version)
);

-- Example data
INSERT INTO prompts (name, version, content, is_active) VALUES
('system_prompt', 'v2.0', 'You are a helpful assistant...', false),
('system_prompt', 'v2.1', 'You are a helpful assistant. Be concise...', true);
```

**Pros:**

- Hot reload without deployment
- Version history in one place
- Can add metadata (who, when, why)

**Cons:**

- More infrastructure
- Need to build management UI
- Must handle cache invalidation

**Best for:** Teams needing hot-swap capability, non-engineer prompt editors.

### 3. Prompt Management Tools

Dedicated tools: LangSmith Prompt Hub, Weights & Biases Prompts, etc.

**LangSmith Prompt Hub** (per current docs):

- Central repository for prompts with automatic versioning
- Every push creates a commit hash for that exact version
- Pull specific versions: `client.pull_prompt("my-prompt:abc123")`
- Playground for interactive testing
- Integrates with LangChain tracing

```python
# Push a prompt to LangSmith Hub
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate

client = Client()

prompt = ChatPromptTemplate([
    ("system", "You are a helpful assistant."),
    ("user", "{question}"),
])

client.push_prompt("my-assistant-prompt", object=prompt)

# Pull specific version
prompt = client.pull_prompt("my-assistant-prompt:abc123def")
```

**Pros:**

- UI for non-engineers
- Built-in testing/playground
- Collaboration features
- Version history automatic

**Cons:**

- External dependency
- Learning curve
- May not fit all workflows

**Best for:** Teams with non-engineer prompt editors, need collaboration features.

---

## File-Based Versioning Implementation

For most teams, file-based versioning is the right starting point:

### Directory Structure Options

**Option A: Directory per version**

```
prompts/
├── v2.0/
│   ├── system.txt
│   └── rag_qa.txt
├── v2.1/
│   ├── system.txt
│   └── rag_qa.txt
└── active.txt  # Contains "v2.1"
```

**Option B: Single file, git handles history**

```
prompts/
├── system.txt
├── rag_qa.txt
└── classification.txt
```

Git tracks history. To get old version: `git show HEAD~5:prompts/system.txt`

**Option A is better** — you can have multiple versions deployed simultaneously for A/B testing, and rollback is just changing a pointer.

### PromptManager Implementation

```python
# prompts/manager.py

from pathlib import Path
from typing import Optional, Dict
import os


class PromptManager:
    """
    Manages versioned prompts stored in files.
    
    Directory structure:
        prompts/
        ├── v2.0/
        │   ├── system.txt
        │   └── rag_qa.txt
        └── v2.1/
            ├── system.txt
            └── rag_qa.txt
    
    Usage:
        manager = PromptManager("prompts/")
        prompt = manager.get("system", version="v2.1")
        
        # Or use active version
        prompt = manager.get("system")  # Uses version from PROMPT_VERSION env var
    """
    
    def __init__(
        self,
        base_path: str = "prompts/",
        default_version: Optional[str] = None,
    ):
        self.base_path = Path(base_path)
        
        # Version priority: explicit > env var > default
        self.default_version = (
            default_version
            or os.getenv("PROMPT_VERSION")
            or self._detect_active_version()
        )
        
        self._cache: Dict[str, str] = {}
    
    def _detect_active_version(self) -> str:
        """Find the active version from active.txt or latest directory."""
        active_file = self.base_path / "active.txt"
        if active_file.exists():
            return active_file.read_text().strip()
        
        # Fall back to latest version directory
        versions = sorted([
            d.name for d in self.base_path.iterdir()
            if d.is_dir() and d.name.startswith("v")
        ])
        if versions:
            return versions[-1]
        
        raise ValueError(f"No prompt versions found in {self.base_path}")
    
    def get(
        self,
        name: str,
        version: Optional[str] = None,
        use_cache: bool = True,
    ) -> str:
        """
        Get prompt content by name.
        
        Args:
            name: Prompt name (without .txt extension)
            version: Specific version (e.g., "v2.1"). Uses default if None.
            use_cache: Whether to cache loaded prompts
        
        Returns:
            Prompt content as string
        """
        version = version or self.default_version
        cache_key = f"{version}:{name}"
        
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]
        
        # Try with and without .txt extension
        prompt_path = self.base_path / version / f"{name}.txt"
        if not prompt_path.exists():
            prompt_path = self.base_path / version / name
        
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Prompt '{name}' not found in version '{version}'. "
                f"Looked in: {prompt_path}"
            )
        
        content = prompt_path.read_text()
        
        if use_cache:
            self._cache[cache_key] = content
        
        return content
    
    def render(
        self,
        name: str,
        variables: Dict[str, str],
        version: Optional[str] = None,
    ) -> str:
        """
        Get prompt and fill in variables.
        
        Prompt file uses {variable_name} syntax:
            "Answer the question about {topic} in {style} style."
        
        Usage:
            prompt = manager.render("qa", {"topic": "Python", "style": "concise"})
        """
        template = self.get(name, version)
        return template.format(**variables)
    
    def list_versions(self) -> list[str]:
        """List all available versions."""
        return sorted([
            d.name for d in self.base_path.iterdir()
            if d.is_dir() and d.name.startswith("v")
        ])
    
    def list_prompts(self, version: Optional[str] = None) -> list[str]:
        """List all prompts in a version."""
        version = version or self.default_version
        version_path = self.base_path / version
        
        return sorted([
            f.stem for f in version_path.iterdir()
            if f.is_file() and f.suffix == ".txt"
        ])
    
    def clear_cache(self):
        """Clear the prompt cache."""
        self._cache.clear()


# Global instance for convenience
_manager: Optional[PromptManager] = None


def get_prompt(name: str, version: Optional[str] = None) -> str:
    """Convenience function using global manager."""
    global _manager
    if _manager is None:
        _manager = PromptManager()
    return _manager.get(name, version)
```

**Usage:**

```python
from prompts.manager import PromptManager, get_prompt

# Explicit instantiation
manager = PromptManager("prompts/")
system_prompt = manager.get("system", version="v2.1")

# With variable substitution
qa_prompt = manager.render(
    "rag_qa",
    {"context": retrieved_context, "question": user_question},
    version="v2.1"
)

# Convenience function (uses env var for version)
# Set PROMPT_VERSION=v2.1 in environment
system_prompt = get_prompt("system")
```

---

## Version Scheme

Three common approaches:

### Semantic Versioning (Recommended)

```
v{major}.{minor}.{patch}

v2.0.0 → v2.1.0 → v2.1.1
```

|Change Type|Version Bump|Example|
|---|---|---|
|**Major**|Breaking changes|Output format change, behavior reversal|
|**Minor**|Behavior change|Added instructions, new constraints|
|**Patch**|No behavior change|Typo fix, clarification|

**Example:**

```
v1.0.0: "You are a helpful assistant."
v1.1.0: "You are a helpful assistant. Be concise."  # Behavior change
v1.1.1: "You are a helpful assistant. Be concise." # Typo fix (none in this case)
v2.0.0: "You are a technical expert. Respond in JSON format."  # Breaking change
```

### Date-Based Versioning

```
{YYYY}-{MM}-{DD}

2024-01-15 → 2024-02-03 → 2024-02-10
```

**Pros:** Clear when each version was created **Cons:** Doesn't communicate significance of change

**Best for:** Rapidly iterating prompts, audit-heavy environments.

### Simple Increment

```
v1 → v2 → v3
```

**Pros:** Simple **Cons:** Doesn't communicate change type

**Best for:** Small projects, few prompts.

---

## The Active Version Concept

Multiple versions exist; one is "active" (what production uses):

```
prompts/
├── v2.0/           # Old version (kept for rollback)
├── v2.1/           # Another old version
├── v2.2/           # Current active version ← production uses this
├── v2.3/           # New version (testing)
└── active.txt      # Contains "v2.2"
```

**Why this matters:**

```python
# Production code always uses active version
prompt = manager.get("system")  # Gets v2.2

# Testing code can specify version
prompt = manager.get("system", version="v2.3")  # Test new version

# Promotion is just updating active.txt
# No code change, no deployment
```

**Implementation:**

```python
# prompts/active.txt
v2.2
```

```python
def set_active_version(self, version: str) -> None:
    """Promote a version to active."""
    version_path = self.base_path / version
    if not version_path.exists():
        raise ValueError(f"Version {version} does not exist")
    
    active_file = self.base_path / "active.txt"
    active_file.write_text(version)
    
    self.clear_cache()  # Important: clear cache after promotion
    self.default_version = version
```

---

## Prompt Registry Pattern

For larger systems, a full registry provides more control:

```python
# prompts/registry.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List
import json
from pathlib import Path


@dataclass
class PromptVersion:
    """Metadata about a prompt version."""
    name: str
    version: str
    content: str
    created_at: datetime
    created_by: str
    description: Optional[str] = None
    model_affinity: Optional[str] = None  # Which model this was optimized for


@dataclass
class PromptAuditEntry:
    """Audit log entry for prompt changes."""
    timestamp: datetime
    action: str  # "created", "promoted", "deprecated"
    name: str
    version: str
    actor: str
    details: Optional[str] = None


class PromptRegistry:
    """
    Central registry for all prompts with full lifecycle management.
    
    Features:
    - Version management (create, get, list)
    - Active version tracking
    - Audit logging
    - Model affinity tracking
    """
    
    def __init__(self, storage_path: str = "prompts/"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        self._metadata_file = self.storage_path / "metadata.json"
        self._audit_file = self.storage_path / "audit.jsonl"
        
        self._load_metadata()
    
    def _load_metadata(self):
        """Load prompt metadata from file."""
        if self._metadata_file.exists():
            self._metadata = json.loads(self._metadata_file.read_text())
        else:
            self._metadata = {"active_versions": {}, "prompts": {}}
    
    def _save_metadata(self):
        """Save prompt metadata to file."""
        self._metadata_file.write_text(json.dumps(self._metadata, indent=2))
    
    def _log_audit(self, entry: PromptAuditEntry):
        """Append to audit log."""
        with open(self._audit_file, "a") as f:
            f.write(json.dumps({
                "timestamp": entry.timestamp.isoformat(),
                "action": entry.action,
                "name": entry.name,
                "version": entry.version,
                "actor": entry.actor,
                "details": entry.details,
            }) + "\n")
    
    def register(
        self,
        name: str,
        version: str,
        content: str,
        created_by: str,
        description: Optional[str] = None,
        model_affinity: Optional[str] = None,
    ) -> PromptVersion:
        """
        Register a new prompt version.
        
        Args:
            name: Prompt identifier (e.g., "system_prompt", "rag_qa")
            version: Version string (e.g., "v2.1.0")
            content: The prompt text
            created_by: Who created this version
            description: What changed in this version
            model_affinity: Which model this was optimized for
        
        Returns:
            PromptVersion object
        """
        # Store the prompt content
        version_dir = self.storage_path / version
        version_dir.mkdir(exist_ok=True)
        
        prompt_file = version_dir / f"{name}.txt"
        prompt_file.write_text(content)
        
        # Update metadata
        if name not in self._metadata["prompts"]:
            self._metadata["prompts"][name] = {"versions": []}
        
        self._metadata["prompts"][name]["versions"].append({
            "version": version,
            "created_at": datetime.utcnow().isoformat(),
            "created_by": created_by,
            "description": description,
            "model_affinity": model_affinity,
        })
        
        self._save_metadata()
        
        # Audit log
        self._log_audit(PromptAuditEntry(
            timestamp=datetime.utcnow(),
            action="created",
            name=name,
            version=version,
            actor=created_by,
            details=description,
        ))
        
        return PromptVersion(
            name=name,
            version=version,
            content=content,
            created_at=datetime.utcnow(),
            created_by=created_by,
            description=description,
            model_affinity=model_affinity,
        )
    
    def get(
        self,
        name: str,
        version: Optional[str] = None,
    ) -> str:
        """
        Get prompt content.
        
        If version is None, returns the active version.
        """
        if version is None:
            version = self.get_active_version(name)
        
        prompt_file = self.storage_path / version / f"{name}.txt"
        
        if not prompt_file.exists():
            raise FileNotFoundError(
                f"Prompt '{name}' version '{version}' not found"
            )
        
        return prompt_file.read_text()
    
    def get_active_version(self, name: str) -> str:
        """Get the currently active version for a prompt."""
        active = self._metadata.get("active_versions", {}).get(name)
        if not active:
            raise ValueError(f"No active version set for prompt '{name}'")
        return active
    
    def promote(
        self,
        name: str,
        version: str,
        promoted_by: str,
    ) -> None:
        """
        Promote a version to active.
        
        This is what production will use.
        """
        # Verify version exists
        prompt_file = self.storage_path / version / f"{name}.txt"
        if not prompt_file.exists():
            raise FileNotFoundError(
                f"Cannot promote: Prompt '{name}' version '{version}' not found"
            )
        
        # Track previous active for audit
        previous = self._metadata.get("active_versions", {}).get(name)
        
        # Update active version
        if "active_versions" not in self._metadata:
            self._metadata["active_versions"] = {}
        self._metadata["active_versions"][name] = version
        
        self._save_metadata()
        
        # Audit log
        self._log_audit(PromptAuditEntry(
            timestamp=datetime.utcnow(),
            action="promoted",
            name=name,
            version=version,
            actor=promoted_by,
            details=f"Previous active: {previous}" if previous else "First promotion",
        ))
    
    def rollback(
        self,
        name: str,
        rolled_back_by: str,
    ) -> str:
        """
        Rollback to previous active version.
        
        Returns the version that is now active.
        """
        # Find previous active from audit log
        previous_active = None
        
        with open(self._audit_file, "r") as f:
            entries = [json.loads(line) for line in f if line.strip()]
        
        # Find the second-to-last promotion for this prompt
        promotions = [
            e for e in reversed(entries)
            if e["action"] == "promoted" and e["name"] == name
        ]
        
        if len(promotions) < 2:
            raise ValueError(f"No previous version to rollback to for '{name}'")
        
        previous_active = promotions[1]["version"]
        
        self.promote(name, previous_active, rolled_back_by)
        
        return previous_active
    
    def list_versions(self, name: str) -> List[Dict]:
        """List all versions of a prompt with metadata."""
        if name not in self._metadata["prompts"]:
            return []
        
        return self._metadata["prompts"][name]["versions"]
    
    def get_audit_history(
        self,
        name: Optional[str] = None,
        limit: int = 100,
    ) -> List[PromptAuditEntry]:
        """Get audit history, optionally filtered by prompt name."""
        entries = []
        
        with open(self._audit_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                if name is None or entry["name"] == name:
                    entries.append(PromptAuditEntry(
                        timestamp=datetime.fromisoformat(entry["timestamp"]),
                        action=entry["action"],
                        name=entry["name"],
                        version=entry["version"],
                        actor=entry["actor"],
                        details=entry.get("details"),
                    ))
        
        return entries[-limit:]
```

**Usage:**

```python
registry = PromptRegistry("prompts/")

# Register a new version
registry.register(
    name="system_prompt",
    version="v2.2.0",
    content="You are a helpful assistant. Be concise and accurate.",
    created_by="harsh@example.com",
    description="Added accuracy instruction",
    model_affinity="gpt-4o-mini",
)

# Promote to active
registry.promote("system_prompt", "v2.2.0", promoted_by="harsh@example.com")

# Get active version (for production)
prompt = registry.get("system_prompt")

# Get specific version (for testing)
prompt = registry.get("system_prompt", version="v2.3.0")

# List all versions
versions = registry.list_versions("system_prompt")
# [{"version": "v2.0.0", ...}, {"version": "v2.1.0", ...}, {"version": "v2.2.0", ...}]

# View audit history
history = registry.get_audit_history("system_prompt")

# Rollback if issues
registry.rollback("system_prompt", rolled_back_by="harsh@example.com")
```

---

## Prompt Change Workflow

The right process prevents production issues:

```
┌─────────────────────────────────────────────────────────────┐
│  1. Create New Version                                       │
│     - Don't modify existing versions                         │
│     - Create v2.3.0, leave v2.2.0 unchanged                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Test in Development                                      │
│     - Run against test cases                                 │
│     - Verify structured output still parses                  │
│     - Check edge cases                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Deploy to Staging                                        │
│     - Set PROMPT_VERSION=v2.3.0 in staging                  │
│     - Run integration tests                                  │
│     - Manual verification                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. A/B Test in Production (Optional)                        │
│     - 10% traffic to v2.3.0                                 │
│     - Compare quality metrics                                │
│     - Statistical significance check                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Promote to Active                                        │
│     - registry.promote("system_prompt", "v2.3.0")           │
│     - No deployment needed (if using hot reload)             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  6. Monitor                                                  │
│     - Watch quality metrics                                  │
│     - Check error rates                                      │
│     - Listen for user feedback                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  7. Rollback if Issues                                       │
│     - registry.rollback("system_prompt")                    │
│     - Immediate (seconds, not minutes)                       │
└─────────────────────────────────────────────────────────────┘
```

**Key principle:** Never modify an existing version. Always create a new one.

---

## Prompt + Model Coupling

A prompt optimized for one model may not work well with another:

```python
# Optimized for GPT-4o-mini
PROMPT_V2_1 = """
You are a helpful assistant. 
Respond in JSON format: {"answer": "...", "confidence": 0.0-1.0}
"""

# Same prompt with Claude might:
# - Add explanation before JSON
# - Use different confidence scale
# - Format JSON differently
```

**Approaches:**

### Option 1: Track Model Affinity

```python
registry.register(
    name="system_prompt",
    version="v2.1.0",
    content=prompt_content,
    created_by="harsh@example.com",
    model_affinity="gpt-4o-mini",  # Optimized for this model
)
```

When switching models, you know which prompts need retesting.

### Option 2: Model-Specific Prompt Versions

```
prompts/
├── gpt-4o-mini/
│   └── v2.1/
│       └── system.txt
└── claude-sonnet/
    └── v2.1/
        └── system.txt
```

Different prompts per model. More maintenance, but guaranteed compatibility.

### Option 3: Test Across Target Models

Before promoting any prompt:

```python
def validate_prompt_across_models(
    prompt: str,
    test_inputs: list[str],
    models: list[str],
) -> dict:
    """Test prompt against multiple models."""
    results = {}
    
    for model in models:
        results[model] = {
            "success_rate": 0,
            "failures": [],
        }
        
        for input_text in test_inputs:
            response = call_model(model, prompt, input_text)
            
            if validates_output(response):
                results[model]["success_rate"] += 1
            else:
                results[model]["failures"].append({
                    "input": input_text,
                    "output": response,
                })
        
        results[model]["success_rate"] /= len(test_inputs)
    
    return results

# Before promoting v2.3.0
validation = validate_prompt_across_models(
    prompt=registry.get("system_prompt", "v2.3.0"),
    test_inputs=load_test_cases(),
    models=["gpt-4o-mini", "claude-sonnet-4-5", "gpt-4o"],
)

if all(r["success_rate"] >= 0.95 for r in validation.values()):
    registry.promote("system_prompt", "v2.3.0", "harsh@example.com")
else:
    print("Prompt failed validation:", validation)
```

---

## Summary

|Concept|Purpose|
|---|---|
|**File-based versioning**|Simple, works for most teams, PR review for changes|
|**Database versioning**|Hot reload, non-engineer access, more complex|
|**Prompt management tools**|UI, collaboration, external dependency|
|**Semantic versioning**|Communicate change significance (breaking/behavior/typo)|
|**Active version**|Decouple promotion from deployment|
|**Prompt registry**|Central control, audit logging, lifecycle management|
|**Model affinity**|Track which model prompts are optimized for|

**The key insight:** Prompts are not "just text" — they're configuration that controls behavior. Version them, review them, test them, and make rollback instant.

---

## What's Next

- **Note 4:** Embedding Migration — blue-green deployment for vector indexes
- **Note 5:** A/B Testing and Shadow Mode — safely testing new models in production