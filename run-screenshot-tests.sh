#!/bin/sh

xdotool windowfocus --sync $WINDOWID
uv run python -m tupimage.testing.cli run *tupimage_terminal* -o report/screenshots
