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
#   -c, --command CMD  Command to test (default: "uv run --no-sync ikup")
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

    # Remove any existing new_files file
    rm -f $OUTPUT_DIR/new_files 2> /dev/null

    # Split the file by test markers
    awk -v output_dir="$OUTPUT_DIR" -v new_files="$OUTPUT_DIR/new_files" '
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
        print current_file >> new_files
        print > current_file
        next
    }
    current_file { print > current_file }
    ' "$OUTPUT_DIR/typescript"

    # Post-process each output file
    while IFS= read -r output_file; do
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
    done < "$OUTPUT_DIR/new_files"

    exit 0
fi

# Set default command if not provided
if [ -z "$IKUP" ]; then
    IKUP="uv run --no-sync ikup"
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
    $IKUP dirty --all --quiet
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

echorun() {
    printf "%s\n" "$*" >&2
    "$@"
    EXIT_CODE="$?"
    if [ $EXIT_CODE -ne 0 ]; then
        echo "Exit code: $EXIT_CODE"
    fi
}

AGENT="ikup terminal image viewer testscript (github.com/sergei-grechanik/ikup)"

[ -f $DATA_DIR/wikipedia.png ] || \
    curl -A "$AGENT" -o $DATA_DIR/wikipedia.png https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/440px-Wikipedia-logo-v2.svg.png
[ -f $DATA_DIR/transparency.png ] || \
    curl -A "$AGENT" -o $DATA_DIR/transparency.png https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png
[ -f $DATA_DIR/tux.png ] || \
    curl -A "$AGENT" -o $DATA_DIR/tux.png https://upload.wikimedia.org/wikipedia/commons/a/af/Tux.png
[ -f $DATA_DIR/column.png ] || \
    curl -A "$AGENT" -o $DATA_DIR/column.png "https://upload.wikimedia.org/wikipedia/commons/9/95/Column6.png"
[ -f $DATA_DIR/small_arrow.png ] || \
    curl -A "$AGENT" -o $DATA_DIR/small_arrow.png "https://upload.wikimedia.org/wikipedia/commons/b/ba/Arrow-up.png"
[ -f $DATA_DIR/ruler.png ] || \
    curl -A "$AGENT" -o $DATA_DIR/ruler.png "https://upload.wikimedia.org/wikipedia/commons/3/38/Screen_Ruler.png"
[ -f $DATA_DIR/earth.jpg ] || \
    curl -A "$AGENT" -o $DATA_DIR/earth.jpg "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cb/The_Blue_Marble_%28remastered%29.jpg/240px-The_Blue_Marble_%28remastered%29.jpg"
[ -f $DATA_DIR/mars.jpg ] || \
    curl -A "$AGENT" -o $DATA_DIR/mars.jpg "https://upload.wikimedia.org/wikipedia/commons/0/02/OSIRIS_Mars_true_color.jpg"
[ -f $DATA_DIR/sun.jpg ] || \
    curl -A "$AGENT" -o $DATA_DIR/sun.jpg "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/The_Sun_by_the_Atmospheric_Imaging_Assembly_of_NASA%27s_Solar_Dynamics_Observatory_-_20100819.jpg/628px-The_Sun_by_the_Atmospheric_Imaging_Assembly_of_NASA%27s_Solar_Dynamics_Observatory_-_20100819.jpg"
[ -f $DATA_DIR/butterfly.jpg ] || \
    curl -A "$AGENT" -o $DATA_DIR/butterfly.jpg "https://upload.wikimedia.org/wikipedia/commons/a/a6/Peacock_butterfly_%28Aglais_io%29_2.jpg"
[ -f $DATA_DIR/david.jpg ] || \
    curl -A "$AGENT" -o $DATA_DIR/david.jpg "https://upload.wikimedia.org/wikipedia/commons/8/84/Michelangelo%27s_David_2015.jpg"
[ -f $DATA_DIR/fern.jpg ] || \
    curl -A "$AGENT" -o $DATA_DIR/fern.jpg "https://upload.wikimedia.org/wikipedia/commons/3/3d/Giant_fern_forest_7.jpg"
[ -f $DATA_DIR/flake.jpg ] || \
    curl -A "$AGENT" -o $DATA_DIR/flake.jpg "https://upload.wikimedia.org/wikipedia/commons/d/d7/Snowflake_macro_photography_1.jpg"
[ -f $DATA_DIR/flower.jpg ] || \
    curl -A "$AGENT" -o $DATA_DIR/flower.jpg "https://upload.wikimedia.org/wikipedia/commons/4/40/Sunflower_sky_backdrop.jpg"
[ -f $DATA_DIR/a_panorama.jpg ] || \
    curl -A "$AGENT" -o $DATA_DIR/a_panorama.jpg "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Kazbeg_Panorama.jpg/2560px-Kazbeg_Panorama.jpg"

