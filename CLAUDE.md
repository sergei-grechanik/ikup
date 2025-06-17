# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

tupimage is a Python tool for displaying images in the terminal using the Kitty
graphics protocol. The tool provides both a CLI interface and Python API for
uploading, displaying, and managing terminal images with features like ID
assignment, concurrent uploads, and database caching.

## Development Commands

**Build and Install:**
```bash
uv build                        # Build source and wheel distributions
uv run tupimage --help          # Test CLI works
```

**Testing:**
There are three types of tests in the project:
- pytest unit tests
- CLI output comparison tests
- Screenshot tests

**Running pytest tests:**
```bash
uv run --extra test pytest
```

**Running CLI output tests:**
CLI tests must be run from a terminal that supports the Kitty graphics protocol,
like `st` (st should be installed in your environment).

```bash
# Run CLI tests and record individual test outputs:
xvfb-run st -e ./test_scripts/run-cli-tests.sh

# Compare the outputs against reference data:
uv run python -m tupimage.testing.output_comparison cli-test-outputs/ data/cli-test-references/

# A simpler comparison command (must be run from the project root, assumes uv):
test_scripts/compare-cli-test.sh cli-test-outputs
```

Note that the output you get from `xvfb-run st -e <command>` comes from the st
terminal, not from `<command>`. In most cases it may be ignored, unless you are
debugging an issue with an image not being displayed correctly.

It is also possible to run individual tests:
```bash
# List available CLI tests:
./test_scripts/run-cli-tests.sh --list

# Run specific CLI tests:
xvfb-run st -e ./test_scripts/run-cli-tests.sh test_basics test_display

# You can compare the whole output directory or just a single test:
uv run python -m tupimage.testing.output_comparison cli-test-outputs/test_basics.out data/cli-test-references/test_basics.reference

# A simpler command for individual test comparison:
test_scripts/compare-cli-test.sh cli-test-outputs/test_basics.out
```

**CLI Test Structure:**
- Each test function generates an individual output file in `cli-test-outputs/<test_name>.out`
- Reference files are stored in `data/cli-test-references/<test_name>.reference`
- The comparison script can compare either individual files or entire directories
- Individual tests can be compared using: `uv run python -m tupimage.testing.output_comparison cli-test-outputs/<test_name>.out data/cli-test-references/<test_name>.reference`

**Running screenshot tests:**
(TODO)
Screenshot tests take a very long time to run, so avoid running them. The
probability of them failing is quite low if everything else works.

## Debugging

**Terminal Environment Requirement:**
CRITICAL: tupimage CLI commands MUST be run within a proper terminal environment
that supports the Kitty graphics protocol. Attempting to debug or test tupimage
commands outside of this environment will result in errors like:

```
OSError: [Errno 6] No such device or address: '/dev/tty'
```

**Correct debugging pattern:**
```bash
# CORRECT - Debug CLI tests in proper terminal
xvfb-run st -e ./test_scripts/run-cli-tests.sh test_name

# CORRECT - Debug individual commands
xvfb-run st -e bash -c 'uv run tupimage display image.png'

# WRONG - Will fail with /dev/tty error
tupimage display image.png
uv run tupimage display image.png
python debug_script.py  # if it calls tupimage directly
```

**Why this is required:**
tupimage initializes `GraphicsTerminal` which attempts to open `/dev/tty` for
terminal communication. This fails when running outside a proper terminal
environment (e.g., in IDEs, simple shells, or scripts without tty allocation).

**Debug Terminal Helper:**
Use `test_scripts/debug-terminal.sh` for easier debugging with a persistent
terminal environment:

```bash
# Start persistent terminal (uses st by default)
./test_scripts/debug-terminal.sh start

# Start with custom terminal and options
./test_scripts/debug-terminal.sh start st -f "Liberation Mono" -e
./test_scripts/debug-terminal.sh start kitty

# Execute commands and get typescript + screenshot
./test_scripts/debug-terminal.sh exec uv run tupimage display image.png
./test_scripts/debug-terminal.sh exec uv run tupimage status

# Stop when done
./test_scripts/debug-terminal.sh stop
```

