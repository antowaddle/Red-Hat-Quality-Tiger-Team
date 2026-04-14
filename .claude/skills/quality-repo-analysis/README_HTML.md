# HTML Report Generator

Converts Quality Repository Analysis markdown reports into beautiful, interactive HTML pages.

## Features

- **Animated Score Visualization**: Circular progress indicator that animates on page load
- **Interactive Scorecard**: Hover effects and color-coded scores across all quality dimensions
- **Collapsible Sections**: Click section titles to expand/collapse for better navigation
- **Severity Indicators**: Visual color coding for critical gaps
  - 🔴 RED: High severity issues
  - 🟡 YELLOW: Medium severity issues  
  - 🟢 GREEN: Low severity issues
- **Responsive Design**: Looks great on desktop, tablet, and mobile
- **Zero Dependencies**: Pure HTML/CSS/JavaScript - no external libraries required
- **Self-Contained**: Single HTML file with embedded styles and scripts

## Usage

### Basic Usage

```bash
python3 html_generator.py input.md output.html
```

### Example

```bash
# Generate HTML from a quality analysis report
python3 html_generator.py quality-analysis-kserve.md kserve-report.html

# Open in browser
open kserve-report.html  # macOS
# or
xdg-open kserve-report.html  # Linux
# or
start kserve-report.html  # Windows
```

### With the Quality Repo Analysis Skill

When using `/quality-repo-analysis`, the skill will:
1. Generate a markdown report (e.g., `quality-analysis-repo.md`)
2. Automatically run the HTML generator
3. Open the HTML report in your default browser

## Color Coding

### Score Colors
- **Green (8.0-10.0)**: Excellent - meets or exceeds gold standards
- **Yellow (6.0-7.9)**: Good - adequate with room for improvement
- **Orange (4.0-5.9)**: Fair - significant gaps identified
- **Red (0.0-3.9)**: Poor - critical improvements needed

### Severity Levels
- **HIGH**: Critical issues requiring immediate attention
- **MEDIUM**: Important issues to address soon
- **LOW**: Minor issues or nice-to-have improvements

## Requirements

- Python 3.6 or higher
- PyYAML (recommended for YAML frontmatter support)
  ```bash
  pip install -r requirements.txt
  ```

**Note**: The generator works without PyYAML but falls back to regex parsing, which is less reliable with LLM-generated markdown. For best results, install PyYAML.

## Input Format

The generator supports two input formats:

### Recommended: YAML Frontmatter (v2)

For reliable parsing with LLM-generated content, use YAML frontmatter:

```markdown
---
repository: "owner/repo-name"
overall_score: 7.8
scorecard:
  - dimension: "Unit Tests"
    score: 8.0
    status: "Strong coverage"
critical_gaps:
  - title: "Missing coverage reporting"
    impact: "Regression risk"
    severity: "HIGH"
    effort: "2-4 hours"
quick_wins:
  - title: "Add Trivy scanning"
    effort: "1 hour"
    impact: "Security improvements"
recommendations:
  priority_0:
    - "Add coverage to PRs"
  priority_1:
    - "Create test rules"
  priority_2:
    - "Add benchmarks"
---

# Quality Analysis: [Repository Name]
...markdown content...
```

### Legacy: Regex Parsing (v1)

For backward compatibility, the generator also parses markdown reports without frontmatter:

```markdown
# Quality Analysis: [Repository Name]

## Executive Summary
- Overall Score: X/10
- Key Strengths: ...
- Critical Gaps: ...

## Quality Scorecard
| Dimension | Score | Status |
|-----------|-------|--------|
| Unit Tests | X/10 | ... |
...

## Critical Gaps
1. [Gap description]
   - Impact: ...
   - Severity: HIGH/MEDIUM/LOW
   - Effort: X hours

## Quick Wins
1. [Improvement]
   - Effort: X hours
   - Impact: ...

## Recommendations
### Priority 0 (Critical)
- Item 1
- Item 2

### Priority 1 (High Value)
- Item 1
...
```

## Output

A single, self-contained HTML file that includes:
- All parsed data from the markdown report
- Embedded CSS styles (no external stylesheets)
- Embedded JavaScript for interactivity
- Responsive layout that adapts to screen size

## Customization

The HTML template includes:
- Modern gradient design (purple/blue theme)
- Card-based layout for easy scanning
- Smooth animations and transitions
- Accessible color contrast ratios

To customize colors or styles, edit the `<style>` section in the `generate_html()` function.

## Example Output

See `sample_output.html` for an example of the generated report based on `sample_report.md`.

## Troubleshooting

**Issue**: HTML file is generated but looks unstyled
- **Solution**: Ensure you're opening the file in a modern browser (Chrome, Firefox, Safari, Edge)

**Issue**: Scores not animating
- **Solution**: The animation runs on page load. Refresh the page to see it again.

**Issue**: Sections not collapsing
- **Solution**: Ensure JavaScript is enabled in your browser.

## License

Part of the Quality Tiger Team toolkit.
