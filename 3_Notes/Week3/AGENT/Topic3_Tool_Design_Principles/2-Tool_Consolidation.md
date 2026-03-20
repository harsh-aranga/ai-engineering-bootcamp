# Note 2: Tool Consolidation — One vs Many, Action Patterns

## The Problem: Tool Library Explosion

As you build agent capabilities, the natural instinct is to create one tool per operation:

```
create_github_pr
update_github_pr
merge_github_pr
close_github_pr
list_github_prs
get_github_pr_details
add_github_pr_reviewer
remove_github_pr_reviewer
create_github_pr_comment
...
```

This creates real problems:

1. **Context window bloat**: Each tool definition consumes tokens (name, description, schema)
2. **Selection ambiguity**: More tools = more chances for the LLM to pick the wrong one
3. **Description overlap**: "Creates a PR" vs "Opens a new PR" — which one?
4. **Maintenance burden**: 50 tools means 50 schemas to update

---

## The Action Parameter Pattern

Instead of many narrow tools, create fewer broader tools with an `action` parameter.

### Before: Many Tools

```python
# 8 separate tool definitions
tools = [
    {"name": "create_pr", "description": "Create a new pull request", ...},
    {"name": "update_pr", "description": "Update a pull request", ...},
    {"name": "merge_pr", "description": "Merge a pull request", ...},
    {"name": "close_pr", "description": "Close a pull request", ...},
    {"name": "list_prs", "description": "List pull requests", ...},
    {"name": "get_pr", "description": "Get pull request details", ...},
    {"name": "add_reviewer", "description": "Add a reviewer to PR", ...},
    {"name": "add_comment", "description": "Add a comment to PR", ...},
]
```

### After: Consolidated Tool

```python
tools = [
    {
        "name": "github_pr",
        "description": "Manage GitHub pull requests. Actions: create, update, merge, close, list, get, add_reviewer, add_comment",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "update", "merge", "close", "list", "get", "add_reviewer", "add_comment"],
                    "description": "The operation to perform"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format"
                },
                "pr_number": {
                    "type": "integer",
                    "description": "PR number (required for update, merge, close, get, add_reviewer, add_comment)"
                },
                "title": {
                    "type": "string",
                    "description": "PR title (required for create)"
                },
                "body": {
                    "type": "string",
                    "description": "PR description or comment body"
                },
                "base_branch": {
                    "type": "string",
                    "description": "Target branch (for create)"
                },
                "head_branch": {
                    "type": "string",
                    "description": "Source branch (for create)"
                },
                "reviewer": {
                    "type": "string",
                    "description": "GitHub username (for add_reviewer)"
                },
                "status_filter": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "description": "Filter for list action"
                }
            },
            "required": ["action", "repo"]
        }
    }
]
```

### Implementation

```python
def github_pr(action: str, repo: str, **kwargs) -> dict:
    match action:
        case "create":
            return create_pr(repo, kwargs["title"], kwargs["body"], 
                           kwargs["base_branch"], kwargs["head_branch"])
        case "update":
            return update_pr(repo, kwargs["pr_number"], 
                           kwargs.get("title"), kwargs.get("body"))
        case "merge":
            return merge_pr(repo, kwargs["pr_number"])
        case "close":
            return close_pr(repo, kwargs["pr_number"])
        case "list":
            return list_prs(repo, kwargs.get("status_filter", "open"))
        case "get":
            return get_pr(repo, kwargs["pr_number"])
        case "add_reviewer":
            return add_reviewer(repo, kwargs["pr_number"], kwargs["reviewer"])
        case "add_comment":
            return add_comment(repo, kwargs["pr_number"], kwargs["body"])
        case _:
            return {"success": False, "error": f"Unknown action: {action}"}
```

---

## When to Consolidate vs Separate

### Consolidate When:

|Scenario|Example|
|---|---|
|Operations on the same resource|CRUD on users, files, orders|
|Shared context/parameters|All operations need `repo` and authentication|
|Logical grouping exists|All "search" operations, all "notification" operations|
|Operations are related steps|create → update → close lifecycle|

### Keep Separate When:

|Scenario|Example|
|---|---|
|Fundamentally different domains|`search_web` vs `send_email`|
|Different auth/permissions|Read operations vs write operations with different access levels|
|Vastly different schemas|Simple lookup vs complex multi-step operation|
|One is dangerous, one isn't|`read_file` vs `delete_file` (you might want separate confirmation flows)|

---

## Anthropic's Recommendation

From Anthropic's tool use best practices:

> **Consolidate related operations into fewer tools.** Rather than creating a separate tool for every action (`create_pr`, `review_pr`, `merge_pr`), group them into a single tool with an action parameter. Fewer, more capable tools reduce selection ambiguity and make your tool surface easier for Claude to navigate.

---

## Namespacing for Multi-Service Integrations

When your agent interacts with multiple services, use consistent prefixes:

