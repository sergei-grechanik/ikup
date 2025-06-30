#!/bin/bash

# debug-terminal.sh - Persistent terminal environment for debugging tupimage
#
# Usage:
#   debug-terminal.sh start [terminal_cmd [args...]]
#   debug-terminal.sh exec command [args...]
#   debug-terminal.sh stop
#
# Examples:
#   debug-terminal.sh start                              # Use default st
#   debug-terminal.sh start st -f "Liberation Mono" -e   # Custom st options
#   debug-terminal.sh start kitty                        # Use kitty instead
#   debug-terminal.sh exec uv run tupimage display image.png
#   debug-terminal.sh stop

set -euo pipefail

# File locations (use current working directory)
DEBUG_DIR="debug-terminal"
XVFB_PID_FILE="$DEBUG_DIR/xvfb.pid"
TERM_PID_FILE="$DEBUG_DIR/term.pid"
PIPE_FILE="$DEBUG_DIR/pipe"
DISPLAY_FILE="$DEBUG_DIR/display"

# Default terminal command
DEFAULT_TERMINAL_CMD="st -e"

usage() {
    echo "Usage: $0 {start|exec|stop}"
    echo ""
    echo "Commands:"
    echo "  start [terminal_cmd [args...]]    Start Xvfb and terminal (default: st -e)"
    echo "  exec command [args...]            Execute command in terminal"
    echo "  stop                              Stop Xvfb and terminal"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 start st -f 'Liberation Mono' -e"
    echo "  $0 start kitty"
    echo "  $0 exec uv run tupimage display image.png"
    echo "  $0 stop"
    exit 1
}

cleanup() {
    echo "Cleaning up due to signal..."
    stop_processes
}

# Set up signal handlers
trap cleanup INT TERM

# Succeeds if the process is running, otherwise removes the PID file and returns
# failure.
is_process_running() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1
}

stop_processes() {
    if is_process_running "$TERM_PID_FILE"; then
        echo "Stopping terminal..."
        local term_pid=$(cat "$TERM_PID_FILE")
        kill "$term_pid" 2>/dev/null || true
        sleep 1
        kill -9 "$term_pid" 2>/dev/null || true
        rm -f "$TERM_PID_FILE"
    fi

    if is_process_running "$XVFB_PID_FILE"; then
        echo "Stopping Xvfb..."
        local xvfb_pid=$(cat "$XVFB_PID_FILE")
        kill "$xvfb_pid" 2>/dev/null || true
        sleep 1
        kill -9 "$xvfb_pid" 2>/dev/null || true
        rm -f "$XVFB_PID_FILE"
    fi

    # Clean up files
    rm -f "$PIPE_FILE" "$DISPLAY_FILE"
}

