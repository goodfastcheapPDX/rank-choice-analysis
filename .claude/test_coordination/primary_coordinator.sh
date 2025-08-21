#!/bin/bash
# Primary Instance Coordination Script

COORD_DIR=".claude/test_coordination"
PING_FILE="$COORD_DIR/ping.json"
PONG_FILE="$COORD_DIR/pong.json"
STATUS_FILE="$COORD_DIR/status_primary.json"
LOG_FILE="$COORD_DIR/test_log.txt"
EXIT_FILE="$COORD_DIR/exit_signal.txt"

# Utility functions
log_action() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [PRIMARY] $1" >> "$LOG_FILE"
    echo "[PRIMARY] $1"
}

update_status() {
    local status="$1"
    local phase="$2"
    cat > "$STATUS_FILE" << EOF
{
  "instance": "primary",
  "pid": "$$",
  "status": "$status",
  "last_activity": "$(date -Iseconds)",
  "test_phase": "$phase",
  "messages_sent": $3,
  "messages_received": $4
}
EOF
}

send_ping() {
    local message="$1"
    log_action "SENDING_PING: $message"

    cat > "$PING_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "from": "primary",
  "to": "secondary",
  "message": "$message",
  "sequence": 1,
  "status": "waiting_for_response",
  "test_id": "ping_pong_001"
}
EOF

    update_status "ping_sent" "waiting_for_pong" 1 0
}

wait_for_pong() {
    local max_wait=30
    local wait_count=0

    log_action "WAITING_FOR_PONG: max_wait=${max_wait}s"

    while [[ $wait_count -lt $max_wait ]]; do
        if [[ -f "$PONG_FILE" ]]; then
            local pong_message=$(jq -r '.message' "$PONG_FILE" 2>/dev/null)
            log_action "RECEIVED_PONG: $pong_message"
            update_status "pong_received" "completed" 1 1
            return 0
        fi

        sleep 2
        wait_count=$((wait_count + 2))
        log_action "POLLING: ${wait_count}s elapsed"
    done

    log_action "TIMEOUT: No pong received after ${max_wait}s"
    update_status "timeout" "failed" 1 0
    return 1
}

cleanup() {
    log_action "CLEANUP: Creating exit signal"
    touch "$EXIT_FILE"
    update_status "cleanup" "finished" 1 1
}

# Main execution
main() {
    log_action "INIT: Primary coordinator starting (PID: $$)"
    update_status "starting" "init" 0 0

    # Clean up any previous test files
    rm -f "$PING_FILE" "$PONG_FILE" "$EXIT_FILE"

    # Send ping message
    send_ping "Hello from primary instance! Testing multi-instance coordination."

    # Wait for pong response
    if wait_for_pong; then
        log_action "SUCCESS: Ping-pong communication test completed successfully!"
        cleanup
        exit 0
    else
        log_action "FAILURE: Ping-pong communication test failed"
        cleanup
        exit 1
    fi
}

# Run main function
main "$@"
