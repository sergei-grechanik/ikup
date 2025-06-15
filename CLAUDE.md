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
# Run CLI tests in a terminal and record the output in `typescript`:
xvfb-run st -e script -e -c "./test_scripts/run-cli-tests.sh"
# Post-process the CLI output:
./test_scripts/postprocess-cli-typescript.sh typescript
# Compare the output against reference data:
uv run python -m tupimage.testing.output_comparison typescript data/cli-tests.reference
```

It is also possible to run individual tests:
```bash
# List available CLI tests:
./test_scripts/run-cli-tests.sh --list
# Run specific CLI tests:
xvfb-run st -e script -e -c "./test_scripts/run-cli-tests.sh test_basics test_display"
# Post-processing and comparison is done the same way as above.
```

**Running screenshot tests:**
(TODO)
Screenshot tests take a very long time to run, so avoid running them. The
probability of them failing is quite low if everything else works.


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
- `tupimage/testing/` - Integration tests and test utilities
- `test_scripts/` - CLI output comparison tests against reference data