################################################################################

if [ -z "$DATABASE_DIR" ]; then
    DATABASE_DIR="$TMPDIR/id_database_dir"
fi

export IKUP_CONFIG="DEFAULT"
export IKUP_ID_DATABASE_DIR="$DATABASE_DIR"
export IKUP_CACHE_DIR="$TMPDIR/cache"
# Set a smaller tolerance for the cache tests.
export IKUP_THUMBNAIL_FILE_SIZE_TOLERANCE=0.05

# Disable 3rd diacritics because they are hard to match with the reference. We
# will test them only in fixed id tests.
export IKUP_ID_SPACE="24bit"

################################################################################

test_place_specification() {
    start_test "Box specification parsing and functionality"

    subtest "Basic dimension specifications"
    run_command $DATA_DIR/wikipedia.png --box 3x2
    run_command $DATA_DIR/wikipedia.png -b 5x1

    subtest "Comma variant for dimensions"
    run_command $DATA_DIR/wikipedia.png --box 4,3

    subtest "Position only specifications"
    run_command $DATA_DIR/wikipedia.png --box @1x2
    run_command $DATA_DIR/wikipedia.png -b @3,4

    subtest "Combined dimension and position"
    run_command $DATA_DIR/wikipedia.png --box 2x3@5x6
    run_command $DATA_DIR/wikipedia.png -b 3,2@4,5

    subtest "Unspecified rows"
    run_command $DATA_DIR/wikipedia.png --box 4x_
    run_command $DATA_DIR/wikipedia.png -b 3,_

    subtest "Formula variants"
    run_command $DATA_DIR/wikipedia.png -b _x4~1+1,2+1@3+2,4+1

    subtest "Max constraints"
    run_command $DATA_DIR/wikipedia.png --box "_,_~5,3"
    run_command $DATA_DIR/wikipedia.png -b "_,3~6,_"
    run_command $DATA_DIR/wikipedia.png --box "~2,2"

    subtest "Multiple images with individual box specs"
    run_command $DATA_DIR/wikipedia.png $DATA_DIR/tux.png --box 2x1 --box 3x2
    run_command $DATA_DIR/wikipedia.png $DATA_DIR/tux.png -b 2x1 -b 3x2

    subtest "Upload command with box specification"
    run_command upload $DATA_DIR/wikipedia.png --box 4x3

    subtest "Error cases - mismatched box count"
    run_command $DATA_DIR/wikipedia.png $DATA_DIR/tux.png --box 3x2
    run_command $DATA_DIR/wikipedia.png --box 2x1 --box 3x2

    subtest "Error cases - conflicting specifications"
    run_command $DATA_DIR/wikipedia.png --box 3x2 --cols 5
    run_command $DATA_DIR/wikipedia.png --box @1x2 --position 3,4
    run_command $DATA_DIR/wikipedia.png --box "_,3~5,_" --max-cols 10

    subtest "Error cases - invalid specifications"
    run_command $DATA_DIR/wikipedia.png --box ""
    run_command $DATA_DIR/wikipedia.png --box @5
    run_command $DATA_DIR/wikipedia.png --box "invalid"
    run_command $DATA_DIR/wikipedia.png --box "@_,1"
    run_command $DATA_DIR/wikipedia.png --box "~_,1"
    run_command $DATA_DIR/wikipedia.png --box 2+1x3
}

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

    subtest "Display through file with append"
    run_command $DATA_DIR/wikipedia.png -r 2 -o $TMPDIR/append_test.txt
    cat $TMPDIR/append_test.txt
    run_command $DATA_DIR/wikipedia.png -r 1 -o $TMPDIR/append_test.txt --append
    cat $TMPDIR/append_test.txt
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

    subtest "Cols > max-cols, scale down"
    run_command $DATA_DIR/wikipedia.png -c 10 --max-cols 3

    subtest "Rows > max-rows, scale down"
    run_command $DATA_DIR/wikipedia.png -r 10 --max-rows 1

    subtest "Many cols, make sure we are within max-rows"
    run_command $DATA_DIR/wikipedia.png -c 10 --max-rows 1

    subtest "Cols > max-cols, rows > max-rows, fit to the maximum box"
    run_command $DATA_DIR/wikipedia.png -c 10 -r 10 --max-cols 3 --max-rows 4

    subtest "Cols > max-cols, rows < max-rows, shrink cols, keep rows"
    run_command $DATA_DIR/wikipedia.png -c 20 -r 1 --max-cols 10 --max-rows 4
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

    subtest "list -p"
    run_command list -p '%cx%r %i %%\\ %i\n%x\t%p %P %m %a %D'

    subtest "list -p, incorrect format"
    run_command list -p '%O'
    run_command list -p '\o'
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
    run_command list -p "%cx%r\t%p" | sort
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
    IKUP_FALLBACK_TERM_SIZE=40x10 \
        script -q -c "$IKUP status" < /dev/null

    subtest "Display image with fallback dimensions"
    script -q -c "$IKUP display $DATA_DIR/tux.png" < /dev/null

    subtest "Display with custom fallback dimensions"
    IKUP_FALLBACK_TERM_SIZE=20x5 \
        script -q -c "$IKUP display $DATA_DIR/tux.png" < /dev/null
}

