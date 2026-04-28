# Historical Bug Test Coverage Analysis Skill

Deep analysis of historical bugs with coverage assessment and confidence scoring.

## Quick Start

```bash
/historical-bug-coverage \
  --jql "project = MYPROJECT AND priority in (Blocker, Critical)" \
  --repo /path/to/your-repo
```

## Key Features

- **Deep Test Analysis** - Reads test files and understands assertions
- **Confidence Scores** - 0-100% match quality for each bug
- **Coverage Criteria** - 80%+ confidence required for COVERED status
- **Test File Visibility** - Shows exactly which test covers each bug
- **Granular Test Levels** - Unit/Mock/Component/E2E-Upstream/E2E-Downstream
- **Team Feedback** - Export mappings for validation and learning

## Documentation

- **[SKILL.md](./SKILL.md)** - User-facing documentation with examples
- **[instructions.md](./instructions.md)** - Agent execution instructions

## Architecture

```
historical-bug-coverage/
├── strict_coverage_analysis.py    # Main analysis engine
├── test_analysis.py                # Deep test file parsing
├── coverage_rubric.py              # Team feedback system
├── repository_discovery.py         # Test infrastructure discovery
└── run_analysis.sh                 # Shell wrapper for .env loading
```

### Key Modules

**strict_coverage_analysis.py**
- Fetches bugs from Jira
- Performs coverage matching
- Integrates deep test analysis
- Generates HTML report

**test_analysis.py**
- Reads test files (Jest, Cypress, pytest, Go)
- Extracts assertions
- Infers what tests validate
- Calculates match confidence

**coverage_rubric.py**
- Exports bug-test mappings
- Generates review templates
- Learns from team feedback
- Improves matching accuracy

## Example Output

```
COVERED: 38/371 (10%)  ✓ High-confidence matches
- Test files visible
- Confidence scores: 85%, 72%, 91%
- Teams can verify matches
```

## Requirements

- Python 3.8+
- Jira API credentials (JIRA_SERVER, JIRA_USER, JIRA_TOKEN)
- Git repository with test files

## Security

All user input is properly escaped to prevent XSS attacks. HTML and JSON outputs are sanitized.

## Support

Report issues: https://github.com/anthropics/claude-code/issues
