# Fingerprinting Design for Quality Tiger Team Skills

## Problem Statement

Quality Tiger Team skills need to leave a "fingerprint" when executed that:
- Works both locally and via Ambient
- Can be consumed by team-tracker dashboard
- Follows the pattern established by [RFE creator](https://github.com/jwforres/rfe-creator)

## Analysis of RFE Creator Approach

### How RFE Creator Does It

**Jira Labels Used:**
- `rfe-creator-auto-created` - New RFE created by the tool
- `rfe-creator-auto-revised` - RFE revised during review
- `rfe-creator-needs-attention` - RFE flagged for manual review

**Implementation:**
- Uses Jira REST API v3 with Basic Auth
- Environment variables: `JIRA_SERVER`, `JIRA_USER`, `JIRA_TOKEN`
- Labels attached to actual RFE tickets (RHAIRFE project)
- Team tracker queries Jira for these labels to track usage

**Key Code Pattern:**
```python
# Determine labels
labels = []
if not is_existing:
    labels.append("rfe-creator-auto-created")
if review_data and review_data.get("revised", False):
    labels.append("rfe-creator-auto-revised")
if review_data and review_data.get("needs_attention", False):
    labels.append("rfe-creator-needs-attention")

# Apply to Jira issue
add_labels(server, user, token, issue_key, labels)
```

## Proposed Design for Quality Tiger Team

### 1. Label Naming Convention

**Skill-specific labels:**
- `quality-repo-analysis-executed` - Quality Repo Analysis skill ran
- `konflux-build-simulator-executed` - Konflux Build Simulator skill ran
- `test-rules-generator-executed` - Test Rules Generator skill ran

**Status/outcome labels (optional):**
- `quality-tiger-team-success` - Execution completed successfully
- `quality-tiger-team-failure` - Execution failed
- `quality-tiger-team-needs-review` - Manual review recommended

### 2. Where to Attach Labels

**Option A: Attach to Existing Repository Issues (Recommended)**
- When skill runs on a repository (e.g., odh-dashboard), find or create a tracking issue
- Issue title: `[Quality Tiger Team] Repository Quality Tracking - {repo-name}`
- Project: RHOAIENG (or appropriate team project)
- Issue type: Task or Epic
- Benefits:
  - One issue per repository tracks all quality initiatives
  - Easy to find and query
  - Links to actual work

**Option B: Create Per-Execution Issues**
- Each skill execution creates a new Jira issue
- Benefits: Detailed audit trail
- Drawbacks: Creates noise, harder to aggregate

**Recommendation: Option A** - One tracking issue per repository, update labels on each execution.

### 3. Metadata to Capture

**In Jira Labels:**
- Tool execution flag (which skill ran)
- Execution status (success/failure)

**In Jira Issue Description/Comments:**
- Execution timestamp (ISO 8601)
- Repository URL
- Skill version
- Key findings/outputs (scorecard, critical gaps, etc.)
- Link to generated artifacts (if applicable)
- Executor (local user or Ambient)

**Example Comment Format:**
```markdown
## Quality Repo Analysis Execution - 2026-03-30T14:32:00Z

**Repository:** https://github.com/opendatahub-io/odh-dashboard
**Executor:** Ambient
**Status:** ✅ Success
**Skill Version:** 1.0.0

### Results
- **Quality Score:** 8.5/10
- **Critical Gaps:** 2
- **Quick Wins:** 5

### Artifacts Generated
- Quality scorecard: `.claude/quality/scorecard.md`
- Critical gaps report: `.claude/quality/critical-gaps.md`
- Recommendations: `.claude/quality/quick-wins.md`

---
*[Quality Tiger Team]* Automated analysis powered by quality-repo-analysis skill
```

### 4. Implementation Options

#### Option 1: MCP Integration (Preferred for Ambient Compatibility)

**Available MCP Servers:**
- [tom28881/mcp-jira-server](https://github.com/tom28881/mcp-jira-server) - Comprehensive
- [MankowskiNick/jira-mcp](https://github.com/MankowskiNick/jira-mcp) - Ticket creation focused
- [codingthefuturewithai/mcp_jira](https://github.com/codingthefuturewithai/mcp_jira) - Full integration
- [Composio managed solution](https://composio.dev/toolkits/jira/framework/claude-code) - Hosted MCP

**Pros:**
- ✅ Works in Ambient automatically
- ✅ Works locally once configured
- ✅ No credential management in skill code
- ✅ Native Claude Code integration

**Cons:**
- ❌ Requires user setup (MCP server configuration)
- ❌ Not all users may have MCP configured

#### Option 2: Direct Jira API (Fallback for Local Execution)

**Pattern from RFE Creator:**
```python
from jira_utils import (
    require_env,
    create_issue,
    update_issue,
    add_labels,
    add_comment,
    markdown_to_adf,
)

# Get credentials
server, user, token = require_env()  # JIRA_SERVER, JIRA_USER, JIRA_TOKEN

# Find or create tracking issue
tracking_issue = find_or_create_tracking_issue(
    server, user, token,
    project="RHOAIENG",
    repo_url="https://github.com/opendatahub-io/odh-dashboard"
)

# Add fingerprint labels
labels = [
    "quality-repo-analysis-executed",
    "quality-tiger-team-success"
]
add_labels(server, user, token, tracking_issue, labels)

# Add execution comment
comment_md = generate_execution_comment(results)
comment_adf = markdown_to_adf(comment_md)
add_comment(server, user, token, tracking_issue, comment_adf)
```

**Pros:**
- ✅ Works without MCP setup
- ✅ Direct control over API calls
- ✅ Proven pattern (RFE creator uses this)

**Cons:**
- ❌ Requires environment variables locally
- ❌ May not work in Ambient (depends on credential access)

#### Option 3: Hybrid Approach (Recommended)

**Strategy:**
1. Check if MCP Jira tools are available
2. If yes, use MCP
3. If no, fall back to direct API with environment variables
4. If neither available, log warning and skip fingerprinting

**Pseudo-code:**
```python
def record_fingerprint(skill_name, repo_url, results):
    # Try MCP first
    if mcp_jira_available():
        return record_via_mcp(skill_name, repo_url, results)

    # Fall back to direct API
    elif jira_env_vars_present():
        return record_via_api(skill_name, repo_url, results)

    # Skip if neither available
    else:
        print("Warning: Fingerprinting skipped (no Jira access configured)")
        print("To enable tracking:")
        print("  1. Configure Jira MCP server, OR")
        print("  2. Set JIRA_SERVER, JIRA_USER, JIRA_TOKEN environment variables")
        return None
```

### 5. Implementation Plan

#### Phase 1: Core Utilities (Shared Across Skills)

Create `/Users/acoughli/qualityTigerTeam/.claude/skills/shared/fingerprint_utils.py`:

```python
#!/usr/bin/env python3
"""Jira fingerprinting utilities for Quality Tiger Team skills."""

import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any

# Import RFE creator's Jira utilities (reuse proven code)
# TODO: Copy jira_utils.py to shared location or create dependency


def is_jira_configured() -> bool:
    """Check if Jira API access is configured via environment variables."""
    return all([
        os.getenv("JIRA_SERVER"),
        os.getenv("JIRA_USER"),
        os.getenv("JIRA_TOKEN"),
    ])


def find_or_create_tracking_issue(
    server: str,
    user: str,
    token: str,
    project: str,
    repo_url: str,
) -> Optional[str]:
    """Find existing tracking issue for repository or create new one.

    Returns:
        Jira issue key (e.g., "RHOAIENG-12345") or None if failed
    """
    # Extract repo name from URL
    repo_name = repo_url.rstrip("/").split("/")[-1]

    # Search for existing tracking issue
    jql = f'project = {project} AND summary ~ "Quality Tiger Team" AND summary ~ "{repo_name}"'
    # TODO: Implement search using jira_utils

    # If not found, create new tracking issue
    # TODO: Implement creation using jira_utils

    return None  # Placeholder


def record_skill_execution(
    skill_name: str,
    repo_url: str,
    status: str,  # "success" or "failure"
    results: Dict[str, Any],
    project: str = "RHOAIENG",
) -> bool:
    """Record skill execution as Jira fingerprint.

    Args:
        skill_name: Name of skill (e.g., "quality-repo-analysis")
        repo_url: Repository URL
        status: Execution status ("success" or "failure")
        results: Skill results to include in comment
        project: Jira project key

    Returns:
        True if fingerprint recorded successfully, False otherwise
    """
    # Check if Jira is configured
    if not is_jira_configured():
        print("\n⚠️  Fingerprinting skipped: Jira not configured", file=sys.stderr)
        print("To enable execution tracking:", file=sys.stderr)
        print("  1. Configure Jira MCP server, OR", file=sys.stderr)
        print("  2. Set environment variables:", file=sys.stderr)
        print("     export JIRA_SERVER=https://redhat.atlassian.net", file=sys.stderr)
        print("     export JIRA_USER=your-email@redhat.com", file=sys.stderr)
        print("     export JIRA_TOKEN=your-api-token", file=sys.stderr)
        return False

    # Get credentials
    server = os.getenv("JIRA_SERVER")
    user = os.getenv("JIRA_USER")
    token = os.getenv("JIRA_TOKEN")

    try:
        # Find or create tracking issue
        issue_key = find_or_create_tracking_issue(server, user, token, project, repo_url)
        if not issue_key:
            print(f"⚠️  Could not find or create tracking issue", file=sys.stderr)
            return False

        # Prepare labels
        labels = [
            f"{skill_name}-executed",
            f"quality-tiger-team-{status}",
        ]

        # Add labels
        # TODO: Use jira_utils.add_labels()

        # Generate and post comment
        comment_md = _generate_execution_comment(skill_name, repo_url, status, results)
        # TODO: Convert to ADF and post using jira_utils.add_comment()

        print(f"\n✅ Fingerprint recorded: {issue_key}")
        print(f"   Labels: {', '.join(labels)}")
        return True

    except Exception as e:
        print(f"⚠️  Fingerprinting failed: {e}", file=sys.stderr)
        return False


def _generate_execution_comment(
    skill_name: str,
    repo_url: str,
    status: str,
    results: Dict[str, Any],
) -> str:
    """Generate markdown comment for Jira issue."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    status_emoji = "✅" if status == "success" else "❌"

    # Extract repo name
    repo_name = repo_url.rstrip("/").split("/")[-1]

    # Build comment
    lines = [
        f"## {skill_name.replace('-', ' ').title()} - {timestamp}",
        "",
        f"**Repository:** {repo_url}",
        f"**Status:** {status_emoji} {status.title()}",
        "",
    ]

    # Add skill-specific results
    if "score" in results:
        lines.append(f"**Quality Score:** {results['score']}/10")
    if "critical_gaps" in results:
        lines.append(f"**Critical Gaps:** {results['critical_gaps']}")
    if "quick_wins" in results:
        lines.append(f"**Quick Wins:** {results['quick_wins']}")
    if "artifacts" in results:
        lines.append("")
        lines.append("### Artifacts Generated")
        for artifact in results["artifacts"]:
            lines.append(f"- {artifact}")

    lines.extend([
        "",
        "---",
        f"*[Quality Tiger Team]* Automated tracking by {skill_name} skill",
    ])

    return "\n".join(lines)
```

#### Phase 2: Skill Integration

Update each skill's `instructions.md` to include fingerprinting step:

**Example for quality-repo-analysis:**

```markdown
## Step 8: Record Execution Fingerprint

After generating all reports and artifacts:

1. Import fingerprinting utilities:
   ```python
   from shared.fingerprint_utils import record_skill_execution
   ```

2. Prepare results dictionary:
   ```python
   results = {
       "score": quality_score,
       "critical_gaps": len(critical_gaps),
       "quick_wins": len(quick_wins),
       "artifacts": [
           ".claude/quality/scorecard.md",
           ".claude/quality/critical-gaps.md",
           ".claude/quality/quick-wins.md",
       ]
   }
   ```

3. Record fingerprint:
   ```python
   record_skill_execution(
       skill_name="quality-repo-analysis",
       repo_url=repository_url,
       status="success",  # or "failure" if errors occurred
       results=results,
   )
   ```

4. If fingerprinting is not configured, the skill will print a warning but continue execution normally.
```

#### Phase 3: Testing

1. **Test locally without Jira configured** - Should print warning and skip
2. **Test locally with Jira API credentials** - Should create/update issue with labels
3. **Test via Ambient with MCP configured** - Should use MCP tools
4. **Verify team-tracker dashboard** - Confirm data appears correctly

### 6. MCP Server Setup Instructions

For users who want full Ambient compatibility, provide setup guide:

```markdown
## Setting Up Jira MCP for Quality Tiger Team Skills

### Option 1: Install Community MCP Server (Recommended)

1. Install the comprehensive Jira MCP server:
   ```bash
   npm install -g @tom28881/mcp-jira-server
   ```

2. Configure in Claude Code settings (`~/.claude/settings.json`):
   ```json
   {
     "mcp": {
       "servers": {
         "jira": {
           "command": "mcp-jira-server",
           "env": {
             "JIRA_SERVER": "https://redhat.atlassian.net",
             "JIRA_USER": "your-email@redhat.com",
             "JIRA_TOKEN": "your-api-token"
           }
         }
       }
     }
   }
   ```

3. Restart Claude Code

4. Verify: Type `@` in Claude Code prompt to see Jira resources

### Option 2: Use Composio Managed MCP (No Local Setup)

1. Visit [Composio Jira MCP](https://composio.dev/toolkits/jira/framework/claude-code)
2. Follow OAuth setup (no API tokens needed)
3. Managed MCP layer handles authentication

### Option 3: Direct API Only (Local Execution)

If you only run skills locally and don't need Ambient compatibility:

1. Export environment variables:
   ```bash
   export JIRA_SERVER=https://redhat.atlassian.net
   export JIRA_USER=your-email@redhat.com
   export JIRA_TOKEN=your-api-token
   ```

2. Add to `~/.zshrc` or `~/.bashrc` to persist across sessions
```

## Next Steps

1. ✅ **Design fingerprinting approach** - THIS DOCUMENT
2. ⏭️ Copy `jira_utils.py` from RFE creator to shared utilities
3. ⏭️ Implement `fingerprint_utils.py` with core functions
4. ⏭️ Update all 3 skill instructions to include fingerprinting step
5. ⏭️ Test locally with and without Jira configured
6. ⏭️ Document MCP setup for users
7. ⏭️ Coordinate with team-tracker maintainers on label conventions

## Questions for Discussion

1. **Which Jira project?** - RHOAIENG or create dedicated quality tracking project?
2. **Issue lifecycle?** - Keep issues open indefinitely or close after X time?
3. **Label consolidation?** - Should we add date to labels (e.g., `quality-repo-analysis-executed-2026-03`)?
4. **Team tracker integration?** - Do we need specific label format for dashboard to parse?
5. **Privacy considerations?** - Any repositories we should NOT track in Jira?

## References

- [RFE Creator Fingerprinting](https://github.com/jwforres/rfe-creator/blob/main/scripts/submit.py#L150-L157)
- [Claude Code MCP Docs](https://code.claude.com/docs/en/mcp)
- [Jira MCP Server (tom28881)](https://github.com/tom28881/mcp-jira-server)
- [Jira MCP Server (MankowskiNick)](https://github.com/MankowskiNick/jira-mcp)
- [Composio Jira MCP](https://composio.dev/toolkits/jira/framework/claude-code)