################################################################################

test_validation() {
    start_test "Validation of CLI options and environment variables"

    subtest "Invalid string values for cols/rows"
    run_command placeholder 123 --cols invalid --rows 5
    run_command placeholder 123 --cols 5 --rows invalid
    run_command display $DATA_DIR/earth.jpg --cols abc --rows 5
    run_command upload $DATA_DIR/earth.jpg --rows xyz --cols 3

    subtest "Negative values for cols/rows"
    run_command placeholder 123 --cols -1 --rows 5
    run_command placeholder 123 --cols 5 --rows -10
    run_command display $DATA_DIR/earth.jpg --cols -5 --rows 3
    run_command upload $DATA_DIR/earth.jpg --rows -2 --cols 4

    subtest "Zero values for cols/rows"
    run_command placeholder 123 --cols 0 --rows 5
    run_command placeholder 123 --cols 5 --rows 0
    run_command display $DATA_DIR/earth.jpg --cols 0 --rows 3
    run_command upload $DATA_DIR/earth.jpg --rows 0 --cols 4

    subtest "Invalid string values for scale"
    run_command display $DATA_DIR/earth.jpg --scale invalid
    run_command display $DATA_DIR/earth.jpg -s abc
    run_command upload $DATA_DIR/earth.jpg --scale xyz

    subtest "Zero and negative values for scale"
    run_command display $DATA_DIR/earth.jpg --scale 0
    run_command display $DATA_DIR/earth.jpg --scale -1.5
    run_command upload $DATA_DIR/earth.jpg -s -0.1

    subtest "Too large values for scale"
    run_command display $DATA_DIR/earth.jpg --scale 1000001
    run_command upload $DATA_DIR/earth.jpg -s 9999999.0

    subtest "Invalid IKUP_SCALE environment variable"
    IKUP_SCALE=invalid run_command display $DATA_DIR/earth.jpg
    IKUP_SCALE=0 run_command display $DATA_DIR/earth.jpg
    IKUP_SCALE=-1 run_command display $DATA_DIR/earth.jpg
    IKUP_SCALE=1000001 run_command display $DATA_DIR/earth.jpg

    subtest "Invalid IKUP_GLOBAL_SCALE environment variable"
    IKUP_GLOBAL_SCALE=invalid run_command display $DATA_DIR/earth.jpg
    IKUP_GLOBAL_SCALE=0 run_command display $DATA_DIR/earth.jpg
    IKUP_GLOBAL_SCALE=-2.5 run_command display $DATA_DIR/earth.jpg
    IKUP_GLOBAL_SCALE=2000000 run_command display $DATA_DIR/earth.jpg

    subtest "Invalid max cols/rows values"
    run_command display $DATA_DIR/earth.jpg --max-cols 0
    run_command display $DATA_DIR/earth.jpg --max-rows 0
    run_command upload $DATA_DIR/earth.jpg --max-cols -5
    run_command upload $DATA_DIR/earth.jpg --max-rows -2
}

################################################################################

test_cache_basic() {
    start_test "Basic cache functionality"

    # Clear cache before starting
    subtest "Clear cache"
    run_command cache remove --all
    run_command cache list

    subtest "Test resizing to specific dimensions (WxH)"
    run_command cache convert $DATA_DIR/earth.jpg -s 100x80
    run_command cache convert $DATA_DIR/butterfly.jpg --size 50x50 --format png
    run_command cache list

    subtest "Test resizing with width only (automatic height)"
    run_command cache convert $DATA_DIR/tux.png --width 64
    run_command cache convert $DATA_DIR/ruler.png --width 200 --format jpeg
    run_command cache convert $DATA_DIR/ruler.png --width 100 --format jpeg
    run_command cache list

    subtest "Test resizing with height only. Check idempotence."
    sun1="$(run_command cache convert $DATA_DIR/sun.jpg --height 75 --format png)"
    stat -c '%y' "$sun1"
    identify "$sun1"
    sun2="$(run_command cache convert $DATA_DIR/sun.jpg --height 75 --format png)"
    stat -c '%y' "$sun2"
    identify "$sun2"
    run_command cache list

    subtest "Test format conversion without resizing"
    run_command cache convert $DATA_DIR/earth.jpg --format png
    run_command cache convert $DATA_DIR/tux.png --format jpeg
    run_command cache list

    subtest "Test cache status functionality"
    run_command cache status
    subtest "Test cache purge functionality"
    run_command cache purge
    run_command cache list
    subtest "Test cache status after purge"
    run_command cache status
}

