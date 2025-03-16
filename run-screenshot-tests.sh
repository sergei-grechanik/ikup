#!/bin/sh

xdotool windowfocus --sync $WINDOWID
uv run python -m tupimage.testing.cli run deletion.underneath_text_restoration -o report/screenshots
