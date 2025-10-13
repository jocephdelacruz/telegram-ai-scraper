# Configurable Field Exclusions - Implementation Guide

## Overview
The Telegram AI Scraper now supports **configurable field exclusions** for Teams notifications and SharePoint Excel files, allowing administrators to customize what information is displayed to end users while preserving complete data integrity in CSV files.

## 🚀 **Key Features**

### **User-Friendly Display**
- Teams and SharePoint show only relevant information to end users
- Technical metadata fields are hidden by default
- Redundant fields (like Author = Channel) are excluded

### **Complete Data Preservation**
- CSV files maintain all 17 fields for future database migration
- No data loss - everything is preserved for analytics
- Full audit trail maintained

### **Easy Customization**
- Modify exclusions in `config.json` without code changes
- Different exclusions possible for Teams vs SharePoint
- Add/remove fields simply by editing configuration

## 📋 **Configuration**

### Required Configuration Fields

Add these new sections to your `config.json`:

```json
{
  "TELEGRAM_EXCEL_FIELDS": [
    "Message_ID", "Channel", "Country", "Date", "Time", "Author", "Message_Text",
    "AI_Category", "AI_Reasoning", "Keywords_Matched", "Message_Type",
    "Forward_From", "Media_Type", "Original_Text", "Original_Language",
    "Was_Translated", "Processed_Date"
  ],
  "EXCLUDED_TEAMS_FIELDS": [
    "Country", "AI_Category", "Message_Type", "Forward_From", "Media_Type",
    "Was_Translated", "Processed_Date", "Author"
  ],
  "EXCLUDED_SHAREPOINT_FIELDS": [
    "Country", "AI_Category", "Message_Type", "Forward_From", "Media_Type",
    "Was_Translated", "Processed_Date", "Author"
  ]
}
```

### Field Descriptions

**TELEGRAM_EXCEL_FIELDS** (17 total fields):
- Master list of all available data fields
- Used for CSV storage (preserves all fields)
- Cannot be modified without code changes

**EXCLUDED_TEAMS_FIELDS** (8 excluded by default):
- Fields to hide from Teams notifications
- Easily customizable - remove items to show them
- Teams displays `17 - 8 = 9` fields by default

**EXCLUDED_SHAREPOINT_FIELDS** (8 excluded by default):
- Fields to hide from SharePoint Excel files
- Same as Teams by default, but can be different
- SharePoint displays `17 - 8 = 9` fields by default

## 🎯 **Default Exclusions Explained**

### Why These Fields Are Excluded

1. **Country**: Redundant (already shown in title and context)
2. **AI_Category**: Internal classification (Significant vs Trivial)
3. **Message_Type**: Technical metadata (text, photo, video, etc.)
4. **Forward_From**: Technical forwarding information
5. **Media_Type**: Technical media type information
6. **Was_Translated**: Internal processing flag
7. **Processed_Date**: Internal timestamp (different from message date)
8. **Author**: Redundant with Channel in Telegram context

### What's Still Shown (9 fields)

1. **Message_ID**: Unique identifier for reference
2. **Channel**: Source channel name
3. **Date**: When message was posted
4. **Time**: Time message was posted
5. **Message_Text**: The actual message content
6. **AI_Reasoning**: Why AI classified it as significant
7. **Keywords_Matched**: Keywords that triggered classification
8. **Original_Text**: Original text before translation
9. **Original_Language**: Detected language of original message

## 🔧 **Customization Examples**

### Show Country Information
To display country information in Teams notifications:

```json
"EXCLUDED_TEAMS_FIELDS": [
  "AI_Category", "Message_Type", "Forward_From", "Media_Type",
  "Was_Translated", "Processed_Date", "Author"
]
```

### Show Processing Metadata
To display when messages were processed:

```json
"EXCLUDED_TEAMS_FIELDS": [
  "Country", "AI_Category", "Message_Type", "Forward_From", "Media_Type",
  "Was_Translated", "Author"
]
```