################################################################################

test_cache_cleanup() {
    start_test "Cache cleanup functionality"

    # Clear cache before starting
    subtest "Clear cache"
    run_command cache purge
    run_command cache status

    subtest "Test cleanup by image count limit"
    # Set very small limits: max 2 images, cleanup to 1 image
    export IKUP_CACHE_MAX_IMAGES=2
    export IKUP_CACHE_MAX_TOTAL_SIZE_BYTES=100000
    export IKUP_CLEANUP_TARGET=0.5  # 2 * 0.5 = 1 image

    # Add 4 small images to trigger image count cleanup
    run_command cache convert $DATA_DIR/tux.png --width 10 --height 10
    run_command cache convert $DATA_DIR/earth.jpg --width 10 --height 10
    run_command cache status
    echo "No cleanup should be needed yet"
    run_command cache cleanup
    run_command cache convert $DATA_DIR/butterfly.jpg --width 10 --height 10
    echo "At this point cleanup is done automatically"
    run_command cache convert $DATA_DIR/sun.jpg --width 10 --height 10

    echo "Verify we now have 2 images"
    run_command cache status
    echo "Check that we retain the newest images"
    run_command cache list

    subtest "Test cleanup by total size limit"
    # Clear cache and set size-based limits
    run_command cache purge
    export IKUP_CACHE_MAX_IMAGES=5
    export IKUP_CACHE_MAX_TOTAL_SIZE_BYTES=50000  # Small size limit ~50KB
    export IKUP_CLEANUP_TARGET=0.4  # Cleanup to 40% of limit = ~20KB

    # Add larger images that will exceed size limit
    run_command cache convert $DATA_DIR/david.jpg -b 5000
    run_command cache convert $DATA_DIR/flower.jpg -b 15000
    run_command cache convert $DATA_DIR/transparency.png -b 10000
    run_command cache convert $DATA_DIR/mars.jpg -b 10000
    run_command cache convert $DATA_DIR/wikipedia.png -b 8000
    run_command cache status
    echo "No cleanup should be needed yet"
    run_command cache cleanup
    run_command cache convert $DATA_DIR/butterfly.jpg -b 12000

    # Run cleanup - should remove oldest images to get under size limit
    run_command cache cleanup
    echo "Verify cache is now under size limit 20KB"
    run_command cache status
    echo "Check that we retain the newest images"
    run_command cache list

    unset IKUP_CACHE_MAX_IMAGES
    unset IKUP_CACHE_MAX_TOTAL_SIZE_BYTES
    unset IKUP_CLEANUP_TARGET
}

################################################################################

test_cache_max_bytes() {
    start_test "Cache max-bytes functionality"

    # Clear cache before starting
    subtest "Clear cache"
    run_command cache remove --all
    run_command cache list

    subtest "Test conversion to larger size than original (no resize should happen)"
    echorun stat -c %s $DATA_DIR/earth.jpg
    run_command cache convert $DATA_DIR/earth.jpg --max-bytes 1000000
    run_command cache list $DATA_DIR/earth.jpg

    subtest "Test conversion to smaller size"
    run_command cache convert $DATA_DIR/earth.jpg --max-bytes 5000 --format png
    run_command cache convert $DATA_DIR/earth.jpg --max-bytes 4500 --format png
    run_command cache list $DATA_DIR/earth.jpg

    subtest "Test png conversion to smaller size"
    echorun stat -c %s $DATA_DIR/transparency.png
    run_command cache convert $DATA_DIR/transparency.png --max-bytes 100000
    run_command cache convert $DATA_DIR/transparency.png --max-bytes 101000
    run_command cache convert $DATA_DIR/transparency.png --max-bytes 99000
    run_command cache convert $DATA_DIR/transparency.png --max-bytes 94000
    run_command cache list $DATA_DIR/transparency.png

    subtest "Test conversion to very small size (should get 1x1)"
    echorun stat -c %s $DATA_DIR/butterfly.jpg
    run_command cache convert $DATA_DIR/butterfly.jpg --max-bytes 500 --format png
    run_command cache list $DATA_DIR/butterfly.jpg
    run_command cache convert $DATA_DIR/butterfly.jpg --max-bytes 700 --format png
    run_command cache list $DATA_DIR/butterfly.jpg

    subtest "Test PNG to JPEG conversion with size limits"
    run_command cache convert $DATA_DIR/tux.png --max-bytes 3000 --format jpeg
    run_command cache convert $DATA_DIR/wikipedia.png --max-bytes 8000 --format jpeg
    run_command cache list $DATA_DIR/tux.png
    run_command cache list $DATA_DIR/wikipedia.png

    subtest "Test JPEG to PNG conversion with size limits"
    run_command cache convert $DATA_DIR/mars.jpg --max-bytes 10000 --format png
    run_command cache convert $DATA_DIR/sun.jpg --max-bytes 15000 --format png
    run_command cache list $DATA_DIR/mars.jpg
    run_command cache list $DATA_DIR/sun.jpg
}

