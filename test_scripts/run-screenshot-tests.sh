#!/bin/sh

# This is a helper script to run screenshot tests in a headless environment.
# The intended use:
#   st -e script -e -c ./test_scripts/run-screenshot-tests.sh
#   cd report
#   uv run python -m ikup.testing.cli compare screenshots/ path/to/referece/screenshots/ -o report.html

xdotool windowfocus --sync $WINDOWID
uv run python -m ikup.testing.cli run -o report/screenshots