### Different Settings for Teams vs SharePoint
```json
"EXCLUDED_TEAMS_FIELDS": [
  "Country", "AI_Category", "Message_Type", "Forward_From", "Media_Type",
  "Was_Translated", "Processed_Date", "Author"
],
"EXCLUDED_SHAREPOINT_FIELDS": [
  "AI_Category", "Message_Type", "Forward_From", "Media_Type",
  "Was_Translated", "Author"
]
```

### Show All Fields (No Exclusions)
```json
"EXCLUDED_TEAMS_FIELDS": [],
"EXCLUDED_SHAREPOINT_FIELDS": []
```

## 🧪 **Testing**

### Run Field Exclusions Test
```bash
# Test the field exclusions system
python3 scripts/run_tests.py --field-exclusions

# Or run as part of comprehensive test suite
python3 scripts/run_tests.py
```

### Manual Testing
1. Modify `config.json` exclusion fields
2. Send a test message through the system
3. Check Teams notification has expected fields
4. Check SharePoint Excel has expected fields
5. Verify CSV still has all 17 fields

## 📊 **Data Flow Architecture**

```
Message Processing
       ↓
17 Fields Captured
       ↓
    ┌─────────────────────────────────────┐
    │           Field Router              │
    └─────────────────────────────────────┘
    ↓              ↓                     ↓
Teams (9 fields)  SharePoint (9 fields)  CSV (17 fields)
Filter by config  Filter by config       No filtering
EXCLUDED_TEAMS    EXCLUDED_SHAREPOINT     Complete preservation
```

## 🔄 **Migration from Previous Versions**

### Automatic Migration
- Old systems will continue working (hardcoded exclusions as fallback)
- New config fields are optional - system provides defaults
- No breaking changes to existing functionality

### Manual Migration Steps
1. Update `config/config.json` with new exclusion fields
2. Update `config/config_sample.json` if customizing
3. Run field exclusions test to validate configuration
4. Optionally customize which fields are shown

## ⚡ **Performance Impact**

- **Minimal overhead**: Simple array filtering
- **No database changes**: Only affects display logic
- **Backward compatible**: Old systems continue working
- **Memory efficient**: No duplication of data

## 🛠️ **Technical Implementation**

### Files Modified
- `config/config.json`: Added exclusion configuration
- `config/config_sample.json`: Added sample exclusion configuration
- `src/tasks/telegram_celery_tasks.py`: SharePoint filtering from config
- `src/integrations/teams_utils.py`: Teams filtering from config
- `scripts/setup.sh`: Updated default config template
- `tests/test_comprehensive_field_exclusions.py`: New consolidated test

### Key Functions
- `TeamsNotifier._load_excluded_teams_fields()`: Loads Teams exclusions from config
- Teams `send_message_alert()`: Filters facts based on excluded fields
- SharePoint task filtering: Creates filtered field list from config

## 🎉 **Benefits**

### For Administrators
- **Easy customization**: Change display without coding
- **Flexible configuration**: Different settings for different outputs
- **No data loss**: Complete preservation in CSV files

### For End Users
- **Cleaner notifications**: Only relevant information shown
- **Focused attention**: Less clutter in Teams alerts
- **Better readability**: Streamlined SharePoint Excel files

### For Developers
- **Maintainable**: Logic separated from hardcoded values
- **Extensible**: Easy to add new fields or outputs
- **Testable**: Comprehensive test coverage for all scenarios

## 📝 **Future Enhancements**

### Potential Extensions
- **Per-country exclusions**: Different fields for different countries
- **Role-based exclusions**: Different fields for different user groups
- **Dynamic exclusions**: Time-based or condition-based field filtering
- **Field grouping**: Logical grouping of related fields

### Configuration UI
- **Web interface**: Browser-based configuration management
- **Validation**: Real-time config validation and preview
- **Templates**: Pre-defined exclusion templates for common scenarios