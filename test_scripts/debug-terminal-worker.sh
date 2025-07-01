#!/bin/bash
# debug-terminal-worker.sh - Worker script that runs inside the debug terminal

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <pipe_file>" >&2
    exit 1
fi

PIPE_FILE="$1"
WORKER_DIR="$(dirname "$PIPE_FILE")"
CURRENT_CMD_PID_FILE="$WORKER_DIR/current_cmd.pid"
LOG_FILE="$WORKER_DIR/debug.log"

# Logging function
log_message() {
    local level="$1"
    shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S.%3N')] [WORKER-$$] [$level] $*" >> "$LOG_FILE"
}

echo "Debug terminal worker started. Waiting for commands..."
echo "PID: $$"
log_message "INFO" "Worker started with PID $$, pipe: $PIPE_FILE"

while true; do
    if read -r cmd_line < "$PIPE_FILE" 2>/dev/null; then
        if [[ "$cmd_line" == "EXIT" ]]; then
            echo "Worker exiting..."
            log_message "INFO" "Received EXIT command, shutting down"
            break
        fi

        # Parse base64 encoded command and filenames
        encoded_cmd=$(echo "$cmd_line" | awk -F'@@@' '{
            # Find the total number of fields
            nf = NF
            # Command is everything except the last two fields, joined back with @@@
            cmd = $1
            for(i = 2; i <= nf-2; i++) {
                cmd = cmd "@@@" $i
            }
            print cmd
        }')
        typescript_file=$(echo "$cmd_line" | awk -F'@@@' '{print $(NF-1)}')
        screenshot_file=$(echo "$cmd_line" | awk -F'@@@' '{print $NF}')

        # Decode the command from base64
        cmd=$(echo "$encoded_cmd" | base64 -d)

        echo "Executing: $cmd"
        log_message "INFO" "Starting command: $cmd"
        log_message "DEBUG" "Output file: $typescript_file, Screenshot: $screenshot_file"

        # Execute command with script to capture typescript
        script -q -e -c "$cmd" "$typescript_file" < /dev/tty &
        cmd_pid=$!
        echo "$cmd_pid" > "$CURRENT_CMD_PID_FILE"
        log_message "INFO" "Command started with PID $cmd_pid"

        # Wait for the command to complete
        log_message "DEBUG" "Waiting for command PID $cmd_pid to complete"
        wait $cmd_pid 2>/dev/null || true
        cmd_exit_code=$?
        log_message "INFO" "Command completed with exit code $cmd_exit_code"

        # Remove PID file when command completes
        rm -f "$CURRENT_CMD_PID_FILE"
        log_message "DEBUG" "Removed PID file"

        # Add delay between command execution and screenshot capture
        sleep 0.5

        # Take screenshot - try terminal window first, then fallback to root
        ([[ -n "${WINDOWID:-}" ]] && import -window "$WINDOWID" "$screenshot_file" 2>/dev/null) || \
        import -window root "$screenshot_file" 2>/dev/null || \
        scrot "$screenshot_file" 2>/dev/null || {
            echo "Warning: Could not take screenshot (neither import nor scrot available)"
            touch "$screenshot_file"  # Create empty file to signal completion
        }

        # Command completed - files signal completion
    fi
done
