#!/bin/sh

# This script that runs vimdiff of a given test output file against the
# reference file.
# Usage: ./test_scripts/vimdiff-cli-test.sh <test_output_file>

if [ -z "$1" ]; then
    echo "Usage: $0 <test_output_file>"
    exit 1
fi

TEST_OUTPUT_FILE="$1"
TEST_NAME=$(basename "$TEST_OUTPUT_FILE" .out)
REFERENCE_FILE="./data/cli-test-references/${TEST_NAME}.reference"

exec vimdiff "$TEST_OUTPUT_FILE" "$REFERENCE_FILE"
