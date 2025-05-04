#!/bin/sh

# This is a helper script to run output tests in a headless environment.
# The intended use:
#   st -e script -e -c ./test_scripts/run-cli-tests.sh
#   ./test_scripts/postprocess-cli-typescript.sh typescript
#   uv run python -m tupimage.testing.output_comparison typescript ./data/cli-tests.reference
#
# Usage:
#   ./test_scripts/run-cli-tests.sh [OPTIONS] [TEST_NAMES...]
#
# Options:
#   -c, --command CMD  Command to test (default: "uv run tupimage")
#   -l, --list         List all available tests
#
# Examples:
#   # List available tests
#   ./test_scripts/run-cli-tests.sh --list
#
#   # Run specific tests
#   ./test_scripts/run-cli-tests.sh test_basics test_display
#
#   # Test a custom command
#   ./test_scripts/run-cli-tests.sh --command 'uv run --python 3.13 tupimage'
#

# Parse command-line options
while [ $# -gt 0 ]; do
    case "$1" in
        -c|--command)
            TUPIMAGE="$2"
            shift 2
            ;;
        -l|--list)
            LIST_TESTS=1
            shift
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

# Set default command if not provided
if [ -z "$TUPIMAGE" ]; then
    TUPIMAGE="uv run tupimage"
fi

# Remaining positional arguments are test names
set -- "$@"

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
    $TUPIMAGE forget --all --quiet
}

subtest() {
    echo
    echo "---------- SUBTEST $1 ----------"
    echo
}

run_command() {
    printf "tupimage %s\n" "$*" >&2
    $TUPIMAGE "$@"
    TUPIMAGE_EXIT_CODE="$?"
    if [ $TUPIMAGE_EXIT_CODE -ne 0 ]; then
        echo "Exit code: $TUPIMAGE_EXIT_CODE"
    fi
}

# Collect all test function names
TEST_NAMES=$(grep '^test_.*() {' "$0" | sed 's/() {//' | awk '{print $1}')

# Handle --list option
if [ -n "$LIST_TESTS" ]; then
    for test in $TEST_NAMES; do
        echo "$test"
    done
    exit 0
fi

