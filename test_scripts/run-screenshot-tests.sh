#!/bin/sh

# This is a helper script to run screenshot tests in a headless environment.
# The intended use:
#   st -e script -e -c ./test_scripts/run-screenshot-tests.sh
#   cd report
#   uv run python -m ikup.testing.cli compare screenshots/ path/to/referece/screenshots/ -o report.html
# Additional arguments are forwarded to the test runner. For example, use
# --screenshot-border 2 to strip a 2-pixel window border before resizing.

xdotool windowfocus --sync $WINDOWID
uv run --extra test python -m ikup.testing.cli run -o report/screenshots "$@"
