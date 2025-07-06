#!/bin/sh

# This is a helper script to run output tests in a headless environment.
# The intended use:
#   xvfb-run st -e ./test_scripts/run-cli-tests.sh
#   uv run python -m ikup.testing.output_comparison cli-test-outputs/ data/cli-test-references/
#
# Usage:
#   ./test_scripts/run-cli-tests.sh [OPTIONS] [TEST_NAMES...]
#
# Options:
#   -c, --command CMD  Command to test (default: "uv run ikup")
#   -l, --list         List all available tests
#   --no-script        Disable script recording (for internal use)
#
# Examples:
#   # List available tests
#   ./test_scripts/run-cli-tests.sh --list
#
#   # Run specific tests
#   ./test_scripts/run-cli-tests.sh test_basics test_display
#
#   # Test a custom command
#   ./test_scripts/run-cli-tests.sh --command 'uv run --python 3.13 ikup'
#

# Capture original arguments before parsing for script wrapper
ORIGINAL_COMMAND="$0 --no-script"
for arg in "$@"; do
    ORIGINAL_COMMAND="$ORIGINAL_COMMAND \"$arg\""
done

# Parse command-line options
while [ $# -gt 0 ]; do
    case "$1" in
        -c|--command)
            IKUP="$2"
            shift 2
            ;;
        -l|--list)
            LIST_TESTS=1
            shift
            ;;
        --db-dir)
            DATABASE_DIR="$2"
            shift 2
            ;;
        --no-script)
            NO_SCRIPT=1
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

# Remaining positional arguments are test names

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

