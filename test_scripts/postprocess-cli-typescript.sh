#!/bin/sh

# This is a helper script to postprocess the typescript file coming from cli
# tests. The typescript file will be modified in place.
# Usage:
#  ./test_scripts/postprocess-cli-typescript.sh typescript

# Insert \n after each \033D (which is used to create a new line by moving the
# cursor down).
sed -i 's/\x1bD/\x1bD\n/g' "$1"

# Insert \n before and after each graphics command (unless it's already there).
sed -i 's/\(.\)\(\x1b_G.*\x1b\\\)/\1\n\2/g' "$1"
sed -i 's/\(\x1b_G.*\x1b\\\)\(.\)/\1\n\2/g' "$1"
