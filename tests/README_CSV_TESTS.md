# CSV Message Storage Tests

## Overview

This directory contains comprehensive tests for CSV message storage functionality. The tests validate the complete storage pipeline from message processing to CSV file creation.

## Main Test File

### `test_csv_message_storage.py`

**Purpose**: Comprehensive test suite for CSV message storage operations

**Test Coverage**:
- Basic CSV functionality with simple message data
- Complex message handling with processing fields
- Data filtering validation (32+ fields → 17 CSV fields)
- Error handling and edge cases
- Real-world data compatibility
- Storage pipeline end-to-end validation
- Performance and reliability testing

**Test Categories**:
1. **Basic Functionality**: Core CSV operations with standard message data
2. **Complex Data**: Messages with AI analysis, teams integration, and processing metadata
3. **Data Filtering**: Verification that extra fields are properly filtered out
4. **Error Handling**: Edge cases like empty messages, missing fields, invalid data
5. **Real-world Data**: Compatibility with actual telegram message structures
6. **Pipeline Testing**: Complete flow from raw message to stored CSV data
7. **Performance**: Large message batches and concurrent operations

## Running the Tests

### Individual Test Execution
```bash
# Run the comprehensive CSV storage test
cd /home/ubuntu/TelegramScraper/telegram-ai-scraper
python tests/test_csv_message_storage.py
```

### Via Test Runner Scripts
```bash
# Run only CSV storage tests
./scripts/run_tests.sh --csv

# Run all tests including CSV storage
./scripts/run_tests.sh

# Quick test run (includes CSV tests)
./scripts/run_tests.sh --quick
```

### Via Python Test Runner
```bash
# CSV tests only
python scripts/run_tests.py --csv

# All tests
python scripts/run_tests.py
```

## Test Results Interpretation

### Success Indicators
- ✅ All 7 test categories pass
- ✅ CSV files created with correct headers
- ✅ Data filtering works (extra fields removed)
- ✅ No field mismatch errors
- ✅ Clean test output with success messages

### Failure Indicators
- ❌ Field mismatch errors ("dict contains fields not in fieldnames")
- ❌ Missing CSV files after test
- ❌ Incorrect data in CSV files
- ❌ Exception traces in test output

## Integration with Main Test Suite

The CSV storage tests are integrated into the main test runner system:

- **Python Runner**: `scripts/run_tests.py` includes `test_csv_storage()` method
- **Bash Wrapper**: `scripts/run_tests.sh` supports `--csv` flag
- **Full Suite**: CSV tests run as part of comprehensive test execution
- **CI/CD Ready**: Tests designed for automated testing environments

## Test Data

The test generates various types of mock message data:

- **Simple Messages**: Basic telegram message structure
- **Complex Messages**: With AI analysis, teams tasks, processing metadata
- **Real-world Format**: Matches actual telegram API response structure
- **Edge Cases**: Empty fields, special characters, large content

## Dependencies

- **Core System**: Tests actual production functions from `src/tasks/telegram_celery_tasks.py`
- **File Handling**: Uses `src/core/file_handling.py` for CSV operations
- **Mock Data**: Self-contained mock data generation
- **Configuration**: Uses project's TELEGRAM_EXCEL_FIELDS configuration

## Historical Context

This consolidated test file replaces multiple individual test files that were created during the storage issue debugging process:

- `test_message_storage.py` (basic functionality)
- `test_csv_direct.py` (direct function testing)
- `debug_csv_detailed.py` (detailed debugging)
- `test_storage_fix.py` (post-fix validation)
- `test_final_validation.py` (comprehensive validation)

The consolidation provides better organization and comprehensive coverage in a single maintainable test suite.

## Storage Issue Resolution

These tests validate the resolution of the "dict contains fields not in fieldnames" error that was causing 100% CSV storage failures. The tests confirm:

1. **Data Filtering**: Extra processing fields are properly filtered out
2. **Field Mapping**: Only expected CSV fields are written
3. **Error Prevention**: No field mismatch errors occur
4. **Compatibility**: Works with both simple and complex message data

For detailed information about the storage issue and its resolution, see `docs/STORAGE_ISSUES_RESOLVED.md`.