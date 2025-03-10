#!/bin/sh

xdotool windowactivate --sync $WINDOWID
xdotool windowfocus --sync $WINDOWID
uv run python -m tupimage.testing.cli run *basics* -o report/screenshots