This tool provides:
- Persistent Xvfb + terminal environment (no need to restart for each command)
- Automatic `script` recording of all command output
- Screenshot capture after each command
- Escaped output for non-printable characters
- Timestamped output files in `debug-terminal/` directory
- Automatic display allocation (no conflicts with existing X servers)

## Development Conventions

**Commit Messages:**
- Keep all lines in commit messages to 72 characters or fewer
- Use imperative mood for the subject line
- Include detailed explanations in the body when needed
- Avoid too many emojis in commit messages
- Avoid using bold and italics in commit messages

## Architecture

**Core Components:**
- `tupimage_terminal.py` - Main API class `TupimageTerminal` that orchestrates image uploading/display
- `graphics_terminal.py` - Low-level terminal communication using Kitty graphics protocol
- `graphics_command.py` - Command building for Kitty protocol (TransmitCommand, PutCommand, etc.)
- `id_manager.py` - SQLite-based ID assignment and upload tracking with concurrent safety
- `cli.py` - Command-line interface with subcommands (display, upload, list, etc.)

**Key Design Patterns:**
- ID assignment uses configurable spaces (8bit, 16bit, 24bit, 32bit) and subspaces for collision avoidance
- Upload methods: FILE (temp files), DIRECT (streaming), auto-detection based on SSH
- Concurrent upload coordination through database locking and retry mechanisms
- Configuration system using TOML with environment variable overrides

**Data Flow:**
1. CLI parses arguments and creates `TupimageTerminal` instance
2. `assign_id()` creates `ImageInstance` with unique ID from `IDManager`
3. `upload()` handles image transmission via `GraphicsTerminal`
4. Database tracks upload status per terminal for reupload decisions
5. `display_only()` generates terminal placeholder text for image positioning

**Testing Structure:**
- `tests/` - Unit tests for core components
- `tupimage/testing/` - Screenshot testing infrastructure and screenshot tests
- `test_scripts/` - Various helper scripts for CLI and screenshot tests
- `test_scripts/run-cli-tests.sh` - The file containing CLI tests

## CLI Test Reference Files

The CLI test system uses a sophisticated pattern language in reference files to
handle dynamic content while ensuring consistency (this is very similar to
llvm's FileCheck utility). Reference files are stored in
`data/cli-test-references/` and use the following pattern syntax:

### Pattern Types

**Regular Expression Patterns: `{{pattern}}`**
`{{<regex>}}` will match the output against a regular expression pattern. It's
used for content that varies but doesn't need to be consistent across the test.
For example:
- `{{.*}}` - Matches any text (most common usage)
- `{{[0-9]+}}` - Matches numbers only

**Variable Capture and Reference: `[[variable:pattern]]` and `[[variable]]`**
- `[[tmpdir:.*]]` - Captures temporary directory path into "tmpdir" variable
- `[[id:.*]]` - Captures image ID into "id" variable
- `[[tmpdir]]` - References previously captured "tmpdir" variable (the output
  text must match the last captured value of `tmpdir`)

**Conditional Variable Capture: `[[variable?:pattern]]`**
- `[[wikipedia_png?:.*]]` - Captures into "wikipedia_png" only if not already set
This is a rarely used feature, it may be removed in the future.

**Function Transformations: `[[function(variable)]]`**
- `[[rgb(id)]]` - Converts numeric ID to RGB color format `r;g;b`
- Used for terminal color codes and other transformed output

**Skip Lines Directive: `{{:SKIP_LINES:}}`**
- Skips any number of input lines until the next reference line matches
- If used as the last line, skips all remaining input
- Useful for handling timing-dependent output, optional sections, or long
  sections that are not very important

### Example

A very common pattern is to match a graphics command, capturing the value of the
image id, and then using the rgb representation of this id when matching the
placeholder:
```
_Gi=[[id:.*]],t=f,q=2,f=100,a=T,U=1,r=1,c=3;[[wikipedia_png:.*]]\
[0m[38;2;[[rgb(id)]]m􎻮̅̅􎻮̅̍􎻮̅̎[0m[3DD
```