# Self-execute with script if not disabled
if [ -z "$NO_SCRIPT" ]; then
    # Create output directory for individual test results
    OUTPUT_DIR="./cli-test-outputs"
    mkdir -p "$OUTPUT_DIR" 2> /dev/null

    script -q -e -c "$ORIGINAL_COMMAND" "$OUTPUT_DIR/typescript"

    # After script completes, split the typescript file
    if [ ! -f "$OUTPUT_DIR/typescript" ]; then
        echo "Error: typescript file not found" >&2
        exit 1
    fi

    # Remove script header and footer lines
    sed -i '/^Script started on /d; /^Script done on /d' "$OUTPUT_DIR/typescript"

    # Split the file by test markers
    awk -v output_dir="$OUTPUT_DIR" '
    /^========== TEST [a-zA-Z_]+ - / {
        if (current_file) close(current_file)
        # Extract test function name from the line
        for (i = 1; i <= NF; i++) {
            if ($i == "TEST") {
                test_name = $(i+1)
                break
            }
        }
        current_file = output_dir "/" test_name ".out"
        print > current_file
        next
    }
    current_file { print > current_file }
    ' "$OUTPUT_DIR/typescript"

    # Post-process each output file
    for output_file in "$OUTPUT_DIR"/*.out; do
        if [ -f "$output_file" ]; then
            # Remove carriage return characters before newlines
            sed -i 's/\r$//' "$output_file"

            # Insert \n after each \033D
            sed -i 's/\x1bD/\x1bD\n/g' "$output_file"

            # Insert \n before and after each graphics command
            sed -i 's/\(.\)\(\x1b_G[^\x1b]*\x1b\\\)\(.\)/\1\n\2\n\3/g' "$output_file"
            sed -i 's/\(\x1b_G[^\x1b]*\x1b\\\)\(.\)/\1\n\2/g' "$output_file"
            sed -i 's/\(.\)\(\x1b_G[^\x1b]*\x1b\\\)/\1\n\2/g' "$output_file"
        fi
    done

    exit 0
fi

# Set default command if not provided
if [ -z "$IKUP" ]; then
    IKUP="uv run ikup"
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
    echo "========== TEST $CURRENT_TEST_NAME - $1 =========="
    echo
    $IKUP forget --all --quiet
}

subtest() {
    echo
    echo "---------- SUBTEST $1 ----------"
    echo
}

run_command() {
    printf "ikup %s\n" "$*" >&2
    $IKUP "$@"
    IKUP_EXIT_CODE="$?"
    if [ $IKUP_EXIT_CODE -ne 0 ]; then
        echo "Exit code: $IKUP_EXIT_CODE"
    fi
}

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

if [ -z "$DATABASE_DIR" ]; then
    DATABASE_DIR="$TMPDIR/id_database_dir"
fi

export IKUP_CONFIG="DEFAULT"
export IKUP_ID_DATABASE_DIR="$DATABASE_DIR"

# Disable 3rd diacritics because they are hard to match with the reference. We
# will test them only in fixed id tests.
export IKUP_ID_SPACE="24bit"

################################################################################

test_basics() {
    start_test "Basics: help, status, config"

    subtest "Just version"
    run_command --version
    run_command -v
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
        $IKUP $DATA_DIR/wikipedia.png -r $i
    done

    subtest "-c from 1 to 5"
    for i in $(seq 1 5); do
        $IKUP $DATA_DIR/wikipedia.png -c $i
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
    run_command $DATA_DIR/wikipedia.png -r 2 --use-line-feeds=true
}

################################################################################

test_scaling() {
    start_test "Scaling"

    subtest "Global scale 0.5 via config"
    echo "global_scale = 0.5" > $TMPDIR/global_scale.toml
    IKUP_CONFIG=$TMPDIR/global_scale.toml $IKUP $DATA_DIR/small_arrow.png | wc -l

    subtest "Global scale 0.5 with CLI scale 2 (total 1.0)"
    IKUP_CONFIG=$TMPDIR/global_scale.toml $IKUP $DATA_DIR/small_arrow.png --scale 2 | wc -l

    subtest "scale 0.5 via config"
    echo "scale = 0.5" > $TMPDIR/global_scale.toml
    IKUP_CONFIG=$TMPDIR/global_scale.toml $IKUP $DATA_DIR/small_arrow.png | wc -l

    subtest "scale 0.5 via config overridden by CLI scale 2"
    echo "scale = 0.5" > $TMPDIR/global_scale.toml
    IKUP_CONFIG=$TMPDIR/global_scale.toml $IKUP $DATA_DIR/small_arrow.png --scale 2 | wc -l

    subtest "combining env var scaling IKUP_GLOBAL_SCALE=0.1 IKUP_SCALE=20"
    IKUP_GLOBAL_SCALE=0.1 IKUP_SCALE=20 $IKUP $DATA_DIR/small_arrow.png | wc -l
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
    ID=$($IKUP get-id $DATA_DIR/small_arrow.png -r 2)
    run_command display $ID

    subtest "Alloc ID, then display, then upload"
    ID=$($IKUP get-id $DATA_DIR/small_arrow.png -r 3)
    run_command display $ID --no-upload
    run_command upload $ID

    subtest "Alloc ID, then display, then upload by filename"
    ID=$($IKUP get-id $DATA_DIR/small_arrow.png -r 4)
    echo $ID
    run_command display $DATA_DIR/small_arrow.png -r 4 --no-upload
    run_command upload $DATA_DIR/small_arrow.png -r 4

    subtest "The placeholder command"
    ID=$($IKUP get-id $DATA_DIR/wikipedia.png)
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
    ID=$($IKUP get-id $DATA_DIR/wikipedia.png)
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
    ID=$($IKUP list --last 1 | awk '{print $1}')
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
    IKUP_ID_SPACE="8bit_diacritic" run_command display $DATA_DIR/wikipedia.png -r 2
    IKUP_ID_SPACE="16bit" run_command display $DATA_DIR/wikipedia.png -r 2

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
    export IKUP_ID_SUBSPACE=$SUBSPACE
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
    IKUP_ID_SPACE="8bit_diacritic" run_command display $DATA_DIR/wikipedia.png -r 2
    IKUP_ID_SPACE="16bit" run_command display $DATA_DIR/wikipedia.png -r 2

    subtest "Invalid id subspace"
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-subspace 0:1
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-subspace 0:1024
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-subspace abc
    run_command display $DATA_DIR/wikipedia.png -r 2 --id-subspace a:b

    unset IKUP_ID_SUBSPACE
}

################################################################################

test_upload_method() {
    start_test "Uploading methods"

    subtest "File"
    run_command display $DATA_DIR/wikipedia.png -r 2 -m file
    run_command display $DATA_DIR/transparency.png -r 2 -m f

    subtest "Stream"
    run_command display $DATA_DIR/tux.png -r 2 -m stream
    run_command display $DATA_DIR/tux.png -r 3 -m direct
    IKUP_UPLOAD_METHOD=stream run_command display $DATA_DIR/tux.png -r 4

    subtest "The fix command"
    run_command dirty --all
    run_command fix $DATA_DIR/tux.png -m direct

    subtest "Unknown and unsupported methods"
    run_command display $DATA_DIR/wikipedia.png -r 2 -m unknown
    run_command display $DATA_DIR/wikipedia.png -r 2 -m temp
}

################################################################################

test_terminal_identification() {
    start_test "Terminal identification options"

    subtest "Default terminal identification"
    run_command status | grep "terminal_name\|terminal_id\|session_id"

    subtest "Custom identification options together"
    export IKUP_TERMINAL_NAME="custom-terminal"
    export IKUP_TERMINAL_ID="custom-terminal-id"
    export IKUP_SESSION_ID="custom-session-id"
    run_command status | grep "terminal_name\|terminal_id\|session_id"

    subtest "Upload and display with custom identification"
    run_command display $DATA_DIR/wikipedia.png -r 2
    run_command list -v

    unset IKUP_TERMINAL_NAME
    unset IKUP_TERMINAL_ID
    unset IKUP_SESSION_ID
}

################################################################################

test_cleanup() {
    start_test "Database cleanup"

    # Create a temporary directory for test databases
    TEST_DB_DIR="$TMPDIR/cleanup_test_db_dir"
    mkdir -p "$TEST_DB_DIR"
    export IKUP_ID_DATABASE_DIR="$TEST_DB_DIR"

    subtest "Create old databases"
    # Create some "old" database files with timestamps in the past
    touch -d "8 days ago" "$TEST_DB_DIR/old_db1.db"
    touch -d "10 days ago" "$TEST_DB_DIR/old_db2.db"
    touch -d "1 day ago" "$TEST_DB_DIR/recent_db.db"

    # Verify databases exist
    ls -la "$TEST_DB_DIR"

    subtest "Explicit cleanup of old databases"
    # Set max age to 7 days
    export IKUP_MAX_DB_AGE_DAYS=7
    run_command cleanup

    # Check if old databases were removed
    echo "Remaining databases after cleanup:"
    ls -la "$TEST_DB_DIR"

    # The old databases should be gone, but the recent one should remain
    [ ! -f "$TEST_DB_DIR/old_db1.db" ] && echo "old_db1.db was successfully removed"
    [ ! -f "$TEST_DB_DIR/old_db2.db" ] && echo "old_db2.db was successfully removed"
    [ -f "$TEST_DB_DIR/recent_db.db" ] && echo "recent_db.db was correctly preserved"

    subtest "Test random cleanup via probability"
    # Set cleanup probability to 100% to ensure it triggers
    export IKUP_CLEANUP_PROBABILITY=1.0
    # Set max_num_ids to a small number
    export IKUP_MAX_NUM_IDS=5

    # Upload several images to exceed the max_num_ids
    for i in $(seq 1 10); do
        run_command upload $DATA_DIR/wikipedia.png -r $i
    done

    # Check how many IDs we have now
    run_command status | grep "Total IDs"

    # The number of IDs should be equal to IKUP_MAX_NUM_IDS + 1 because we
    # do the cleanup before each ID assignment.
    ID_COUNT=$($IKUP status | grep "Total IDs" | awk '{print $NF}')
    if [ "$ID_COUNT" -le 6 ]; then
        echo "Random cleanup successfully limited IDs to $IKUP_MAX_NUM_IDS + 1"
    else
        echo "Random cleanup failed: $ID_COUNT IDs remain (should be <= $IKUP_MAX_NUM_IDS + 1)"
    fi

    run_command list

    # Restore original database directory
    export IKUP_ID_DATABASE_DIR="$DATABASE_DIR"
    unset IKUP_MAX_DB_AGE_DAYS
    unset IKUP_CLEANUP_PROBABILITY
    unset IKUP_MAX_NUM_IDS
}

################################################################################

test_out_command() {
    start_test "Out command redirection"

    # Create a temporary file for command output
    COMMAND_FILE="$TMPDIR/command_output.txt"

    subtest "Display image with commands redirected to file"
    run_command display $DATA_DIR/wikipedia.png -r 2 --out-command="$COMMAND_FILE"
    echo "Commands:"
    cat "$COMMAND_FILE"

    subtest "Upload with commands redirected to file"
    # Clear the command file
    > "$COMMAND_FILE"
    run_command upload $DATA_DIR/tux.png -r 2 -O "$COMMAND_FILE"
    run_command display $DATA_DIR/tux.png -r 2
    echo "Commands:"
    cat "$COMMAND_FILE"
}

################################################################################

test_overwrite() {
    start_test "Image overwriting / mtime change"

    # Create a temporary image file that we'll replace
    TEST_IMAGE="$TMPDIR/test_image.png"

    subtest "Display original image"
    cp "$DATA_DIR/wikipedia.png" "$TEST_IMAGE"
    run_command display "$TEST_IMAGE" -r 2
    WIKIPEDIA_ID=$($IKUP get-id "$TEST_IMAGE" -r 2)

    subtest "Replace image and display again"
    cp "$DATA_DIR/tux.png" "$TEST_IMAGE"
    run_command display "$TEST_IMAGE" -r 2
    TUX_ID=$($IKUP get-id "$TEST_IMAGE" -r 2)

    subtest "List images with the given name"
    run_command list "$TEST_IMAGE"

    subtest "Fixing all. Nothing should be fixed."
    run_command fix --all

    subtest "Mark the wikipedia image as dirty."
    run_command dirty $WIKIPEDIA_ID
    # Now fixing wikipedia is impossible, we will get an error
    run_command fix --all
    run_command reupload $WIKIPEDIA_ID $TUX_ID
}

################################################################################

# Define a set of images to use in concurrent uploads
CONCURRENT_IMAGES="$DATA_DIR/wikipedia.png $DATA_DIR/tux.png $DATA_DIR/transparency.png $DATA_DIR/column.png $DATA_DIR/small_arrow.png $DATA_DIR/ruler.png $DATA_DIR/earth.jpg $DATA_DIR/flower.jpg"

test_concurrent_file() {
    start_test "Concurrent file uploads"

    # Create temporary output files
    OUTFILE1="$TMPDIR/concurrent_out1.txt"
    OUTFILE2="$TMPDIR/concurrent_out2.txt"
    OUTFILE3="$TMPDIR/concurrent_out3.txt"
    OUTFILE4="$TMPDIR/concurrent_out4.txt"
    OUTFILE5="$TMPDIR/concurrent_out5.txt"

    subtest "Running concurrent upload and display commands"

    # Run 5 processes in concurrent with different parameters
    # We do -r 1 twice to increase collision probability
    $IKUP display $CONCURRENT_IMAGES -r 1 -o "$OUTFILE1" &
    PID1=$!
    $IKUP display $CONCURRENT_IMAGES -r 1 -o "$OUTFILE2" &
    PID2=$!
    $IKUP display $CONCURRENT_IMAGES -r 2 -o "$OUTFILE3" &
    PID3=$!
    $IKUP display $CONCURRENT_IMAGES -c 1 -o "$OUTFILE4" &
    PID4=$!
    $IKUP display $CONCURRENT_IMAGES -c 2 -o "$OUTFILE5" &
    PID5=$!

    # Wait for all background processes to complete
    echo "Waiting for processes to complete..."
    wait $PID1 $PID2 $PID3 $PID4 $PID5
    echo "All processes completed."

    subtest "Results of concurrent uploads"
    echo "Output from process 1 (rows=1):"
    cat "$OUTFILE1"
    echo "Output from process 2 (rows=1):"
    cat "$OUTFILE2"
    echo "Output from process 3 (rows=2):"
    cat "$OUTFILE3"
    echo "Output from process 4 (cols=1):"
    cat "$OUTFILE4"
    echo "Output from process 5 (cols=2):"
    cat "$OUTFILE5"

    subtest "List all uploaded images"
    run_command list | cut -f2- | sort
}

################################################################################

test_concurrent_stream() {
    start_test "Concurrent stream uploads"

    # Create temporary output files
    OUTFILE1="$TMPDIR/concurrent_out1.txt"
    OUTFILE2="$TMPDIR/concurrent_out2.txt"
    OUTFILE3="$TMPDIR/concurrent_out3.txt"
    OUTFILE4="$TMPDIR/concurrent_out4.txt"
    OUTFILE5="$TMPDIR/concurrent_out5.txt"

    subtest "Running concurrent upload and display commands"

    # Run 5 processes in concurrent with different parameters
    # We do -r 1 twice to increase collision probability
    $IKUP display $CONCURRENT_IMAGES -m d -r 1 -o "$OUTFILE1" &
    $IKUP display $CONCURRENT_IMAGES -m d -r 1 -o "$OUTFILE2" &
    $IKUP display $CONCURRENT_IMAGES -m d -r 2 -o "$OUTFILE3" &
    $IKUP display $CONCURRENT_IMAGES -m d -c 1 -o "$OUTFILE4" &
    $IKUP display $CONCURRENT_IMAGES -m d -c 2 -o "$OUTFILE5" &

    # Wait for all background processes to complete
    echo "Waiting for processes to complete..."
    wait
    echo "All processes completed."

    subtest "Results of concurrent uploads"
    echo "Output from process 1 (rows=1):"
    cat "$OUTFILE1"
    echo "Output from process 2 (rows=1):"
    cat "$OUTFILE2"
    echo "Output from process 3 (rows=2):"
    cat "$OUTFILE3"
    echo "Output from process 4 (cols=1):"
    cat "$OUTFILE4"
    echo "Output from process 5 (cols=2):"
    cat "$OUTFILE5"

    subtest "List all uploaded images"
    run_command list | cut -f2- | sort
}

################################################################################

test_concurrent_mixed() {
    start_test "Concurrent stream and file uploads"

    subtest "Running concurrent upload commands"

    # Run may processes in concurrent with different parameters.
    for i in $(seq 1 5); do
        $IKUP upload $CONCURRENT_IMAGES -m d -r 1 -c 1  &
        $IKUP upload $CONCURRENT_IMAGES -m f -r 1 -c 1  &
        $IKUP upload $CONCURRENT_IMAGES -m d -r 1 -c 1  &
        $IKUP upload $CONCURRENT_IMAGES -m f -r 1 -c 1  &
        $IKUP upload $CONCURRENT_IMAGES --force-upload -m d -r 1  &
        $IKUP upload $CONCURRENT_IMAGES -m d -r 1  &
        $IKUP upload $CONCURRENT_IMAGES -m f -r 1  &
        $IKUP upload $CONCURRENT_IMAGES -m d -c 1  &
        $IKUP upload $CONCURRENT_IMAGES -m f -c 1  &
    done

    # Wait for all background processes to complete
    echo "Waiting for processes to complete..."
    wait
    echo "All processes completed."

    subtest "Show some of the images"
    $IKUP display $CONCURRENT_IMAGES -r 1 -c 1 --no-upload

    subtest "List all uploaded images"
    run_command list | cut -f2- | sort
}

################################################################################

test_concurrent_mixed_noconcurrent() {
    start_test "Concurrent stream and file uploads, concurrent uploads disabled"

    export IKUP_ALLOW_CONCURRENT_UPLOADS=False

    subtest "Running concurrent upload commands"

    # Run may processes in concurrent with different parameters.
    for i in $(seq 1 5); do
        $IKUP upload $CONCURRENT_IMAGES -m d -r 1 -c 1  &
        $IKUP upload $CONCURRENT_IMAGES -m f -r 1 -c 1  &
        $IKUP upload $CONCURRENT_IMAGES -m d -r 1 -c 1  &
        $IKUP upload $CONCURRENT_IMAGES -m f -r 1 -c 1  &
        $IKUP upload $CONCURRENT_IMAGES --force-upload -m d -r 1  &
        $IKUP upload $CONCURRENT_IMAGES -m d -r 1  &
        $IKUP upload $CONCURRENT_IMAGES -m f -r 1  &
        $IKUP upload $CONCURRENT_IMAGES -m d -c 1  &
        $IKUP upload $CONCURRENT_IMAGES -m f -c 1  &
    done

    # Wait for all background processes to complete
    echo "Waiting for processes to complete..."
    wait
    echo "All processes completed."

    subtest "Show some of the images"
    $IKUP display $CONCURRENT_IMAGES -r 1 -c 1 --no-upload

    subtest "List all uploaded images"
    run_command list | cut -f2- | sort

    unset IKUP_ALLOW_CONCURRENT_UPLOADS
}

################################################################################

test_mark_uploaded() {
    start_test "Mark uploaded option"

    subtest "Default behavior (mark as uploaded)"
    run_command upload $DATA_DIR/tux.png
    run_command list -v

    subtest "Don't mark as uploaded (but it's already marked)"
    run_command upload $DATA_DIR/tux.png --mark-uploaded=false
    run_command list -v

    subtest "Don't mark as uploaded (but reupload, so it will be dirty)"
    run_command upload $DATA_DIR/tux.png --mark-uploaded=false --force-upload
    run_command list -v

    subtest "Explicitly mark as uploaded"
    run_command upload $DATA_DIR/tux.png --mark-uploaded=true
    run_command list -v $DATA_DIR/tux.png
}

################################################################################

test_concurrent_stalled() {
    start_test "Upload command delay and stall detection"

    # Set the stall timeout to a small value
    export IKUP_UPLOAD_STALL_TIMEOUT=0.1
    export IKUP_UPLOAD_PROGRESS_UPDATE_INTERVAL=0.01

    # Run a process with a long delay in the background
    IKUP_UPLOAD_COMMAND_DELAY=0.8 \
        $IKUP display $DATA_DIR/tux.png -r 2 -m direct --force-id 42 &
    sleep 0.3
    # Display another image with the same ID in the meanwhile
    $IKUP display $DATA_DIR/transparency.png -r 1 --force-id 42
    # There will be a short period when the second image is displayed
    sleep 0.8
    $IKUP list -v | grep -q "Uploading in progress" || echo "Failed to see that the upload is in progress"

    # Wait for the first process to finish
    wait
    echo "Display both images"
    run_command display $DATA_DIR/tux.png -r 2 --id-space 8bit
    run_command display $DATA_DIR/transparency.png -r 1 --id-space 8bit
    run_command list -v

    unset IKUP_UPLOAD_STALL_TIMEOUT
    unset IKUP_UPLOAD_PROGRESS_UPDATE_INTERVAL
}

################################################################################

test_named_pipe() {
    start_test "Sending commands through a named pipe"

    PIPE_NAME="$TMPDIR/named_pipe"
    mkfifo "$PIPE_NAME"

    tail -f "$PIPE_NAME" &
    TAIL_PID=$!

    run_command display $DATA_DIR/wikipedia.png -r 2 -O "$PIPE_NAME"
    run_command display $DATA_DIR/tux.png -r 2 -O "$PIPE_NAME"

    sleep 1.0
    kill $TAIL_PID

    # Clean up the named pipe
    rm "$PIPE_NAME"
}

################################################################################

test_fallback_dimensions() {
    start_test "Fallback dimensions when terminal size detection fails"

    subtest "Status with simulated terminal size failure"
    script -q -c "$IKUP status" < /dev/null

    subtest "Status with custom fallback dimensions"
    IKUP_FALLBACK_MAX_ROWS=10 IKUP_FALLBACK_MAX_COLS=40 \
        script -q -c "$IKUP status" < /dev/null

    subtest "Display image with fallback dimensions"
    script -q -c "$IKUP display $DATA_DIR/tux.png" < /dev/null

    subtest "Display with custom fallback dimensions"
    IKUP_FALLBACK_MAX_ROWS=5 IKUP_FALLBACK_MAX_COLS=20 \
        script -q -c "$IKUP display $DATA_DIR/tux.png" < /dev/null
}

################################################################################

# Run the tests.
for test in $TESTS_TO_RUN; do
    CURRENT_TEST_NAME="$test"
    $test
done
