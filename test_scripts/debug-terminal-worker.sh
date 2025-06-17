#!/bin/bash
# debug-terminal-worker.sh - Worker script that runs inside the debug terminal

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <pipe_file>" >&2
    exit 1
fi

PIPE_FILE="$1"

echo "Debug terminal worker started. Waiting for commands..."
echo "PID: $$"

while true; do
    if read -r cmd_line < "$PIPE_FILE"; then
        if [[ "$cmd_line" == "EXIT" ]]; then
            echo "Worker exiting..."
            break
        fi

        # Parse command and filenames using awk, handling cases where command
        # contains `@@@`. We assume only the last two @@@ are real separators
        # (for typescript and screenshot files).
        cmd=$(echo "$cmd_line" | awk -F'@@@' '{
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

        echo "Executing: $cmd"

        # Execute command with script to capture typescript
        script -q -e -c "$cmd" "$typescript_file"
        cmd_exit_code=$?

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