start_terminal() {
    # Parse terminal command from arguments
    local terminal_cmd=()
    if [[ $# -eq 0 ]]; then
        # Default terminal
        terminal_cmd=($DEFAULT_TERMINAL_CMD)
    else
        # Custom terminal command - use all arguments
        terminal_cmd=("$@")
    fi

    # Check if already running
    if is_process_running "$XVFB_PID_FILE" && is_process_running "$TERM_PID_FILE"; then
        echo "Debug terminal is already running, restarting..."
    fi

    # Stop any existing processes
    stop_processes

    # Create debug directory
    mkdir -p "$DEBUG_DIR"

    echo "Starting Xvfb..."
    # Use automatic display allocation
    XVFB_OUTPUT=$(mktemp)
    nohup Xvfb -displayfd 1 -screen 0 1024x768x24 > "$XVFB_OUTPUT" 2>/dev/null < /dev/null &
    XVFB_PID=$!
    disown
    echo $XVFB_PID > "$XVFB_PID_FILE"

    # Wait for Xvfb to write the display number
    sleep 2
    if [[ -s "$XVFB_OUTPUT" ]]; then
        DISPLAY_NUM=":$(cat "$XVFB_OUTPUT")"
        echo "$DISPLAY_NUM" > "$DISPLAY_FILE"
        echo "Started Xvfb on display $DISPLAY_NUM"
    else
        echo "Error: Failed to get display number from Xvfb" >&2
        stop_processes
        rm -f "$XVFB_OUTPUT"
        exit 1
    fi
    rm -f "$XVFB_OUTPUT"

    # Create named pipe for communication
    mkfifo "$PIPE_FILE"

    # Use separate worker script file
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local worker_script="$script_dir/debug-terminal-worker.sh"

    if [[ ! -f "$worker_script" ]]; then
        echo "Error: Worker script not found: $worker_script" >&2
        stop_processes
        exit 1
    fi

    echo "Starting terminal: ${terminal_cmd[*]} $worker_script $PIPE_FILE"

    # Start terminal with worker script
    nohup env DISPLAY="$DISPLAY_NUM" "${terminal_cmd[@]}" "$worker_script" "$PIPE_FILE" >/dev/null 2>&1 < /dev/null &
    echo $! > "$TERM_PID_FILE"
    disown

    # Wait a moment for terminal to start
    sleep 2

    # Verify everything is running
    if is_process_running "$XVFB_PID_FILE" && is_process_running "$TERM_PID_FILE"; then
        echo "Debug terminal started successfully!"
        echo "Xvfb PID: $(cat "$XVFB_PID_FILE")"
        echo "Terminal PID: $(cat "$TERM_PID_FILE")"
        echo "Use '$0 exec <command>' to execute commands"
        echo "Use '$0 stop' to shutdown"
    else
        echo "Failed to start debug terminal" >&2
        stop_processes
        exit 1
    fi
}

exec_command() {
    if [[ $# -eq 0 ]]; then
        echo "Error: No command specified" >&2
        exit 1
    fi

    # Check if terminal is running
    if ! is_process_running "$XVFB_PID_FILE" || ! is_process_running "$TERM_PID_FILE"; then
        echo "Error: Debug terminal is not running. Use '$0 start' first." >&2
        exit 1
    fi

    if [[ ! -p "$PIPE_FILE" ]]; then
        echo "Error: Command pipe not found: $PIPE_FILE" >&2
        exit 1
    fi

    # Generate filenames with milliseconds to avoid collisions
    local timestamp=$(date +%Y%m%d-%H%M%S-%3N)
    local typescript_file="${DEBUG_DIR}/cmd-${timestamp}.out"
    local screenshot_file="${DEBUG_DIR}/cmd-${timestamp}.png"

    # Join all arguments into a single command string
    local cmd_string="$*"

    echo "Executing command: $cmd_string"

    # Send command with filenames to worker via pipe
    # Always use base64 encoding to handle both single-line and multiline commands
    local encoded_cmd=$(echo -n "$cmd_string" | base64 -w 0)
    echo "$encoded_cmd@@@$typescript_file@@@$screenshot_file" > "$PIPE_FILE"

    # Wait for command to complete by checking if files exist
    for i in $(seq 30); do
        if [[ -f "$typescript_file" && -f "$screenshot_file" ]]; then
            break
        fi
        sleep 0.5
    done

    # Show results
    echo ""
    echo "=== Command completed ==="
    echo "=== Output file: $typescript_file ==="
    if [[ -f "$typescript_file" ]]; then
        # Show file content with some ASCII control characters escaped.
        sed 's/\r/^M/g; s/\x1b/^[/g; s/\x08/^H/g; s/\x07/^G/g' "$typescript_file"
    else
        echo "(output file not found)"
    fi
    echo "=== Screenshot: $screenshot_file ==="
    if [[ -f "$screenshot_file" ]]; then
        echo "Screenshot saved successfully"
    else
        echo "(screenshot failed)"
    fi
    echo "=== End of output ==="
}

stop_terminal() {
    echo "Stopping debug terminal..."

    # Send EXIT command to worker if pipe exists
    if [[ -p "$PIPE_FILE" ]]; then
        echo "EXIT" > "$PIPE_FILE" 2>/dev/null || true
        sleep 1
    fi

    stop_processes
    echo "Debug terminal stopped."
}

# Main command handling
case "${1:-}" in
    start)
        shift
        start_terminal "$@"
        ;;
    exec)
        shift
        exec_command "$@"
        ;;
    stop)
        stop_terminal
        ;;
    *)
        usage
        ;;
esac
