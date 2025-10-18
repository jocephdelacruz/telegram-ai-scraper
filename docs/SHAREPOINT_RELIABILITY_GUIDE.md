# SharePoint Integration Reliability Guide

This guide covers the enhanced SharePoint reliability features implemented in the Telegram AI Scraper, including best practices for monitoring, troubleshooting, and maintaining optimal SharePoint integration performance.

## Table of Contents
- [Overview](#overview)
- [Enhanced Features](#enhanced-features)
- [Configuration](#configuration)
- [Monitoring and Health Checks](#monitoring-and-health-checks)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)
- [Recovery Procedures](#recovery-procedures)

## Overview

The SharePoint integration has been significantly enhanced with enterprise-grade reliability features to prevent service crashes and ensure consistent data storage. The improvements focus on:

- **Session Management**: Robust session validation and multi-attempt initialization
- **Error Handling**: Comprehensive error classification and recovery procedures
- **Fault Tolerance**: Exponential backoff retry logic and graceful degradation
- **Monitoring**: Detailed logging and health checks for proactive issue detection

## Enhanced Features

### Session Management Improvements

#### Multi-Attempt Session Initialization
```python
# Enhanced session creation with up to 3 attempts
def createExcelSession(self):
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            # Create session with timeout handling
            session = self._create_session_with_timeout()
            # Validate session health
            if self.validateSession(session):
                return session
        except Exception as e:
            self.logger.warning(f"Session creation attempt {attempt} failed: {e}")
            if attempt < max_attempts:
                time.sleep(attempt * 2)  # Exponential backoff
    raise SharePointInitializationError("Failed to establish SharePoint session after 3 attempts")
```

#### Session Validation
```python
def validateSession(self, session):
    """Validate SharePoint session health"""
    try:
        # Test basic connectivity with timeout
        response = session.get(
            f"{self.base_url}/sites/{self.site_id}",
            timeout=30
        )
        return response.status_code == 200
    except Exception:
        return False
```

### Enhanced Retry Logic

#### Celery Task Retry Configuration
```python
@celery.task(
    bind=True, 
    max_retries=5,          # Up to 5 retry attempts
    default_retry_delay=180, # 3-minute base delay
    retry_backoff=True,     # Exponential backoff
    retry_jitter=False      # Consistent timing
)
def save_to_sharepoint(self, message_data):
    try:
        # Enhanced SharePoint processing with session validation
        processor = SharePointProcessor()
        result = processor.process_message(message_data)
        return result
    except SharePointInitializationError as e:
        # Retry for session initialization failures
        raise self.retry(countdown=180 * (self.request.retries + 1))
    except Exception as e:
        # Log error and send admin notification
        logger.error(f"SharePoint task failed: {e}")
        send_critical_exception("SharePointTaskError", str(e), "save_to_sharepoint")
        raise
```

### Timeout and Error Handling

#### Request Timeout Configuration
- **Session Creation**: 45 seconds
- **Authentication**: 30 seconds  
- **Excel Operations**: 30 seconds
- **Connection Validation**: 15 seconds

#### Error Classification
1. **Authentication Errors**: Token refresh and retry
2. **Network Timeouts**: Exponential backoff retry
3. **Service Unavailable**: Graceful degradation with notifications
4. **Session Corruption**: Session recreation and retry

## Configuration

### SharePoint Processor Settings

Add the following to your SharePoint configuration for optimal reliability:

```json
{
  "MS_SHAREPOINT_ACCESS": {
    "CLIENT_ID": "your-client-id",
    "CLIENT_SECRET": "your-client-secret", 
    "TENANT_ID": "your-tenant-id",
    "SITE_URL": "https://yoursite.sharepoint.com/sites/yoursite",
    "WORKBOOK_PATH": "/path/to/workbook.xlsx",
    "reliability_settings": {
      "max_session_attempts": 3,
      "session_timeout": 45,
      "operation_timeout": 30,
      "validation_timeout": 15,
      "retry_delay_base": 180,
      "max_retries": 5
    }
  }
}
```

### Celery Task Configuration

```json
{
  "CELERY_CONFIG": {
    "task_routes": {
      "src.tasks.telegram_celery_tasks.save_to_sharepoint": {
        "queue": "sharepoint",
        "priority": 8
      }
    },
    "task_time_limit": 600,
    "task_soft_time_limit": 540
  }
}
```

## Monitoring and Health Checks

### Log Files to Monitor

1. **SharePoint Operations**: `logs/sharepoint.log`
   ```bash
   # Monitor successful operations
   tail -f logs/sharepoint.log | grep "status=200"
   
   # Watch for session issues
   tail -f logs/sharepoint.log | grep -i "session\|error\|failed"
   ```

2. **Teams Notifications**: `logs/teams.log`
   ```bash
   # Check for SharePoint crash alerts
   grep "SharePointInitializationError" logs/teams.log
   ```

3. **Celery Data Services**: `logs/celery_data_services.log`
   ```bash
   # Monitor task success/failure
   tail -f logs/celery_data_services.log | grep -E "succeeded|failed"
   ```

### Health Check Commands

```bash
# Quick SharePoint health check
./scripts/sharepoint_health_check.sh

# Test SharePoint connectivity
./scripts/run_tests.sh --sharepoint

# Monitor real-time SharePoint operations
tail -f logs/sharepoint.log logs/celery_data_services.log
```

### Key Performance Indicators

- **Success Rate**: > 95% of SharePoint operations should succeed
- **Response Time**: Excel operations should complete within 30 seconds
- **Session Validity**: Sessions should last > 1 hour without recreation
- **Error Recovery**: Failed operations should recover within 3 attempts

## Troubleshooting

### Common Issues and Solutions

#### 1. SharePointInitializationError
**Symptoms**: Teams alerts showing session initialization failures
**Log Pattern**: `Failed to establish SharePoint session after 3 attempts`

```bash
# Check authentication status
grep "authentication" logs/sharepoint.log | tail -5

# Verify credentials
python3 -c "
import json
with open('config/config.json') as f:
    config = json.load(f)
print('SharePoint config loaded successfully')
"

# Test connection manually
./scripts/run_tests.sh --sharepoint
```

**Recovery**:
1. Verify SharePoint credentials in config.json
2. Check network connectivity to graph.microsoft.com
3. Restart data services worker: `./scripts/deploy_celery.sh restart data_services`

#### 2. Timeout Errors
**Symptoms**: Operations hanging or timing out
**Log Pattern**: `TimeoutError` or `ReadTimeout`

```bash
# Check network latency
ping graph.microsoft.com

# Monitor timeout patterns
grep -i "timeout" logs/sharepoint.log | tail -10
```

**Recovery**:
1. Increase timeout values in SharePoint processor
2. Check network stability
3. Consider reducing concurrency: `./scripts/deploy_celery.sh 1`

#### 3. Authentication Token Expiration
**Symptoms**: HTTP 401 errors in SharePoint operations
**Log Pattern**: `Authentication failed` or `401 Unauthorized`

```bash
# Check token refresh patterns
grep "getAccessToken" logs/sharepoint.log | tail -10

# Look for 401 responses
grep "status=401" logs/sharepoint.log
```

**Recovery**:
1. System automatically refreshes tokens
2. If persistent, verify client credentials
3. Check tenant permissions for the application

### Diagnostic Commands

```bash
# Comprehensive SharePoint diagnostics
./scripts/sharepoint_diagnostics.sh

# Check recent errors with context
grep -B2 -A2 -i "error\|failed" logs/sharepoint.log | tail -20

# Monitor success rate
echo "Recent SharePoint operations:"
echo "Successful: $(grep 'status=200' logs/sharepoint.log | wc -l)"
echo "Failed: $(grep -v 'status=200' logs/sharepoint.log | grep 'status=' | wc -l)"
```

## Best Practices

### Development and Testing

1. **Always Use Test Environment**: Use dedicated test SharePoint sheets
2. **Production Safety**: Run `./scripts/run_tests.sh --sharepoint` before deployment
3. **Session Safety**: Never manually access SharePoint while workers are running
4. **Error Monitoring**: Set up alerts for SharePointInitializationError in Teams

### Operations and Maintenance

1. **Regular Health Checks**: Monitor SharePoint logs daily
2. **Proactive Monitoring**: Set up automated health check scripts
3. **Capacity Planning**: Monitor Excel file sizes and performance
4. **Backup Strategy**: Ensure CSV backups are functioning

### Performance Optimization

1. **Worker Tuning**: Use 2-3 SharePoint workers for optimal performance
2. **Timeout Adjustment**: Adjust timeouts based on network conditions
3. **Session Reuse**: Let the system manage session lifecycle automatically
4. **Rate Limiting**: Respect Microsoft Graph API rate limits

## Recovery Procedures

### Emergency SharePoint Service Recovery

```bash
# 1. Stop all services
./scripts/deploy_celery.sh stop

# 2. Check system health
./scripts/status.sh

# 3. Clear any stuck tasks (if needed)
redis-cli FLUSHDB

# 4. Start services with monitoring
./scripts/deploy_celery.sh start

# 5. Verify SharePoint is working
tail -f logs/sharepoint.log
```

### Data Consistency Verification

```bash
# Check CSV backups are current
ls -la data/backups/iraq_*.csv

# Verify Excel file accessibility
./scripts/run_tests.sh --sharepoint

# Compare record counts
echo "CSV records: $(wc -l data/backups/iraq_significant.csv)"
echo "Recent SharePoint ops: $(grep 'status=200' logs/sharepoint.log | tail -10 | wc -l)"
```

### Session Recovery After Authentication Issues

```bash
# 1. Clear session state (if persistent auth issues)
rm -f sharepoint_session_cache.*

# 2. Test credentials
./scripts/run_tests.sh --config

# 3. Restart with fresh session
./scripts/deploy_celery.sh restart data_services

# 4. Monitor recovery
tail -f logs/sharepoint.log logs/teams.log
```

## Maintenance Schedule

### Daily Tasks
- Monitor SharePoint operation logs
- Check Teams notifications for errors
- Verify data consistency between CSV and Excel

### Weekly Tasks  
- Run comprehensive SharePoint tests
- Review performance metrics
- Update Excel file permissions if needed

### Monthly Tasks
- Review and rotate authentication credentials
- Analyze error patterns and optimize configurations
- Performance tuning based on usage patterns

## Support and Escalation

For SharePoint-related issues:

1. **Check Logs**: Start with `logs/sharepoint.log` and `logs/teams.log`
2. **Run Diagnostics**: Use `./scripts/run_tests.sh --sharepoint`
3. **Test Connectivity**: Verify network and authentication
4. **Review Configuration**: Ensure credentials and permissions are correct
5. **Escalate**: If issues persist, collect logs and configuration for analysis

## Conclusion

The enhanced SharePoint reliability features provide enterprise-grade stability and error handling. By following this guide's monitoring and maintenance procedures, you can ensure optimal SharePoint integration performance and quick recovery from any issues.

For additional support or feature requests, refer to the main project documentation and troubleshooting guides.