################################################################################

test_cache_check() {
    start_test "Cache check functionality"

    # Clear cache before starting
    subtest "Clear cache"
    run_command cache remove --all
    run_command cache list

    subtest "Convert images to cache"
    run_command cache convert $DATA_DIR/earth.jpg --width 80 --height 80
    run_command cache convert $DATA_DIR/butterfly.jpg --max-bytes 8000 --format png

    subtest "Check the cache for width/height combinations"
    run_command cache check $DATA_DIR/earth.jpg --width 80 --height 80
    run_command cache check $DATA_DIR/earth.jpg --width 80
    run_command cache check $DATA_DIR/earth.jpg --width 80 --height 81
    run_command cache check $DATA_DIR/earth.jpg --width 80 --height 80 --format png
    run_command cache check $DATA_DIR/earth.jpg --width 80 --height 80 --format jpeg

    subtest "Test single dimension tolerance behavior"
    # Create a cache entry with specific dimensions (64x75 for tux.png)
    run_command cache convert $DATA_DIR/tux.png --width 64
    # Check that exact width matches
    run_command cache check $DATA_DIR/tux.png --width 64
    # Check that slightly different width doesn't match (no tolerance for explicit dimensions)
    run_command cache check $DATA_DIR/tux.png --width 65
    # Check that height-only queries also don't use tolerance
    run_command cache check $DATA_DIR/tux.png --height 75
    run_command cache check $DATA_DIR/tux.png --height 76

    subtest "Check the cache for max-bytes"
    run_command cache check $DATA_DIR/butterfly.jpg --max-bytes 8050 --format png
    run_command cache check $DATA_DIR/butterfly.jpg --max-bytes 7999 --format png

    subtest "These images should not be found"
    run_command cache check $DATA_DIR/butterfly.jpg --max-bytes 7610 --format png
    run_command cache check $DATA_DIR/butterfly.jpg --max-bytes 8401 --format png

    subtest "Test max-bytes check with a very big request"
    echo "This image shouldn't be found in the cache"
    run_command cache check $DATA_DIR/tux.png --max-bytes 100000
    run_command cache check $DATA_DIR/tux.png --max-bytes 11913

    echo "Now request a large image"
    run_command cache convert $DATA_DIR/tux.png --max-bytes 100000
    echo "The image should be found in the cache now"
    run_command cache check $DATA_DIR/tux.png --max-bytes 100000
    run_command cache check $DATA_DIR/tux.png --max-bytes 11913
    echo "But a smaller image should not be found"
    run_command cache check $DATA_DIR/tux.png --max-bytes 11900

    subtest "Test max-bytes check with a very small request"
    run_command cache convert $DATA_DIR/tux.png --max-bytes 10
    subtest "This should return the minimal image and report impossibility"
    run_command cache check $DATA_DIR/tux.png --max-bytes 20

    subtest "Corrupt the cache"
    cached_file="$($IKUP cache convert $DATA_DIR/butterfly.jpg --max-bytes 8000 --format png)"
    echorun rm "$cached_file"
    echo "The next command should return an error"
    run_command cache check $DATA_DIR/butterfly.jpg --max-bytes 8000 --format png
    run_command cache check $DATA_DIR/butterfly.jpg --max-bytes 8000 --format png
    echo "The next command should recreate the file"
    run_command cache convert $DATA_DIR/butterfly.jpg --max-bytes 8000 --format png
    run_command cache check $DATA_DIR/butterfly.jpg --max-bytes 8000 --format png
    cached_file="$($IKUP cache convert $DATA_DIR/butterfly.jpg --max-bytes 8000 --format png)"
    echorun cp $DATA_DIR/butterfly.jpg "$cached_file"
    echo "The next command should return another error"
    run_command cache check $DATA_DIR/butterfly.jpg --max-bytes 8000 --format png
}

################################################################################

