#!/bin/bash
# Secondary Instance Coordination Script

COORD_DIR=".claude/test_coordination"
PING_FILE="$COORD_DIR/ping.json"
PONG_FILE="$COORD_DIR/pong.json"
STATUS_FILE="$COORD_DIR/status_secondary.json"
LOG_FILE="$COORD_DIR/test_log.txt"
EXIT_FILE="$COORD_DIR/exit_signal.txt"

# Utility functions
log_action() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SECONDARY] $1" >> "$LOG_FILE"
    echo "[SECONDARY] $1"
}

update_status() {
    local status="$1"
    local phase="$2"
    cat > "$STATUS_FILE" << EOF
{
  "instance": "secondary",
  "pid": "$$",
  "status": "$status",
  "last_activity": "$(date -Iseconds)",
  "test_phase": "$phase",
  "messages_sent": $3,
  "messages_received": $4
}
EOF
}

wait_for_ping() {
    local max_wait=60
    local wait_count=0

    log_action "WAITING_FOR_PING: max_wait=${max_wait}s"

    while [[ $wait_count -lt $max_wait ]]; do
        # Check for exit signal
        if [[ -f "$EXIT_FILE" ]]; then
            log_action "EXIT_SIGNAL: Received exit signal, shutting down"
            return 2
        fi

        # Check for ping file
        if [[ -f "$PING_FILE" ]]; then
            local ping_message=$(jq -r '.message' "$PING_FILE" 2>/dev/null)
            if [[ $? -eq 0 && "$ping_message" != "null" ]]; then
                log_action "RECEIVED_PING: $ping_message"
                update_status "ping_received" "processing" 0 1
                echo "$ping_message"  # Return the message
                return 0
            fi
        fi

        sleep 2
        wait_count=$((wait_count + 2))

        # Log every 10 seconds to avoid spam
        if [[ $((wait_count % 10)) -eq 0 ]]; then
            log_action "POLLING: ${wait_count}s elapsed, still waiting for ping"
        fi
    done

    log_action "TIMEOUT: No ping received after ${max_wait}s"
    update_status "timeout" "failed" 0 0
    return 1
}

send_pong() {
    local original_message="$1"
    local pong_message="Hello back from secondary instance! Received: $original_message"

    log_action "SENDING_PONG: $pong_message"

    cat > "$PONG_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "from": "secondary",
  "to": "primary",
  "message": "$pong_message",
  "sequence": 2,
  "status": "response_sent",
  "test_id": "ping_pong_001",
  "original_message": "$original_message"
}
EOF

    update_status "pong_sent" "completed" 1 1
}

# Main execution
main() {
    log_action "INIT: Secondary coordinator starting (PID: $$)"
    update_status "starting" "init" 0 0

    # Wait for ping message
    ping_message=$(wait_for_ping)
    exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        # Send pong response
        send_pong "$ping_message"
        log_action "SUCCESS: Ping-pong communication completed successfully!"
        update_status "completed" "finished" 1 1
        exit 0
    elif [[ $exit_code -eq 2 ]]; then
        # Graceful shutdown
        log_action "SHUTDOWN: Graceful shutdown via exit signal"
        update_status "shutdown" "finished" 0 1
        exit 0
    else
        # Timeout or error
        log_action "FAILURE: Ping-pong communication failed"
        update_status "failed" "error" 0 0
        exit 1
    fi
}

# Run main function
main "$@"
