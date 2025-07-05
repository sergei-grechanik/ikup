#!/bin/sh

# This script that runs output comparison for a given test output file
# # Usage: ./test_scripts/compare-cli-test.sh <test_output_file>

if [ -z "$1" ]; then
    echo "Usage: $0 <test_output_file>"
    exit 1
fi

if [ -d "$1" ]; then
    exec uv run python -m ikup.testing.output_comparison "$1" ./data/cli-test-references
fi

TEST_OUTPUT_FILE="$1"
TEST_NAME=$(basename "$TEST_OUTPUT_FILE" .out)
REFERENCE_FILE="./data/cli-test-references/${TEST_NAME}.reference"

exec uv run python -m ikup.testing.output_comparison "$TEST_OUTPUT_FILE" "$REFERENCE_FILE"