test_cache_column() {
    start_test "Cache max-bytes functionality, a tricky column image"

    # Clear cache before starting
    subtest "Clear cache"
    run_command cache remove --all
    run_command cache list

    run_command cache convert .cli-tests-data/column.png -b 1000
    run_command cache check .cli-tests-data/column.png -b 1000
    echo "The next command must return no image"
    run_command cache check .cli-tests-data/column.png -b 10000

    echo "Now check that a big image is found after conversion"
    run_command cache convert .cli-tests-data/column.png -b 1000000
    run_command cache check .cli-tests-data/column.png -b 1000000
}

################################################################################

test_cache_concurrent() {
    start_test "Concurrent cache conversion"

    # Clear cache before starting
    subtest "Clear cache"
    run_command cache remove --all
    run_command cache list

    subtest "Test multiple concurrent conversions"

    SIZES="1000 2000 10000 100000 101000 99000 102000 98000 1000000"

    # Build many cache commands
    for img in $DATA_DIR/butterfly.jpg $DATA_DIR/column.png $DATA_DIR/tux.png; do
        for size in $SIZES; do
            echo " $img --max-bytes $size "
        done
    done > "$TMPDIR/cache_concurrent_commands.txt"

    # Repeat them several times and shuffle
    for i in $(seq 1 5); do
        cat "$TMPDIR/cache_concurrent_commands.txt"
    done | shuf > "$TMPDIR/cache_concurrent_commands_shuf.txt"

    # Run the shuffled commands
    echo "Starting background processes"
    while read -r command; do
        $IKUP cache convert $command >> "$TMPDIR/outputs.txt" &
    done < "$TMPDIR/cache_concurrent_commands_shuf.txt"

    echo "Waiting for background processes to complete..."
    wait

    echorun wc -l "$TMPDIR/cache_concurrent_commands_shuf.txt"
    echorun wc -l "$TMPDIR/outputs.txt"
    echo "Unique outputs: $(cat "$TMPDIR/outputs.txt" | sort | uniq | wc -l)"

    # Check the original commands
    echo "Checking the cache"
    while read -r command; do
        run_command cache check $command
    done < "$TMPDIR/cache_concurrent_commands.txt"
}

################################################################################

test_upload_size_limits() {
    start_test "Upload size limits validation"

    # Clear cache before starting
    subtest "Clear cache"
    run_command cache remove --all

    subtest "Test file upload size limit with large image"
    # Set a low file upload limit (15KB) and upload a large image
    export IKUP_FILE_MAX_SIZE=15360
    export IKUP_UPLOAD_METHOD=file
    run_command display $DATA_DIR/wikipedia.png
    run_command cache list $DATA_DIR/wikipedia.png
    unset IKUP_FILE_MAX_SIZE
    unset IKUP_UPLOAD_METHOD

    subtest "Test stream upload size limit with large image"
    # Set a low stream upload limit (10KB) and upload a large image
    export IKUP_STREAM_MAX_SIZE=10240
    export IKUP_UPLOAD_METHOD=direct
    run_command display $DATA_DIR/butterfly.jpg
    run_command cache list $DATA_DIR/butterfly.jpg
    unset IKUP_STREAM_MAX_SIZE
    unset IKUP_UPLOAD_METHOD

    subtest "Test tiny upload limit forces heavy optimization"
    # Set very tiny limit that forces aggressive optimization
    export IKUP_FILE_MAX_SIZE=1024
    export IKUP_UPLOAD_METHOD=file
    run_command display $DATA_DIR/earth.jpg
    run_command cache list $DATA_DIR/earth.jpg
    unset IKUP_FILE_MAX_SIZE
    unset IKUP_UPLOAD_METHOD
}

################################################################################

