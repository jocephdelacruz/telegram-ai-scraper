# Session Invalidation Prevention Guide

## 🚨 Problem Overview

The Telegram session invalidation issue you've been experiencing is caused by **concurrent access** to the same session file by multiple processes. When this happens, Telegram's servers detect unusual activity and invalidate the session, disconnecting your phone's Telegram app.

## 🔍 Root Causes Identified

### 1. **Worker Restart Session Conflicts**
- **Issue**: When you run `deploy_celery.sh stop`, workers are killed before they can properly close Telegram connections
- **Impact**: Session gets corrupted, causing invalidation
- **Solution**: Extended graceful shutdown timeout (5s → 15s) to allow proper Telegram disconnect

### 2. **Test Scripts Running While Workers Active**
- **Issue**: Running `debug_recent_messages.py` or other test scripts while Celery workers are active
- **Impact**: Multiple processes accessing same session file simultaneously
- **Solution**: Session safety checks prevent tests from running when workers are active

### 3. **Concurrent Session File Access**
- **Issue**: No file locking mechanism prevented multiple processes from accessing `telegram_session.session`
- **Impact**: Session corruption and invalidation
- **Solution**: File-level locking with timeout and retry mechanisms

### 4. **Improper Session Cleanup**
- **Issue**: Clients not properly disconnecting before process termination
- **Impact**: Telegram servers detect abrupt disconnections as suspicious
- **Solution**: Enhanced cleanup with proper async disconnect and delays

## 🔧 Fixes Implemented

### 1. **Session File Locking** ✅
- Added `fcntl` file locking to prevent concurrent session access
- 30-second timeout with warning messages
- Automatic lock cleanup on process exit

### 2. **Session Safety Manager** ✅
- New module: `src/integrations/session_safety.py`
- Detects running Celery workers before allowing session access
- Prevents tests/debug scripts from causing conflicts

### 3. **Enhanced Graceful Shutdown** ✅
- Extended shutdown timeout from 5s to 15s
- Progress messages during shutdown
- Better error handling for stuck processes

### 4. **Improved Session Cleanup** ✅
- Longer disconnect timeout (10s instead of default)
- Proper async cleanup with sleep delays
- Lock release after every operation

### 5. **Protected Test Scripts** ✅
- All test scripts now check for session safety
- Clear error messages when conflicts detected
- Guidance on how to safely run tests

## 📋 New Safety Features

### Session Safety Checker
```bash
# Check if it's safe to perform Telegram operations
python3 scripts/check_session_safety.py
```

### Protected Authentication
```bash
# Authentication now includes safety checks
python3 scripts/telegram_auth.py
```

### Safe Test Execution
```bash
# Tests now automatically check for conflicts
python3 tests/debug_recent_messages.py
```

## 🛡️ Prevention Guidelines

### **Before Running Tests or Debug Scripts:**
1. Check session safety: `python3 scripts/check_session_safety.py`
2. If workers are running, either:
   - Wait for them to finish current tasks (~4 minutes)
   - Or stop workers: `./scripts/deploy_celery.sh stop`
3. Run your test/debug script
4. Restart workers: `./scripts/deploy_celery.sh start`

### **Safe Worker Management:**
```bash
# Always use graceful shutdown (never kill -9)
./scripts/deploy_celery.sh stop

# Wait for confirmation that all processes stopped
./scripts/status.sh

# Then restart
./scripts/deploy_celery.sh start
```

### **Re-authentication Process:**
```bash
# Stop workers first
./scripts/deploy_celery.sh stop

# Authenticate safely
python3 scripts/telegram_auth.py

# Restart workers
./scripts/deploy_celery.sh start
```

## 🔧 Emergency Recovery

If you experience session invalidation:

1. **Stop all workers immediately:**
   ```bash
   ./scripts/deploy_celery.sh stop --force
   ```

2. **Check for session conflicts:**
   ```bash
   python3 scripts/check_session_safety.py
   ```

3. **Remove corrupted session:**
   ```bash
   rm -f telegram_session.session*
   rm -f telegram_session.lock*
   ```

4. **Re-authenticate:**
   ```bash
   python3 scripts/telegram_auth.py
   ```

5. **Restart system:**
   ```bash
   ./scripts/deploy_celery.sh start
   ```

## 📊 Monitoring Session Health

### Check Session Status
```bash
# Comprehensive session status
python3 scripts/telegram_session_check.py --quick

# Worker status
./scripts/status.sh

# Session safety
python3 scripts/check_session_safety.py
```

### Log Monitoring
```bash
# Watch for session issues
tail -f logs/telegram.log | grep -E "(SESSION|session|Session)"

# Monitor worker activity
tail -f logs/celery_main_processor.log
```

## 🎯 Best Practices

1. **Never run test scripts while workers are active**
2. **Always use graceful shutdown** (`deploy_celery.sh stop`, not `kill -9`)
3. **Check session safety before authentication**
4. **Monitor logs for session warnings**
5. **Use the provided safety tools**

## 🔍 Technical Details

### File Locking Implementation
- Uses `fcntl.LOCK_EX` for exclusive access
- 30-second timeout with 1-second intervals
- Automatic cleanup in `__exit__` methods

### Worker Detection
- Scans for `celery.*telegram_celery_tasks` processes
- Checks PIDs and process status
- Provides specific worker information

### Enhanced Disconnect
- 10-second timeout for `client.disconnect()`
- Asyncio sleep delays for proper cleanup
- Multiple retry attempts with exponential backoff

## 🎉 Expected Results

With these fixes:
- ✅ **No more session invalidation** from worker restarts
- ✅ **No more phone disconnections** from concurrent access  
- ✅ **Clear warnings** when operations are unsafe
- ✅ **Proper session management** across all processes
- ✅ **Graceful error recovery** with helpful guidance

The session should now remain stable for days/weeks instead of becoming invalid after each restart.