#!/bin/sh

# This is a helper script to run output tests in a headless environment.
# The intended use:
#   st -e script -e -c ./test_scripts/run-cli-tests.sh
#   ./test_scripts/postprocess-cli-typescript.sh typescript
#   uv run python -m tupimage.testing.output_comparison typescript ./data/cli-tests.reference

TUPIMAGE="$1"

if [ -z "$TUPIMAGE" ]; then
    TUPIMAGE="uv run tupimage"
fi

DATA_DIR="./.cli-tests-data"
mkdir -p "$DATA_DIR" 2> /dev/null

TMPDIR="$(mktemp -d)"
if [ -z "$TMPDIR" ]; then
    echo "Failed to create a temporary directory" 1>&2
    exit 1
fi

cleanup() {
    rm -r "$TMPDIR"
}

start_test() {
    echo
    echo "========== TEST $1 =========="
    echo
}

subtest() {
    echo
    echo "---------- SUBTEST $1 ----------"
    echo
}

run_command() {
    printf "tupimage %s\n" "$*" >&2
    $TUPIMAGE "$@"
}


[ -f $DATA_DIR/wikipedia.png ] || \
    curl -o $DATA_DIR/wikipedia.png https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/440px-Wikipedia-logo-v2.svg.png
[ -f $DATA_DIR/transparency.png ] || \
    curl -o $DATA_DIR/transparency.png https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png
[ -f $DATA_DIR/tux.png ] || \
    curl -o $DATA_DIR/tux.png https://upload.wikimedia.org/wikipedia/commons/a/af/Tux.png
[ -f $DATA_DIR/column.png ] || \
    curl -o $DATA_DIR/column.png "https://upload.wikimedia.org/wikipedia/commons/9/95/Column6.png"
[ -f $DATA_DIR/earth.jpg ] || \
    curl -o $DATA_DIR/earth.jpg "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cb/The_Blue_Marble_%28remastered%29.jpg/240px-The_Blue_Marble_%28remastered%29.jpg"
[ -f $DATA_DIR/mars.jpg ] || \
    curl -o $DATA_DIR/mars.jpg "https://upload.wikimedia.org/wikipedia/commons/0/02/OSIRIS_Mars_true_color.jpg"
[ -f $DATA_DIR/sun.jpg ] || \
    curl -o $DATA_DIR/sun.jpg "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/The_Sun_by_the_Atmospheric_Imaging_Assembly_of_NASA%27s_Solar_Dynamics_Observatory_-_20100819.jpg/628px-The_Sun_by_the_Atmospheric_Imaging_Assembly_of_NASA%27s_Solar_Dynamics_Observatory_-_20100819.jpg"
[ -f $DATA_DIR/butterfly.jpg ] || \
    curl -o $DATA_DIR/butterfly.jpg "https://upload.wikimedia.org/wikipedia/commons/a/a6/Peacock_butterfly_%28Aglais_io%29_2.jpg"
[ -f $DATA_DIR/david.jpg ] || \
    curl -o $DATA_DIR/david.jpg "https://upload.wikimedia.org/wikipedia/commons/8/84/Michelangelo%27s_David_2015.jpg"
[ -f $DATA_DIR/fern.jpg ] || \
    curl -o $DATA_DIR/fern.jpg "https://upload.wikimedia.org/wikipedia/commons/3/3d/Giant_fern_forest_7.jpg"
[ -f $DATA_DIR/flake.jpg ] || \
    curl -o $DATA_DIR/flake.jpg "https://upload.wikimedia.org/wikipedia/commons/d/d7/Snowflake_macro_photography_1.jpg"
[ -f $DATA_DIR/flower.jpg ] || \
    curl -o $DATA_DIR/flower.jpg "https://upload.wikimedia.org/wikipedia/commons/4/40/Sunflower_sky_backdrop.jpg"
[ -f $DATA_DIR/a_panorama.jpg ] || \
    curl -o $DATA_DIR/a_panorama.jpg "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Kazbeg_Panorama.jpg/2560px-Kazbeg_Panorama.jpg"

################################################################################

export TUPIMAGE_CONFIG="DEFAULT"
export TUPIMAGE_ID_DATABASE_DIR="$TMPDIR/id_database_dir"

# Disable 3rd diacritics because they are hard to match with the reference. We
# will test them only in fixed id tests.
export TUPIMAGE_ID_SPACE="24bit"

################################################################################

start_test "Basics: help, status, config"

subtest "Just help"
run_command --help
subtest "Different ways of printing help (only help line is checked)"
run_command | grep help
run_command -h | grep help
run_command $DATA_DIR/tux.png --help | grep help
run_command $DATA_DIR/tux.png -h | grep help

subtest "Config"
run_command dump-config
subtest "Config without provenance"
run_command dump-config --no-provenance
subtest "Config without defaults"
run_command dump-config --skip-default
subtest "Config without defaults and provenance"
run_command dump-config --skip-default --no-provenance


subtest "Status"
run_command status

################################################################################

start_test "Basic image display"

subtest "Just wikipedia logo"
run_command $DATA_DIR/wikipedia.png

subtest "Various ways to specify 1 row"
run_command $DATA_DIR/wikipedia.png -r 1
run_command -r 1 $DATA_DIR/wikipedia.png
run_command $DATA_DIR/wikipedia.png --rows 1

subtest "Various ways to specify 1 column"
run_command $DATA_DIR/wikipedia.png -c 1
run_command -c 1 $DATA_DIR/wikipedia.png
run_command $DATA_DIR/wikipedia.png --cols 1

subtest "-r from 1 to 5"
for i in $(seq 1 5); do
    $TUPIMAGE $DATA_DIR/wikipedia.png -r $i
done

subtest "-c from 1 to 5"
for i in $(seq 1 5); do
    $TUPIMAGE $DATA_DIR/wikipedia.png -c $i
done

subtest "Test scaling via -s and --scale"
run_command $DATA_DIR/wikipedia.png -s 0.5
run_command $DATA_DIR/wikipedia.png --scale 0.2

subtest "Display through file"
run_command $DATA_DIR/tux.png -o $TMPDIR/tux.txt
cat $TMPDIR/tux.txt

subtest "Display through pipe"
run_command $DATA_DIR/wikipedia.png -r 2 | cat
run_command list | head -10

subtest "Display with use-line-feeds"
run_command $DATA_DIR/wikipedia.png -r 2 --use-line-feeds=yes
sleep 20
