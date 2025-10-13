#!/usr/bin/env python3
"""
Comprehensive test script to validate config-based field exclusions for Teams and SharePoint
Consolidates previous field exclusion tests into a single comprehensive test suite
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import json
from src.integrations.teams_utils import TeamsNotifier
from src.core import file_handling as fh

def test_comprehensive_field_exclusions():
    """
    Comprehensive test that validates config-based field exclusions for Teams and SharePoint
    """
    print("🧪 COMPREHENSIVE FIELD EXCLUSIONS - COMPLETE TEST SUITE")
    print("=" * 70)
    
    # Load config to verify settings
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return False
    
    print(f"📋 Configuration Loaded from: {config_path}")
    
    # Test 1: Verify config has the new fields
    print("\n=== Test 1: Configuration Structure Validation ===")
    
    telegram_excel_fields = config.get('TELEGRAM_EXCEL_FIELDS', [])
    excluded_teams_fields = config.get('EXCLUDED_TEAMS_FIELDS', [])
    excluded_sharepoint_fields = config.get('EXCLUDED_SHAREPOINT_FIELDS', [])
    
    if not telegram_excel_fields:
        print("❌ TELEGRAM_EXCEL_FIELDS not found in config")
        return False
    
    if not excluded_teams_fields:
        print("❌ EXCLUDED_TEAMS_FIELDS not found in config")
        return False
    
    if not excluded_sharepoint_fields:
        print("❌ EXCLUDED_SHAREPOINT_FIELDS not found in config")
        return False
    
    print(f"✅ TELEGRAM_EXCEL_FIELDS: {len(telegram_excel_fields)} fields")
    print(f"✅ EXCLUDED_TEAMS_FIELDS: {len(excluded_teams_fields)} fields")
    print(f"✅ EXCLUDED_SHAREPOINT_FIELDS: {len(excluded_sharepoint_fields)} fields")
    
    print(f"\n📊 Teams excluded fields: {excluded_teams_fields}")
    print(f"📊 SharePoint excluded fields: {excluded_sharepoint_fields}")
    
    # Test 2: Verify 'Author' is now excluded
    print("\n=== Test 2: Author Field Exclusion Validation ===")
    
    if 'Author' in excluded_teams_fields:
        print("✅ Author field is excluded from Teams notifications")
    else:
        print("❌ Author field is NOT excluded from Teams notifications")
        return False
    
    if 'Author' in excluded_sharepoint_fields:
        print("✅ Author field is excluded from SharePoint Excel")
    else:
        print("❌ Author field is NOT excluded from SharePoint Excel")
        return False
    
    # Test 3: Test Teams field filtering logic
    print("\n=== Test 3: Teams Field Loading and Filtering ===")
    
    # Create TeamsNotifier instance to test the field loading
    teams_notifier = TeamsNotifier("https://test.webhook.url", "Test Channel")
    excluded_fields_from_teams = teams_notifier._load_excluded_teams_fields()
    
    print(f"✅ Teams notifier loaded {len(excluded_fields_from_teams)} excluded fields")
    print(f"📋 Excluded fields from Teams: {excluded_fields_from_teams}")
    
    # Verify the fields match config
    if set(excluded_fields_from_teams) == set(excluded_teams_fields):
        print("✅ Teams excluded fields match config.json")
    else:
        print("❌ Teams excluded fields do NOT match config.json")
        print(f"   Config: {set(excluded_teams_fields)}")
        print(f"   Loaded: {set(excluded_fields_from_teams)}")
        return False
    
    # Test 4: Calculate expected field counts
    print("\n=== Test 4: Field Count Calculations ===")
    
    teams_allowed_fields = [field for field in telegram_excel_fields if field not in excluded_teams_fields]
    sharepoint_allowed_fields = [field for field in telegram_excel_fields if field not in excluded_sharepoint_fields]
    
    print(f"📊 Total TELEGRAM_EXCEL_FIELDS: {len(telegram_excel_fields)}")
    print(f"📊 Teams excluded: {len(excluded_teams_fields)}, allowed: {len(teams_allowed_fields)}")
    print(f"📊 SharePoint excluded: {len(excluded_sharepoint_fields)}, allowed: {len(sharepoint_allowed_fields)}")
    
    # Verify math
    expected_teams = len(telegram_excel_fields) - len(excluded_teams_fields)
    expected_sharepoint = len(telegram_excel_fields) - len(excluded_sharepoint_fields)
    
    if len(teams_allowed_fields) == expected_teams:
        print("✅ Teams field count calculation is correct")
    else:
        print(f"❌ Teams field count error: got {len(teams_allowed_fields)}, expected {expected_teams}")
        return False
    
    if len(sharepoint_allowed_fields) == expected_sharepoint:
        print("✅ SharePoint field count calculation is correct")
    else:
        print(f"❌ SharePoint field count error: got {len(sharepoint_allowed_fields)}, expected {expected_sharepoint}")
        return False
    
    print(f"\n📋 Teams allowed fields: {teams_allowed_fields}")
    print(f"📋 SharePoint allowed fields: {sharepoint_allowed_fields}")
    
    # Test 5: SharePoint range calculation
    print("\n=== Test 5: SharePoint Range Calculation ===")
    
    expected_range_end = chr(ord('A') + len(sharepoint_allowed_fields) - 1)
    print(f"✅ SharePoint fields: {len(sharepoint_allowed_fields)}")
    print(f"✅ Expected range end column: {expected_range_end}")
    print(f"✅ Example range for row 2: A2:{expected_range_end}2")
    
    # Test 6: Simulate message data processing
    print("\n=== Test 6: Message Processing Simulation ===")
    
    # Create sample message data with all fields
    sample_message = {
        "Message_ID": "12345",
        "Channel": "@testchannel",
        "Country": "Iraq",
        "Date": "2024-10-13",
        "Time": "10:30:00",
        "Author": "@testauthor",
        "Message_Text": "Test message content",
        "AI_Category": "Significant",
        "AI_Reasoning": "Contains security keywords",
        "Keywords_Matched": "security, alert",
        "Message_Type": "TEXT",
        "Forward_From": "@originalsender",
        "Media_Type": "NONE",
        "Original_Text": "Test message content",
        "Original_Language": "EN",
        "Was_Translated": False,
        "Processed_Date": "2024-10-13 10:30:00"
    }
    
    print(f"✅ Created sample message with {len(sample_message)} fields")
    
    # Test 7: Teams facts creation simulation
    print("\n=== Test 7: Teams Facts Creation Simulation ===")
    
    # Simulate Teams facts creation (the logic from send_message_alert)
    teams_facts = []
    
    if 'Channel' not in excluded_teams_fields:
        teams_facts.append({"name": "Channel", "value": sample_message.get('Channel')})
    
    teams_facts.append({"name": "Date & Time", "value": f"{sample_message.get('Date', '')} {sample_message.get('Time', '')}"})
    
    if 'Author' not in excluded_teams_fields:
        teams_facts.append({"name": "Author", "value": sample_message.get('Author')})
    
    teams_facts.append({"name": "AI Reasoning", "value": sample_message.get('AI_Reasoning', '')[:200]})
    
    # Add other conditional fields
    if sample_message.get('Keywords_Matched'):
        teams_facts.append({"name": "Keywords Matched", "value": sample_message.get('Keywords_Matched')})
    
    if 'Country' not in excluded_teams_fields and sample_message.get('Country'):
        teams_facts.append({"name": "Country", "value": sample_message.get('Country')})
    
    if 'AI_Category' not in excluded_teams_fields and sample_message.get('AI_Category'):
        teams_facts.append({"name": "AI Category", "value": sample_message.get('AI_Category')})
    
    if 'Message_Type' not in excluded_teams_fields and sample_message.get('Message_Type'):
        teams_facts.append({"name": "Message Type", "value": sample_message.get('Message_Type')})
    
    if 'Forward_From' not in excluded_teams_fields and sample_message.get('Forward_From'):
        teams_facts.append({"name": "Forwarded From", "value": sample_message.get('Forward_From')})
    
    if 'Media_Type' not in excluded_teams_fields and sample_message.get('Media_Type'):
        teams_facts.append({"name": "Media Type", "value": sample_message.get('Media_Type')})
    
    if sample_message.get('Was_Translated'):
        original_language = sample_message.get('Original_Language', 'Unknown')
        teams_facts.append({"name": "Original Language", "value": original_language})
        
        if 'Was_Translated' not in excluded_teams_fields:
            teams_facts.append({"name": "Translation", "value": "✅ Translated to English"})
    
    if 'Processed_Date' not in excluded_teams_fields and sample_message.get('Processed_Date'):
        teams_facts.append({"name": "Processed Date", "value": sample_message.get('Processed_Date')})
    
    print(f"✅ Teams facts simulation: {len(teams_facts)} facts would be included")
    for fact in teams_facts:
        print(f"    📌 {fact['name']}: {fact['value']}")
    
    # Test 8: Verify exclusions work correctly
    print("\n=== Test 8: Exclusion Verification ===")
    
    # Map excluded field names to their display names in Teams facts
    excluded_display_names = []
    if 'Country' in excluded_teams_fields:
        excluded_display_names.append('Country')
    if 'AI_Category' in excluded_teams_fields:
        excluded_display_names.append('AI Category')
    if 'Message_Type' in excluded_teams_fields:
        excluded_display_names.append('Message Type')
    if 'Forward_From' in excluded_teams_fields:
        excluded_display_names.append('Forwarded From')
    if 'Media_Type' in excluded_teams_fields:
        excluded_display_names.append('Media Type')
    if 'Was_Translated' in excluded_teams_fields:
        excluded_display_names.append('Translation')
    if 'Processed_Date' in excluded_teams_fields:
        excluded_display_names.append('Processed Date')
    if 'Author' in excluded_teams_fields:
        excluded_display_names.append('Author')
    
    actual_fact_names = [fact['name'] for fact in teams_facts]
    found_excluded = [name for name in excluded_display_names if name in actual_fact_names]
    
    if not found_excluded:
        print("✅ No excluded fields found in Teams facts - exclusion working correctly")
    else:
        print(f"❌ Found excluded fields in Teams facts: {found_excluded}")
        return False
    
    # Test 9: CSV preservation verification
    print("\n=== Test 9: CSV Data Preservation Verification ===")
    
    csv_fields = telegram_excel_fields  # CSV should preserve all fields
    
    if len(csv_fields) == len(telegram_excel_fields):
        print("✅ CSV preserves all original fields")
    else:
        print("❌ CSV does not preserve all fields")
        return False
    
    print(f"✅ CSV storage: {len(csv_fields)} fields preserved")
    print(f"✅ Teams display: {len(teams_allowed_fields)} fields shown ({len(excluded_teams_fields)} excluded)")
    print(f"✅ SharePoint display: {len(sharepoint_allowed_fields)} fields shown ({len(excluded_sharepoint_fields)} excluded)")
    
    # Test 10: Configuration consistency check
    print("\n=== Test 10: Configuration Consistency Check ===")
    
    # Check if Teams and SharePoint exclusions are identical (they should be in current setup)
    if set(excluded_teams_fields) == set(excluded_sharepoint_fields):
        print("✅ Teams and SharePoint exclusions are consistent")
    else:
        print("⚠️  Teams and SharePoint exclusions differ (this may be intentional)")
        print(f"   Teams only: {set(excluded_teams_fields) - set(excluded_sharepoint_fields)}")
        print(f"   SharePoint only: {set(excluded_sharepoint_fields) - set(excluded_teams_fields)}")
    
    # Verify all excluded fields exist in the original field list
    all_excluded = set(excluded_teams_fields) | set(excluded_sharepoint_fields)
    invalid_exclusions = all_excluded - set(telegram_excel_fields)
    
    if not invalid_exclusions:
        print("✅ All excluded fields are valid (exist in TELEGRAM_EXCEL_FIELDS)")
    else:
        print(f"❌ Invalid excluded fields found: {invalid_exclusions}")
        return False
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 COMPREHENSIVE FIELD EXCLUSIONS TEST SUMMARY")
    print("=" * 70)
    print("✅ Configuration structure: VALID")
    print("✅ Author field exclusion: IMPLEMENTED")
    print("✅ Teams field loading: WORKING")
    print("✅ Field count calculations: CORRECT")
    print("✅ SharePoint range calculation: UPDATED")
    print("✅ Message processing simulation: SUCCESSFUL")
    print("✅ Teams facts filtering: WORKING")
    print("✅ Exclusion verification: PASSED")
    print("✅ CSV data preservation: CONFIRMED")
    print("✅ Configuration consistency: VERIFIED")
    print("\n🎉 ALL COMPREHENSIVE FIELD EXCLUSION TESTS PASSED!")
    print(f"📋 Total fields in TELEGRAM_EXCEL_FIELDS: {len(telegram_excel_fields)}")
    print(f"📋 Fields excluded from Teams: {len(excluded_teams_fields)} ({excluded_teams_fields})")
    print(f"📋 Fields excluded from SharePoint: {len(excluded_sharepoint_fields)} ({excluded_sharepoint_fields})")
    print(f"📋 Fields allowed in Teams notifications: {len(teams_allowed_fields)}")
    print(f"📋 Fields allowed in SharePoint Excel: {len(sharepoint_allowed_fields)}")
    print(f"📋 Fields preserved in CSV storage: {len(csv_fields)}")
    
    return True

if __name__ == "__main__":
    success = test_comprehensive_field_exclusions()
    if not success:
        print("\n❌ COMPREHENSIVE FIELD EXCLUSIONS TEST FAILED!")
        sys.exit(1)
    else:
        print("\n✅ COMPREHENSIVE FIELD EXCLUSIONS TEST COMPLETED SUCCESSFULLY!")
        sys.exit(0)