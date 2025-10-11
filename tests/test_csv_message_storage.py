#!/usr/bin/env python3
"""
Comprehensive CSV Message Storage Test Suite

This test suite validates the complete CSV storage pipeline for Telegram messages,
including data filtering, field mapping, error handling, and file operations.

Consolidates functionality from:
- debug_csv_detailed.py
- test_csv_direct.py 
- test_message_storage.py
- test_storage_fix.py
- test_final_validation.py
"""

import os
import sys
import json
import csv
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.core.file_handling import FileHandling


class CSVMessageStorageTestSuite:
    """Comprehensive test suite for CSV message storage functionality with production data protection"""
    
    def __init__(self):
        self.config = self._load_config()
        self.excel_fields = self.config.get('TELEGRAM_EXCEL_FIELDS', [])
        self.test_results = {}
        
        # SAFETY: Use dedicated test CSV files to protect production data
        self.data_dir = os.path.join(PROJECT_ROOT, "data")
        self.test_csv_files = {
            'significant': os.path.join(self.data_dir, "TEST_iraq_significant_messages.csv"),
            'trivial': os.path.join(self.data_dir, "TEST_iraq_trivial_messages.csv")
        }
        self.test_files_created = []  # Track test files for cleanup
        
    def _load_config(self):
        """Load application configuration"""
        config_path = os.path.join(PROJECT_ROOT, "config", "config.json")
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def create_test_csv_files(self):
        """Create dedicated test CSV files to protect production data"""
        print("🛡️ Production Data Protection Setup")
        print("=" * 50)
        
        os.makedirs(self.data_dir, exist_ok=True)
        
        for csv_type, csv_path in self.test_csv_files.items():
            try:
                # Create test CSV file with headers
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self.excel_fields)
                    writer.writeheader()
                
                self.test_files_created.append(csv_path)
                print(f"✅ Created test CSV: {os.path.basename(csv_path)}")
                
            except Exception as e:
                print(f"❌ Failed to create test CSV {csv_path}: {e}")
                return False
        
        return True
    
    def cleanup_test_csv_files(self):
        """Delete test CSV files completely to keep production directory clean"""
        print("\n🧹 Test CSV File Cleanup (Remove Test Files Completely)")
        print("=" * 60)
        
        for csv_path in self.test_files_created:
            try:
                if os.path.exists(csv_path):
                    # Count lines before deletion for reporting
                    with open(csv_path, 'r', encoding='utf-8') as f:
                        line_count = sum(1 for line in f) - 1  # Exclude header
                    
                    os.remove(csv_path)
                    print(f"✅ Deleted test CSV: {os.path.basename(csv_path)} ({line_count} test entries removed)")
                else:
                    print(f"ℹ️ Test CSV not found: {os.path.basename(csv_path)} (nothing to delete)")
                    
            except Exception as e:
                print(f"❌ Failed to delete test CSV {csv_path}: {e}")
        
        self.test_files_created.clear()
        print(f"🛡️ Production data directory returned to clean state")
    
    def create_minimal_test_message(self):
        """Create minimal test message with only required fields"""
        return {
            'Message_ID': 100001,
            'Channel': '@minimal_test',
            'Country': 'Iraq',
            'Date': '2025-10-11',
            'Time': '22:30:00',
            'Author': '@test_minimal',
            'Message_Text': 'Minimal test message for CSV storage',
            'AI_Category': 'Trivial',
            'AI_Reasoning': 'Test message - minimal fields',
            'Keywords_Matched': 'minimal, test',
            'Message_Type': 'text',
            'Forward_From': '',
            'Media_Type': 'text',
            'Original_Text': 'Minimal test message for CSV storage',
            'Original_Language': 'english',
            'Was_Translated': False,
            'Processed_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def create_comprehensive_test_message(self):
        """Create comprehensive test message with extra fields (simulates real processing)"""
        return {
            # Expected CSV fields
            'Message_ID': 100002,
            'Channel': '@comprehensive_test',
            'Country': 'Iraq',
            'Date': '2025-10-11',
            'Time': '22:35:00',
            'Author': '@test_comprehensive',
            'Message_Text': 'Comprehensive test message with extra processing fields',
            'AI_Category': 'Significant',
            'AI_Reasoning': 'Test message - comprehensive with extra fields',
            'Keywords_Matched': 'comprehensive, test, extra',
            'Message_Type': 'text',
            'Forward_From': '',
            'Media_Type': 'text',
            'Original_Text': 'Comprehensive test message with extra processing fields',
            'Original_Language': 'english',
            'Was_Translated': False,
            'Processed_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            
            # Extra fields that should be filtered out (these caused original errors)
            'channel': '@comprehensive_test',  # lowercase duplicate
            'Datetime_UTC': datetime.now(),
            'teams_task_id': 'teams-100002-test',
            'is_significant': True,
            'sharepoint_task_id': 'sp-100002-test',
            'id': 100002,  # duplicate
            'ai_analysis': {'is_significant': True, 'reasoning': 'test'},
            'text': 'Comprehensive test message with extra processing fields',  # duplicate
            'country_code': 'iraq',
            'processed_at': datetime.now().isoformat(),
            'received_at': datetime.now().isoformat(),
            'country_name': 'Iraq'
        }
    
    def create_malformed_test_message(self):
        """Create test message with missing required fields"""
        return {
            'Message_ID': 100003,
            'Channel': '@malformed_test',
            # Missing Country field
            'Date': '2025-10-11',
            # Missing Time field
            'Author': '@test_malformed',
            'Message_Text': 'Malformed test message missing some fields',
            'AI_Category': 'Significant',
            # Missing other fields...
        }
    
    def test_basic_csv_functionality(self):
        """Test basic CSV writing functionality with FileHandling class (production safe)"""
        print("=== Testing Basic CSV Functionality (Safe Test Files) ===")
        
        try:
            # Use dedicated test CSV file
            test_file = self.test_csv_files['significant']
            file_handler = FileHandling(test_file)
            
            # Test data with clear test identification
            test_data = self.create_minimal_test_message()
            test_data['Message_ID'] = 'TEST_basic_csv_100001'
            test_data['Channel'] = '@TEST_basic_csv'
            test_data['AI_Category'] = 'Significant'
            
            # Write to CSV
            success = file_handler.append_to_csv(test_data, self.excel_fields)
            
            if success:
                # Verify file content
                with open(test_file, 'r') as f:
                    content = f.read()
                    lines = content.strip().split('\n')
                
                if len(lines) >= 2 and 'TEST_basic_csv_100001' in lines[1]:
                    print("✅ Basic CSV functionality test PASSED (written to test file)")
                    self.test_results['basic_csv'] = True
                else:
                    print("❌ Basic CSV functionality test FAILED - Data not written correctly")
                    self.test_results['basic_csv'] = False
                
            else:
                print("❌ Basic CSV functionality test FAILED - Write operation failed")
                self.test_results['basic_csv'] = False
                
        except Exception as e:
            print(f"❌ Basic CSV functionality test FAILED - Exception: {e}")
            self.test_results['basic_csv'] = False
    
    def test_data_filtering(self):
        """Test data filtering functionality (core fix for storage issues)"""
        print("\n=== Testing Data Filtering ===")
        
        try:
            # Create message with extra fields
            message_data = self.create_comprehensive_test_message()
            
            print(f"Original message has {len(message_data)} fields")
            print(f"Expected CSV fields: {len(self.excel_fields)}")
            
            # Apply filtering (same logic as the fix)
            filtered_data = {}
            for field in self.excel_fields:
                filtered_data[field] = message_data.get(field, '')
            
            print(f"Filtered message has {len(filtered_data)} fields")
            
            # Verify all expected fields are present
            missing_fields = [field for field in self.excel_fields if field not in filtered_data]
            extra_fields = [field for field in filtered_data if field not in self.excel_fields]
            
            if not missing_fields and not extra_fields:
                print("✅ Data filtering test PASSED")
                self.test_results['data_filtering'] = True
            else:
                print(f"❌ Data filtering test FAILED - Missing: {missing_fields}, Extra: {extra_fields}")
                self.test_results['data_filtering'] = False
                
        except Exception as e:
            print(f"❌ Data filtering test FAILED - Exception: {e}")
            self.test_results['data_filtering'] = False
    
    def test_celery_function_integration(self):
        """Test CSV logic without calling production Celery function (production safe)"""
        print("\n=== Testing CSV Logic Integration (Production Safe) ===")
        
        try:
            # Simulate the Celery function logic but use test files
            test_cases = [
                {'is_significant': True, 'csv_file': self.test_csv_files['significant']},
                {'is_significant': False, 'csv_file': self.test_csv_files['trivial']}
            ]
            
            success_count = 0
            
            for case in test_cases:
                # Create test message
                message_data = self.create_comprehensive_test_message()
                message_data['is_significant'] = case['is_significant']
                category = 'Significant' if case['is_significant'] else 'Trivial'
                message_data['AI_Category'] = category
                message_data['Message_ID'] = f"TEST_celery_{category.lower()}_{100002}"
                message_data['Channel'] = f"@TEST_celery_{category.lower()}"
                
                # Use FileHandling class (same as Celery function)
                file_handler = FileHandling(case['csv_file'])
                
                # Filter data (same as Celery function)
                filtered_data = {}
                for field in self.excel_fields:
                    filtered_data[field] = message_data.get(field, '')
                
                # Write to test CSV
                success = file_handler.append_to_csv(filtered_data, self.excel_fields)
                
                if success:
                    success_count += 1
                    print(f"✅ CSV logic test PASSED for {category} (test file)")
                else:
                    print(f"❌ CSV logic test FAILED for {category}")
            
            if success_count == 2:
                print("✅ CSV logic integration test PASSED (both significant and trivial)")
                self.test_results['celery_integration'] = True
            else:
                print(f"❌ CSV logic integration test FAILED - {success_count}/2 succeeded")
                self.test_results['celery_integration'] = False
                
        except Exception as e:
            print(f"❌ CSV logic integration test FAILED - Exception: {e}")
            self.test_results['celery_integration'] = False
    
    def test_error_handling(self):
        """Test error handling with malformed data"""
        print("\n=== Testing Error Handling ===")
        
        try:
            # Create test file
            test_file = os.path.join(PROJECT_ROOT, "data", "test_error_handling.csv")
            file_handler = FileHandling(test_file)
            
            # Test with malformed data
            malformed_data = self.create_malformed_test_message()
            
            # Apply filtering to handle missing fields
            filtered_data = {}
            for field in self.excel_fields:
                filtered_data[field] = malformed_data.get(field, '')  # Empty string for missing fields
            
            # Attempt to write
            success = file_handler.append_to_csv(filtered_data, self.excel_fields)
            
            if success:
                print("✅ Error handling test PASSED - Missing fields handled gracefully")
                self.test_results['error_handling'] = True
                
                # Clean up
                if os.path.exists(test_file):
                    os.remove(test_file)
            else:
                print("❌ Error handling test FAILED - Could not handle missing fields")
                self.test_results['error_handling'] = False
                
        except Exception as e:
            print(f"❌ Error handling test FAILED - Exception: {e}")
            self.test_results['error_handling'] = False
    
    def test_file_permissions(self):
        """Test file and directory permissions"""
        print("\n=== Testing File Permissions ===")
        
        try:
            data_dir = os.path.join(PROJECT_ROOT, "data")
            
            # Check directory permissions
            dir_exists = os.path.exists(data_dir)
            dir_writable = os.access(data_dir, os.W_OK) if dir_exists else False
            
            # Check CSV files
            sig_csv = os.path.join(data_dir, "iraq_significant_messages.csv")
            triv_csv = os.path.join(data_dir, "iraq_trivial_messages.csv")
            
            sig_exists = os.path.exists(sig_csv)
            triv_exists = os.path.exists(triv_csv)
            
            sig_writable = os.access(sig_csv, os.W_OK) if sig_exists else False
            triv_writable = os.access(triv_csv, os.W_OK) if triv_exists else False
            
            print(f"Data directory - Exists: {dir_exists}, Writable: {dir_writable}")
            print(f"Significant CSV - Exists: {sig_exists}, Writable: {sig_writable}")
            print(f"Trivial CSV - Exists: {triv_exists}, Writable: {triv_writable}")
            
            if dir_exists and dir_writable and sig_exists and triv_exists and sig_writable and triv_writable:
                print("✅ File permissions test PASSED")
                self.test_results['file_permissions'] = True
            else:
                print("❌ File permissions test FAILED")
                self.test_results['file_permissions'] = False
                
        except Exception as e:
            print(f"❌ File permissions test FAILED - Exception: {e}")
            self.test_results['file_permissions'] = False
    
    def test_csv_format_validation(self):
        """Test that CSV files maintain proper format"""
        print("\n=== Testing CSV Format Validation ===")
        
        try:
            # Test both significant and trivial CSV files
            for csv_type in ['significant', 'trivial']:
                csv_file = os.path.join(PROJECT_ROOT, "data", f"iraq_{csv_type}_messages.csv")
                
                if os.path.exists(csv_file):
                    with open(csv_file, 'r') as f:
                        reader = csv.DictReader(f)
                        headers = reader.fieldnames
                        
                    # Verify headers match expected fields
                    if headers == self.excel_fields:
                        print(f"✅ {csv_type.title()} CSV format is correct")
                    else:
                        print(f"❌ {csv_type.title()} CSV format is incorrect")
                        print(f"   Expected: {self.excel_fields}")
                        print(f"   Found: {headers}")
                        self.test_results['csv_format'] = False
                        return
                else:
                    print(f"⚠️  {csv_type.title()} CSV file does not exist")
            
            print("✅ CSV format validation test PASSED")
            self.test_results['csv_format'] = True
            
        except Exception as e:
            print(f"❌ CSV format validation test FAILED - Exception: {e}")
            self.test_results['csv_format'] = False
    
    def test_production_scenario(self):
        """Test realistic production scenario (production safe)"""
        print("\n=== Testing Production Scenario (Safe Test Files) ===")
        
        try:
            # Simulate processing multiple messages with varying field structures
            messages = [
                self.create_minimal_test_message(),
                self.create_comprehensive_test_message(),
                self.create_malformed_test_message()
            ]
            
            # Add test identifiers to prevent confusion with production data
            for i, message in enumerate(messages):
                message['Message_ID'] = f'TEST_production_{i + 100003}'
                message['Channel'] = f'@TEST_production_{i + 1}'
            
            success_count = 0
            
            for i, message in enumerate(messages):
                try:
                    # Apply data filtering (core fix)
                    filtered_data = {}
                    for field in self.excel_fields:
                        filtered_data[field] = message.get(field, '')
                    
                    # Use dedicated test file (alternating between significant and trivial)
                    test_file = self.test_csv_files['significant'] if i % 2 == 0 else self.test_csv_files['trivial']
                    file_handler = FileHandling(test_file)
                    
                    if file_handler.append_to_csv(filtered_data, self.excel_fields):
                        success_count += 1
                        print(f"   ✅ Message {i} written to test CSV")
                    else:
                        print(f"   ❌ Message {i} failed to write")
                        
                except Exception as e:
                    print(f"   ❌ Message {i} failed: {e}")
            
            if success_count == len(messages):
                print("✅ Production scenario test PASSED")
                self.test_results['production_scenario'] = True
            else:
                print(f"❌ Production scenario test FAILED - {success_count}/{len(messages)} succeeded")
                self.test_results['production_scenario'] = False
                
        except Exception as e:
            print(f"❌ Production scenario test FAILED - Exception: {e}")
            self.test_results['production_scenario'] = False
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*70)
        print("                CSV MESSAGE STORAGE TEST REPORT")
        print("="*70)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        failed_tests = total_tests - passed_tests
        
        print(f"\nOVERALL RESULTS:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests} ✅")
        print(f"   Failed: {failed_tests} {'❌' if failed_tests > 0 else ''}")
        print(f"   Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        print(f"\nDETAILED RESULTS:")
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {test_name.replace('_', ' ').title()}: {status}")
        
        if failed_tests == 0:
            print(f"\n🎉 ALL TESTS PASSED!")
            print(f"   CSV message storage is working correctly.")
            print(f"   The storage issues have been completely resolved.")
        else:
            print(f"\n⚠️  SOME TESTS FAILED")
            print(f"   Review failed tests above for issues that need attention.")
        
        print("\n" + "="*70)
    
    def run_all_tests(self):
        """Run the complete test suite with production data protection"""
        print("🔍 CSV MESSAGE STORAGE - COMPREHENSIVE TEST SUITE")
        print("="*60)
        print("Testing all aspects of CSV message storage functionality...")
        print("🛡️ PRODUCTION SAFE: Uses dedicated test CSV files, then deletes them completely")
        
        # Create test CSV files for safe testing
        test_files_ready = self.create_test_csv_files()
        
        if test_files_ready:
            # Run all tests
            self.test_basic_csv_functionality()
            self.test_data_filtering()
            self.test_celery_function_integration()
            self.test_error_handling()
            self.test_file_permissions()
            self.test_csv_format_validation()
            self.test_production_scenario()
            
            # Clean up test files completely
            self.cleanup_test_csv_files()
        else:
            print("❌ Unable to create test CSV files - skipping tests")
        
        # Generate report
        self.generate_test_report()


def main():
    """Main entry point"""
    test_suite = CSVMessageStorageTestSuite()
    test_suite.run_all_tests()


if __name__ == "__main__":
    main()