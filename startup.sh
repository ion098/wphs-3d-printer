#!/bin/bash

PID=0

cd "~/Desktop/wphs-3d-printer"

TERMINAL="lxterminal --title=3D-Printer -e"

cleanup() {
    if [ "$PID" -ne 0 ]; then
        echo "$(date): Shutting down terminal..."
        kill "$PID" 2>/dev/null
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM

while true; do
    # 1. Start uv inside a new GUI terminal window if not running
    if [ "$PID" -eq 0 ] || ! kill -0 "$PID" 2>/dev/null; then
        echo "$(date): Launching app in GUI terminal..."
        $TERMINAL uv run python3 main.py &
        PID=$!
    fi

    # 2. Wait until the next check for 3 minutes (180 s)
    sleep "180"

    # 3. Poll Git for updates
    echo "$(date): Checking for updates..."
    git fetch origin prod > /dev/null 2>&1

    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse @{u})

    # 4. Seamless Update: Pull -> Sync Deps -> Kill Old -> Boot New
    if [ "$LOCAL" != "$REMOTE" ]; then
        echo "$(date): New update found."
        
        # Pull code safely while old app keeps running
        git pull --ff-only origin prod
        
        echo "$(date): Code downloaded. Updating dependencies..."
        # Force uv to sync the environment in the background right now
        uv sync > /dev/null 2>&1
        
        echo "$(date): Dependencies updated. Restarting code..."

        # Kill the old GUI terminal process
        kill "$PID" 2>/dev/null
        wait "$PID" 2>/dev/null
        PID=0
        
        # The loop instantly moves to step 1 to launch the new version
    fi
done
