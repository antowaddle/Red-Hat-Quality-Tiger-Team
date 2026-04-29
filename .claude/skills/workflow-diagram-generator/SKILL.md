---
description: Generate Mermaid workflow diagrams (.mmd) and render to PNG from a given context — markdown docs, code, or conversation
user-invocable: true
allowedTools:
  - Read
  - Write
  - Bash
  - Glob
  - AskUserQuestion
---

# Workflow Diagram Generator

Generate Mermaid diagrams from a given context and render them as high-resolution PNGs.

## Usage

```
/workflow-diagram-generator <source>
```

**Source** can be:
- A file path (markdown, code, or text)
- A directory path (scans for markdown files)
- Inline description in the conversation

If no source is provided, ask the user what they want to diagram.

## Process

### Step 1: Understand the Context

1. If a file/directory path is given, read the source material.
2. Identify the workflows, pipelines, failure modes, or architecture to diagram.
3. Ask the user via AskUserQuestion if the scope is ambiguous — e.g., "I found 3 workflows in this doc. Diagram all of them, or a specific one?"

### Step 2: Plan Diagrams

Determine which diagram types fit the content:

| Content Pattern | Diagram Type | Mermaid Syntax |
|----------------|-------------|----------------|
| Sequential pipeline steps | `flowchart LR` | Left-to-right flow |
| Decision trees, failure modes | `flowchart TD` | Top-down with branches |
| Time-ordered interactions | `sequenceDiagram` | Actor lifelines |
| State transitions | `stateDiagram-v2` | States and transitions |
| Parallel activities | `flowchart TD` with subgraphs | Grouped parallel paths |

Use subgraphs to group related components (e.g., separate repos, teams, environments).

### Step 3: Generate `.mmd` Files

1. Create a target directory: use the source file's directory, or `docs/diagrams/` as the default.
2. Write one `.mmd` file per diagram. Name files descriptively with zero-padded numbering:
   - `01-pipeline-happy-path.mmd`
   - `02-failure-mode-session-break.mmd`
3. Follow these Mermaid rules to avoid syntax errors:
   - Node IDs must be alphanumeric (no spaces, hyphens, or special chars)
   - Wrap label text in `["quotes"]` if it contains special characters
   - Use `{{"double braces"}}` for hexagon/decision nodes
   - Escape parentheses in labels: use `["text (detail)"]` not `(text (detail))`
   - Subgraph IDs cannot match node IDs

### Step 4: Apply Visual Styling

Use color-coded `style` directives to convey meaning:

```
style nodeId fill:#2d5a2d,stroke:#4a4a4a,color:#fff   %% green  = success/healthy
style nodeId fill:#5a5a2d,stroke:#4a4a4a,color:#fff   %% yellow = warning/partial
style nodeId fill:#6e2d2d,stroke:#4a4a4a,color:#fff   %% red    = failure/error
style nodeId fill:#2d4a6e,stroke:#4a4a4a,color:#fff   %% blue   = info/separate system
style nodeId fill:#3a3a5a,stroke:#4a4a4a,color:#fff   %% purple = context/container
style nodeId fill:#1a1a2e,stroke:#4a4a4a,color:#fff   %% dark   = background group
```

Apply styles to subgraphs for grouping by team, repo, or environment.

### Step 5: Render to PNG

Run `mmdc` for each `.mmd` file:

```bash
mmdc -i <file>.mmd -o <file>.png -t dark -b transparent -w 2400 -H 1800 -s 3
```

**Defaults:** dark theme, transparent background, 2400px wide, 1800px tall, 3x scale.

If `mmdc` is not installed, install it:

```bash
npm install -g @mermaid-js/mermaid-cli
```

If a render fails, read the error, fix the `.mmd` syntax, and retry.

### Step 6: Report

List the generated files with a brief description of each diagram:

```
| File | Description |
|------|-------------|
| 01-happy-path.png | Reference pipeline flow |
| 02-failure-xyz.png | Failure when X happens |
```

## Gotchas

- `mmdc` may fail silently on syntax errors — always check that the `.png` file was actually created and has non-zero size.
- Flowcharts with many nodes render better as `TD` (top-down) than `LR` (left-right).
- Subgraph labels with special characters need quoting: `subgraph sg1["My Group (v2)"]`.
- Wide `LR` diagrams may render with small text — increase `-w` or switch to `TD`.
- For diagrams with 15+ nodes, consider splitting into multiple diagrams rather than one dense chart.
