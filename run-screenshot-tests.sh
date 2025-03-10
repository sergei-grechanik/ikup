#!/bin/sh

xdotool windowactivate $WINDOWID
uv run python -m tupimage.testing.cli run *basics* -o report/screenshots
