#!/bin/bash
# Batch Quality Analysis Helper Script
#
# This script helps automate the process of running quality analysis
# on multiple repositories and aggregating the results.
#
# Usage:
#   ./run_batch_analysis.sh [output_dir]

set -e

OUTPUT_DIR="${1:-quality_reports/$(date +%Y-%m-%d)}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Quality Analysis Batch Processor"
echo "================================="
echo ""
echo "Output directory: $OUTPUT_DIR"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Step 1: Generate commands
echo "Step 1: Generating analysis commands..."
python3 "$SCRIPT_DIR/aggregate_quality_reports.py" \
  --generate-commands \
  --commands-output "$OUTPUT_DIR/analysis_commands.txt"

echo ""
echo "✓ Commands generated: $OUTPUT_DIR/analysis_commands.txt"
echo ""

# Step 2: Instructions for running analyses
echo "Step 2: Run Quality Analyses"
echo "----------------------------"
echo ""
echo "Please run the following commands in Claude Code:"
echo ""
cat "$OUTPUT_DIR/analysis_commands.txt" | grep "^/quality-repo-analysis"
echo ""
echo "After running each analysis:"
echo "  1. Save the generated report as: {repo_name}_quality_report.md"
echo "  2. Move the report to: $OUTPUT_DIR/"
echo ""
echo "Press Enter when all analyses are complete and reports are saved..."
read -r

# Step 3: Aggregate reports
echo ""
echo "Step 3: Aggregating reports..."
echo ""

REPORT_COUNT=$(find "$OUTPUT_DIR" -name "*.md" -not -name "combined_*" -not -name "AGGREGATOR_README.md" | wc -l)

if [ "$REPORT_COUNT" -eq 0 ]; then
    echo "❌ No report files found in $OUTPUT_DIR"
    echo "   Please ensure reports are saved with .md extension"
    exit 1
fi

echo "Found $REPORT_COUNT report files"
echo ""

python3 "$SCRIPT_DIR/aggregate_quality_reports.py" \
  --reports-dir "$OUTPUT_DIR" \
  --output-md "$OUTPUT_DIR/combined_quality_report.md" \
  --output-json "$OUTPUT_DIR/quality_summary.json"

echo ""
echo "✓ Combined report: $OUTPUT_DIR/combined_quality_report.md"
echo "✓ JSON summary: $OUTPUT_DIR/quality_summary.json"
echo ""

# Step 4: Display summary
echo "Step 4: Summary"
echo "---------------"
echo ""

if [ -f "$OUTPUT_DIR/quality_summary.json" ]; then
    TOTAL=$(jq -r '.total_repositories' "$OUTPUT_DIR/quality_summary.json" 2>/dev/null || echo "N/A")
    AVG_SCORE=$(jq -r '.average_score' "$OUTPUT_DIR/quality_summary.json" 2>/dev/null || echo "N/A")

    echo "Total repositories analyzed: $TOTAL"
    echo "Average quality score: $AVG_SCORE/10"
    echo ""
fi

echo "All outputs saved to: $OUTPUT_DIR"
echo ""
echo "Next steps:"
echo "  - Review combined report: $OUTPUT_DIR/combined_quality_report.md"
echo "  - Analyze trends in JSON: $OUTPUT_DIR/quality_summary.json"
echo "  - Prioritize improvements based on common gaps"
echo ""