test_upload_quality() {
    start_test "Quality optimization with different file size limits"

    subtest "Clear conversion cache"
    run_command cache remove --all

    subtest "Upload with small file size limit"
    echo "Setting IKUP_FILE_MAX_SIZE=8192 and uploading image"
    export IKUP_FILE_MAX_SIZE=8192
    export IKUP_UPLOAD_METHOD=file
    run_command display $DATA_DIR/butterfly.jpg
    echo "Check list -v that it's uploaded with quality < 1.0"
    run_command list -v $DATA_DIR/butterfly.jpg

    subtest "Upload with even smaller file size limit"
    echo "Setting IKUP_FILE_MAX_SIZE=4096 and uploading same image"
    export IKUP_FILE_MAX_SIZE=4096
    run_command display $DATA_DIR/butterfly.jpg
    echo "Check that list -v shows that the quality is the same"
    run_command list -v $DATA_DIR/butterfly.jpg

    subtest "Upload with slightly larger file size limit"
    echo "Setting IKUP_FILE_MAX_SIZE=9000 and uploading same image"
    export IKUP_FILE_MAX_SIZE=9000
    run_command display $DATA_DIR/butterfly.jpg
    echo "Check that list -v shows that the quality is the same again"
    run_command list -v $DATA_DIR/butterfly.jpg

    subtest "Upload with larger file size limit"
    echo "Setting IKUP_FILE_MAX_SIZE=16384 and uploading same image"
    export IKUP_FILE_MAX_SIZE=16384
    run_command display $DATA_DIR/butterfly.jpg
    echo "Check that list -v shows that the quality is now larger"
    run_command list -v $DATA_DIR/butterfly.jpg

    subtest "Upload without file size limit"
    echo "Unsetting IKUP_FILE_MAX_SIZE and uploading same image"
    unset IKUP_FILE_MAX_SIZE
    run_command display $DATA_DIR/butterfly.jpg
    echo "Check that list -v shows that the quality is now 1.0"
    run_command list -v $DATA_DIR/butterfly.jpg

    subtest "Upload with small file size limit again"
    echo "Setting IKUP_FILE_MAX_SIZE=8192 again and uploading same image"
    export IKUP_FILE_MAX_SIZE=8192
    run_command display $DATA_DIR/butterfly.jpg
    echo "Check that list -v shows that the quality is still 1.0"
    run_command list -v $DATA_DIR/butterfly.jpg

    unset IKUP_FILE_MAX_SIZE
    unset IKUP_UPLOAD_METHOD
}

################################################################################

test_concurrent_quality_uploads() {
    start_test "Concurrent uploads with different quality settings"

    subtest "Clear conversion cache"
    run_command cache remove --all

    subtest "Running many concurrent upload processes"
    echo "Starting many concurrent uploads with different size limits"

    # Run many processes in concurrent with different size limits
    LIMITS1="2000 4000 8000 16000 32000"
    LIMITS2="2200 4400 8800 17600 35200"
    LIMITS3="2420 4840 9680 19360 38720"
    LIMITS4="2662 99000000 5324 10648 21296 42592"
    for size in $LIMITS1 $LIMITS2 $LIMITS3 $LIMITS4; do
        for i in $(seq 1 2); do
            # Upload with file method
            IKUP_FILE_MAX_SIZE=$size IKUP_UPLOAD_METHOD=file $IKUP upload $DATA_DIR/butterfly.jpg -r 1 -c 1 &
            # Upload with direct method
            IKUP_STREAM_MAX_SIZE=$size IKUP_UPLOAD_METHOD=direct $IKUP upload $DATA_DIR/butterfly.jpg -r 1 -c 1 &
        done
    done

    echo "Waiting for all processes to complete"
    wait
    echo "All processes completed"

    subtest "Check final quality result"
    echo "All uploads completed, checking final quality"
    run_command list -v $DATA_DIR/butterfly.jpg
}

################################################################################

test_placeholder_formulas() {
    start_test "Placeholder formulas and positioning"

    run_command upload $DATA_DIR/wikipedia.png -r 2
    ID=$($IKUP get-id $DATA_DIR/wikipedia.png -r 2)

    subtest "Formula-derived placeholder size"
    run_command placeholder $ID --cols 'tc/70' --rows 'tr/5'

    subtest "Placeholder positioning formulas"
    run_command placeholder $ID --cols 2 --rows 1 --pos 'tc-ec,tr-er'

    subtest "Restore cursor flag without explicit value"
    run_command placeholder $ID --cols 6 --rows 3 --pos '5,2' --restore-cursor
}

################################################################################

test_position() {
    start_test "Image positioning"

    subtest "Absolute positioning, corners and in the middle"
    $IKUP $DATA_DIR/wikipedia.png --max-rows 4 --pos 0,0
    $IKUP $DATA_DIR/tux.png --max-rows 4 --pos tc-c,0
    $IKUP $DATA_DIR/a_panorama.jpg --max-cols 10 --pos 0,tr-r
    $IKUP $DATA_DIR/earth.jpg -r 5 --pos tc-c,tr-r
    # Two images in the middle. Position is applied to the first one, the second
    # one is placed immediately below it.
    $IKUP $DATA_DIR/david.jpg $DATA_DIR/butterfly.jpg --max-rows 4 --pos '(tc-c)/2+0.5,(tr-r)/2+0.5'
}

################################################################################

test_position_file_out() {
    start_test "Image positioning, output goes to file"

    subtest "Absolute positioning, corners and in the middle"
    $IKUP --append -o $TMPDIR/out.txt $DATA_DIR/wikipedia.png --max-rows 4 --pos 0,0
    $IKUP --append -o $TMPDIR/out.txt $DATA_DIR/tux.png --max-rows 4 --pos tc-c,0
    $IKUP --append -o $TMPDIR/out.txt $DATA_DIR/a_panorama.jpg --max-cols 10 --pos 0,tr-r
    $IKUP --append -o $TMPDIR/out.txt $DATA_DIR/earth.jpg -r 5 --pos tc-c,tr-r
    $IKUP --append -o $TMPDIR/out.txt $DATA_DIR/david.jpg $DATA_DIR/butterfly.jpg --max-rows 4 --pos '(tc-c)/2+0.5,(tr-r)/2+0.5'

    cat $TMPDIR/out.txt
}

