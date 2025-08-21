# Instructions for Secondary Claude Instance

## Overview
You are the secondary Claude instance in a multi-instance coordination test. Your role is to respond to messages from the primary instance.

## Your Task
1. Navigate to the project directory: `cd /mnt/c/Users/Joe/Projects/ranked-elections-analyzer`
2. Run the secondary coordinator script: `bash .claude/test_coordination/secondary_coordinator.sh`
3. The script will automatically:
   - Poll for ping messages from the primary instance
   - Respond with a pong message when a ping is detected
   - Log all activities to the shared log file
   - Handle graceful shutdown when signaled

## What to Expect
- The script will start and log "INIT: Secondary coordinator starting"
- It will poll every 2 seconds for a ping message
- Once it receives a ping, it will immediately respond with a pong
- The test should complete within 1-2 minutes
- You can monitor progress in the log file: `tail -f .claude/test_coordination/test_log.txt`

## Manual Backup Instructions
If the automated script fails, you can manually participate in the test:

```bash
# 1. Check for ping file
cat .claude/test_coordination/ping.json

# 2. If ping exists, create pong response
cat > .claude/test_coordination/pong.json << 'EOF'
{
  "timestamp": "$(date -Iseconds)",
  "from": "secondary",
  "to": "primary",
  "message": "Manual pong response from secondary instance",
  "sequence": 2,
  "status": "response_sent",
  "test_id": "ping_pong_001",
  "original_message": "PING_MESSAGE_HERE"
}
EOF

# 3. Update your status
echo "Manual response sent at $(date)" >> .claude/test_coordination/test_log.txt
```

## Success Criteria
- ✅ Script starts successfully and logs initialization
- ✅ Detects ping message from primary instance
- ✅ Sends pong response back to primary instance
- ✅ Both instances log successful completion
- ✅ Test completes without timeouts or errors