```python
tools = [
    {"name": "github_repo", ...},      # GitHub repository operations
    {"name": "github_pr", ...},        # GitHub PR operations
    {"name": "github_issue", ...},     # GitHub issue operations
    
    {"name": "slack_message", ...},    # Slack messaging
    {"name": "slack_channel", ...},    # Slack channel management
    
    {"name": "jira_ticket", ...},      # Jira ticket operations
    {"name": "jira_sprint", ...},      # Jira sprint management
]
```

Why this matters:

- **Clear ownership**: Model knows `slack_*` tools are for Slack
- **Reduced confusion**: `github_issue` vs `jira_ticket` is unambiguous
- **Easier tool search**: When using deferred loading, semantic search works better with clear prefixes

---

## Token Economics of Consolidation

Let's do the math for a real scenario:

### Separate Tools (8 tools)

Each tool definition ~150 tokens:

- Name + description: ~50 tokens
- Schema: ~100 tokens

**Total: 8 × 150 = 1,200 tokens**

### Consolidated Tool (1 tool)

One combined definition:

- Name + description: ~80 tokens (slightly longer description)
- Combined schema: ~250 tokens (one schema with action enum)

**Total: ~330 tokens**

**Savings: 870 tokens (72% reduction)**

At scale, this adds up. An agent with 50 separate tools vs 10 consolidated tools could save 5,000+ tokens per request.

---

## Dynamic Tool Filtering

Even with consolidation, you may have more tools than needed for any single conversation. Filter tools dynamically based on context:

```python
def get_relevant_tools(user_message: str, user_permissions: list) -> list:
    all_tools = load_all_tools()
    
    # Filter by permissions
    allowed_tools = [t for t in all_tools if t["name"] in user_permissions]
    
    # Filter by detected intent (simple keyword matching or embedding similarity)
    if "github" in user_message.lower() or "pull request" in user_message.lower():
        return [t for t in allowed_tools if t["name"].startswith("github_")]
    
    if "slack" in user_message.lower() or "message" in user_message.lower():
        return [t for t in allowed_tools if t["name"].startswith("slack_")]
    
    # Default: return most common tools
    return [t for t in allowed_tools if t["name"] in COMMON_TOOLS]
```

This is a precursor to **Tool Search** (covered in Days 3-4, Note 7), where you can have 1000+ tools but only load relevant ones into context.

---

## Real-World Example: Database Operations

### Over-Fragmented (Bad)

```
select_from_users
select_from_orders
select_from_products
insert_into_users
insert_into_orders
update_users
update_orders
delete_from_users
...
```

### Well-Consolidated (Good)

```python
{
    "name": "database_query",
    "description": "Execute database operations. Use 'query' for SELECT, 'execute' for INSERT/UPDATE/DELETE. Returns results or affected row count.",
    "input_schema": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["query", "execute"],
                "description": "query for SELECT (returns rows), execute for modifications (returns affected count)"
            },
            "sql": {
                "type": "string",
                "description": "SQL statement to run. Use parameterized queries with ? placeholders."
            },
            "params": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Parameter values for ? placeholders in order"
            }
        },
        "required": ["operation", "sql"]
    }
}
```

One tool, infinite queries. The LLM constructs the SQL based on context.

---

## Consolidation Anti-Patterns

### 1. The God Tool

**Bad**: One tool that does everything

```python
{
    "name": "do_everything",
    "description": "Handles all operations. Actions: search_web, send_email, create_file, delete_file, query_database, call_api, ..."
}
```

This defeats the purpose. The LLM still has to parse a massive action enum, and the schema becomes unwieldy.

### 2. Forced Consolidation

**Bad**: Grouping unrelated operations

```python
{
    "name": "misc_operations",
    "description": "Random utilities. Actions: get_weather, calculate_tip, convert_currency, translate_text"
}
```

These have nothing in common. Keep them as separate, well-described tools.

### 3. Hidden Complexity

**Bad**: Simple interface hiding complex conditional logic

```python
{
    "name": "file_ops",
    "description": "File operations",
    "input_schema": {
        "properties": {
            "action": {"enum": ["read", "write", "delete", "copy", "move", "compress", "encrypt", "sync_to_cloud", "version", "share"]}
            # ... 30 conditional parameters
        }
    }
}
```

If your consolidated tool needs a decision tree to understand, split it.

---

## Summary: Consolidation Guidelines

|Guideline|Rationale|
|---|---|
|**Group by resource**|`user_*`, `order_*`, `file_*` — natural boundaries|
|**3-8 actions per tool**|Sweet spot for consolidation|
|**Clear action enum**|Let the schema enforce valid actions|
|**Namespace prefixes**|`service_resource` pattern for multi-service agents|
|**Shared parameters**|If most actions need the same base params, consolidate|
|**Don't force it**|Unrelated operations stay separate|

---

## Key Takeaway

> **Fewer, smarter tools beat many narrow tools.**
> 
> Consolidation reduces token costs, selection ambiguity, and maintenance burden. But don't over-consolidate — the goal is logical grouping, not a single god tool.