################################################################################

test_position_conflicts() {
    start_test "Positioning constraints"

    subtest "Display with positioning and line feeds"
    run_command $DATA_DIR/wikipedia.png --max-rows 2 --pos '0,0' --use-line-feeds true

    subtest "Placeholder with positioning and line feeds"
    ID=$($IKUP get-id $DATA_DIR/small_arrow.png -r 2)
    run_command placeholder $ID --cols 4 --rows 2 --pos '1,1' --use-line-feeds true
}

################################################################################

test_formulas_basic() {
    start_test "Basic formula functionality in CLI"

    run_command $DATA_DIR/wikipedia.png --rows '10-2*3'
    run_command $DATA_DIR/wikipedia.png --rows '(10-2)*3'
    run_command $DATA_DIR/small_arrow.png --rows 'floor(3.8)'
    run_command $DATA_DIR/small_arrow.png --rows 'ceil(3.8)'
}

################################################################################

test_formulas_errors() {
    start_test "Formula error handling"

    subtest "Invalid formula syntax"
    run_command $DATA_DIR/wikipedia.png --cols '2+'
    run_command $DATA_DIR/tux.png --rows 'invalid_function(5)'
    run_command $DATA_DIR/small_arrow.png --max-cols '2 ** 3'

    subtest "Unknown variables"
    run_command $DATA_DIR/wikipedia.png --cols 'unknown_var'
    run_command $DATA_DIR/tux.png --rows 'fake_variable + 1'

    subtest "Division by zero"
    run_command $DATA_DIR/wikipedia.png --cols '10/0'
    run_command $DATA_DIR/tux.png --max-rows '5/(2-2)'

    subtest "Invalid function calls"
    run_command $DATA_DIR/wikipedia.png --cols 'min()'
    run_command $DATA_DIR/tux.png --rows 'ceil(1,2,3)'
    run_command $DATA_DIR/small_arrow.png --max-cols 'unknown_func(5)'

    subtest "Positioning formula errors"
    run_command $DATA_DIR/wikipedia.png --pos 'invalid_pos_var,5'
    run_command $DATA_DIR/tux.png --pos '5/0,tr/2'
}

################################################################################

test_restore_cursor() {
    start_test "Cursor restoration functionality"

    clear

    subtest "Automatic restore cursor with positioning"
    run_command $DATA_DIR/wikipedia.png --max-rows 3 --pos '10,5'

    subtest "Explicit restore cursor settings"
    run_command $DATA_DIR/tux.png --max-rows 3 --pos '15,8' --restore-cursor true

    subtest "No-value restore cursor (same as true)"
    run_command $DATA_DIR/small_arrow.png --max-rows 3 --pos '5,2' --restore-cursor

    subtest "Auto restore cursor behavior"
    run_command $DATA_DIR/wikipedia.png --max-rows 3 --pos 'tc/2,tr/2' --restore-cursor auto

    subtest "Disable restore cursor"
    run_command $DATA_DIR/small_arrow.png --max-rows 3 --pos '5,2' --restore-cursor false
}

################################################################################

test_formulas_multiple_images() {
    start_test "Formulas with multiple images"

    clear

    subtest "Multiple images with different number of rows"
    # The number of rows is calculated for each image separately using the same
    # formula but with different cursor position.
    run_command $DATA_DIR/wikipedia.png $DATA_DIR/tux.png $DATA_DIR/transparency.png $DATA_DIR/small_arrow.png $DATA_DIR/wikipedia.png --rows '(tr-cy)/3'
}

################################################################################

test_multi_command() {
    start_test "Multi-command mode with colon separators"

    subtest "Multi-command with multiple colons as separators"
    run_command upload $DATA_DIR/small_arrow.png -r 1 ::: get-id $DATA_DIR/transparency.png -r 2

    subtest "Complex multi-command with different command types"
    ID1=$($IKUP get-id $DATA_DIR/wikipedia.png -r 2)
    ID2=$($IKUP get-id $DATA_DIR/tux.png -r 3)
    run_command display $ID1 --no-upload : placeholder $ID2 --cols 5 --rows 3 : list --last 2

    subtest "Multi-command error handling (invalid command should fail)"
    run_command status : invalid-command : status
}

################################################################################

# Run the tests.
for test in $TESTS_TO_RUN; do
    CURRENT_TEST_NAME="$test"
    $test
done
