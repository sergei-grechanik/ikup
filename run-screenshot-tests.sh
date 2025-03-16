#!/bin/sh

xdotool windowfocus --sync $WINDOWID
uv run python -m tupimage.testing.cli run -o report/screenshots