# Validate test names if provided
if [ $# -gt 0 ]; then
    for test in "$@"; do
        if ! echo "$TEST_NAMES" | grep -qw "$test"; then
            echo "Error: Invalid test name '$test'" >&2
            echo "Available tests: $TEST_NAMES" >&2
            exit 1
        fi
    done
    TESTS_TO_RUN="$@"
else
    TESTS_TO_RUN="$TEST_NAMES"
fi

[ -f $DATA_DIR/wikipedia.png ] || \
    curl -o $DATA_DIR/wikipedia.png https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/440px-Wikipedia-logo-v2.svg.png
[ -f $DATA_DIR/transparency.png ] || \
    curl -o $DATA_DIR/transparency.png https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png
[ -f $DATA_DIR/tux.png ] || \
    curl -o $DATA_DIR/tux.png https://upload.wikimedia.org/wikipedia/commons/a/af/Tux.png
[ -f $DATA_DIR/column.png ] || \
    curl -o $DATA_DIR/column.png "https://upload.wikimedia.org/wikipedia/commons/9/95/Column6.png"
[ -f $DATA_DIR/small_arrow.png ] || \
    curl -o $DATA_DIR/small_arrow.png "https://upload.wikimedia.org/wikipedia/commons/b/ba/Arrow-up.png"
[ -f $DATA_DIR/ruler.png ] || \
    curl -o $DATA_DIR/ruler.png "https://upload.wikimedia.org/wikipedia/commons/3/38/Screen_Ruler.png"
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

test_basics() {
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
}

################################################################################

test_display() {
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
    run_command list -v | head -10

    subtest "Display with use-line-feeds"
    run_command $DATA_DIR/wikipedia.png -r 2 --use-line-feeds=yes
}

################################################################################

test_scaling() {
    start_test "Scaling"

    subtest "Global scale 0.5 via config"
    echo "global_scale = 0.5" > $TMPDIR/global_scale.toml
    TUPIMAGE_CONFIG=$TMPDIR/global_scale.toml $TUPIMAGE $DATA_DIR/small_arrow.png | wc -l

    subtest "Global scale 0.5 with CLI scale 2 (total 1.0)"
    TUPIMAGE_CONFIG=$TMPDIR/global_scale.toml $TUPIMAGE $DATA_DIR/small_arrow.png --scale 2 | wc -l

    subtest "scale 0.5 via config"
    echo "scale = 0.5" > $TMPDIR/global_scale.toml
    TUPIMAGE_CONFIG=$TMPDIR/global_scale.toml $TUPIMAGE $DATA_DIR/small_arrow.png | wc -l

    subtest "scale 0.5 via config overridden by CLI scale 2"
    echo "scale = 0.5" > $TMPDIR/global_scale.toml
    TUPIMAGE_CONFIG=$TMPDIR/global_scale.toml $TUPIMAGE $DATA_DIR/small_arrow.png --scale 2 | wc -l

    subtest "combining env var scaling TUPIMAGE_GLOBAL_SCALE=0.1 TUPIMAGE_SCALE=20"
    TUPIMAGE_GLOBAL_SCALE=0.1 TUPIMAGE_SCALE=20 $TUPIMAGE $DATA_DIR/small_arrow.png | wc -l
}

################################################################################

test_max_rows_cols() {
    start_test "Max rows/cols and multiple images"

    subtest "Max cols"
    run_command $DATA_DIR/wikipedia.png $DATA_DIR/small_arrow.png --max-cols 3

    subtest "Max rows"
    run_command $DATA_DIR/wikipedia.png $DATA_DIR/small_arrow.png --max-rows 3

    subtest "Max rows and cols"
    run_command display ./.cli-tests-data/wikipedia.png ./.cli-tests-data/column.png --max-cols=3 --max-rows=4
}

################################################################################

test_assign_id_upload() {
    start_test "Separate id assignment and uploading"

    subtest "No upload and force upload cannot be used together"
    run_command $DATA_DIR/wikipedia.png --no-upload --force-upload

    subtest "Upload, upload, force upload"
    run_command upload $DATA_DIR/wikipedia.png
    run_command upload $DATA_DIR/wikipedia.png
    run_command upload $DATA_DIR/wikipedia.png --force-upload

    subtest "Alloc ID, then upload and display"
    ID=$($TUPIMAGE get-id $DATA_DIR/small_arrow.png -r 2)
    run_command display $ID

    subtest "Alloc ID, then display, then upload"
    ID=$($TUPIMAGE get-id $DATA_DIR/small_arrow.png -r 3)
    run_command display $ID --no-upload
    run_command upload $ID

    subtest "Alloc ID, then display, then upload by filename"
    ID=$($TUPIMAGE get-id $DATA_DIR/small_arrow.png -r 4)
    echo $ID
    run_command display $DATA_DIR/small_arrow.png -r 4 --no-upload
    run_command upload $DATA_DIR/small_arrow.png -r 4

    subtest "The placeholder command"
    ID=$($TUPIMAGE get-id $DATA_DIR/wikipedia.png)
    echo $ID
    run_command placeholder $ID -r 3 -c 50
}

################################################################################

test_multiple_images() {
    start_test "Multiple images"

    subtest "Display multiple images"
    run_command $DATA_DIR/wikipedia.png $DATA_DIR/small_arrow.png

    subtest "Display multiple images with the same row parameter"
    run_command $DATA_DIR/wikipedia.png $DATA_DIR/small_arrow.png -r 2

    subtest "Display even more images"
    run_command -r 1 $DATA_DIR/wikipedia.png $DATA_DIR/small_arrow.png \
        $DATA_DIR/column.png $DATA_DIR/ruler.png $DATA_DIR/tux.png \
        $DATA_DIR/transparency.png

    subtest "Display some of them again. Mix in non-existing images."
    run_command -r 1 $DATA_DIR/wikipedia.png $DATA_DIR/nonexisting.png \
        $DATA_DIR/ruler.png $DATA_DIR/tux.png $DATA_DIR/transparency.png

    subtest "List all images (only one-line info)"
    run_command list

    subtest "List last 3 images"
    run_command list --last 3

    subtest "Mix ids and filenames"
    # Note that getting the id of wikipedia will update its atime, making it
    # the last image in the subsequent calls.
    ID=$($TUPIMAGE get-id $DATA_DIR/wikipedia.png)
    run_command list $ID $DATA_DIR/tux.png id:123 $DATA_DIR/nonexisting.png

    subtest "Mark dirty last 2 images, then fix last 3"
    run_command dirty --last 2
    run_command list -v --last 2
    run_command fix --last 3
    run_command list -v --last 2

    subtest "Mark dirty last 2 images, then reupload last 3"
    run_command dirty --last 2
    run_command reupload --last 3

    subtest "Mark dirty the last image, then display it"
    run_command dirty --last 1
    ID=$($TUPIMAGE list --last 1 | awk '{print $1}')
    run_command display id:$ID

    subtest "Mixing queries and images/ids is not supported"
    run_command list --last 1 $DATA_DIR/wikipedia.png

    subtest "Mixing queries and --all is not supported"
    run_command list --last 1 -a
}

################################################################################

test_force_id() {
    start_test "Force ID"

    # We need to use a number from the 24bit ID space.
    IDNUM=1193046

    subtest "Upload an image with a specific id"
    run_command display $DATA_DIR/wikipedia.png -r 2 --force-id $IDNUM

    subtest "Redisplay it"
    run_command display $DATA_DIR/wikipedia.png -r 2

    subtest "Check that the id is set"
    run_command get-id $DATA_DIR/wikipedia.png -r 2
    run_command list $DATA_DIR/wikipedia.png

    subtest "Assign the same id to a different image without uploading"
    run_command get-id $DATA_DIR/tux.png -r 2 --force-id $IDNUM
    run_command list -v

    subtest "Fix the image"
    run_command fix $IDNUM

    subtest "Display the image by id"
    run_command display $IDNUM
    run_command list -v
}

################################################################################

test_id_space() {
    start_test "ID space"

    subtest "Upload the same image with different id spaces"
    run_command upload $DATA_DIR/wikipedia.png -r 2 --id-space 24bit
    run_command upload $DATA_DIR/wikipedia.png -r 2 --id-space 32
    run_command get-id $DATA_DIR/wikipedia.png -r 2 --id-space 8bit
    run_command get-id $DATA_DIR/wikipedia.png -r 2 --id-space 8bit_diacritic
    run_command get-id $DATA_DIR/wikipedia.png -r 2 --id-space 16bit

    subtest "List all"
    run_command list -v

    subtest "Display them"
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-space 24bit
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-space 32
    # 256 = 8bit
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-space 256
    TUPIMAGE_ID_SPACE="8bit_diacritic" run_command display $DATA_DIR/wikipedia.png -r 2
    TUPIMAGE_ID_SPACE="16bit" run_command display $DATA_DIR/wikipedia.png -r 2

    subtest "Invalid id space"
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-space 123
}

################################################################################

test_id_subspace() {
    start_test "ID subspace"

    SUBSPACE="42:43"

    subtest "Upload an image with different id spaces and the same subspace"
    run_command upload $DATA_DIR/wikipedia.png -r 2 --id-space 24bit --id-subspace $SUBSPACE
    run_command upload $DATA_DIR/wikipedia.png -r 2 --id-space 32 --id-subspace $SUBSPACE
    export TUPIMAGE_ID_SUBSPACE=$SUBSPACE
    run_command get-id $DATA_DIR/wikipedia.png -r 2 --id-space 8bit
    run_command get-id $DATA_DIR/wikipedia.png -r 2 --id-space 8bit_diacritic
    run_command get-id $DATA_DIR/wikipedia.png -r 2 --id-space 16bit

    subtest "List all"
    run_command list -v

    subtest "Display them"
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-space 24bit
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-space 32
    # 256 = 8bit
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-space 256
    TUPIMAGE_ID_SPACE="8bit_diacritic" run_command display $DATA_DIR/wikipedia.png -r 2
    TUPIMAGE_ID_SPACE="16bit" run_command display $DATA_DIR/wikipedia.png -r 2

    subtest "Invalid id subspace"
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-subspace 0:1
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-subspace 0:1024
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-subspace abc
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-subspace a:b

    unset TUPIMAGE_ID_SUBSPACE
}

################################################################################

# Run the tests.
for test in $TESTS_TO_RUN; do
    $test
done
