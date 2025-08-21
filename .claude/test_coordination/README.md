# Multi-Instance Coordination Test

This directory contains test files for coordinating between multiple Claude instances.

## Test Protocol

1. **Primary Instance** (this instance):
   - Writes ping.json with initial message
   - Polls for pong.json response
   - Logs all actions to test_log.txt

2. **Secondary Instance** (launched via tmux):
   - Polls for ping.json
   - Responds with pong.json when detected
   - Logs actions to test_log.txt

## File Structure

- `ping.json` - Message from primary to secondary
- `pong.json` - Response from secondary to primary
- `status_primary.json` - Primary instance status
- `status_secondary.json` - Secondary instance status
- `test_log.txt` - Shared activity log
- `exit_signal.txt` - Signal for graceful shutdown
