# AI Exception Filtering System

## Overview

The AI Exception Filtering system is an advanced feature that uses OpenAI's GPT models to filter out messages that may match keywords but are not actually relevant to the target country. This helps reduce false positives in message classification, especially for news about other countries or international events.

## When to Use

Enable AI exception filtering when you experience:
- False positives from news about other countries
- International events being classified as locally significant
- Foreign political developments appearing as relevant
- Overseas incidents being categorized incorrectly

## Configuration

### Basic Setup

In your `config.json`, add these fields to each country's `message_filtering` section:

```json
{
  "message_filtering": {
    "use_ai_for_enhanced_filtering": true,
    "ai_exception_rules": [
      "news about other countries or regions",
      "international events not affecting [COUNTRY_NAME]",
      "foreign political developments",
      "overseas incidents or accidents"
    ]
  }
}
```

### Configuration Fields

#### `use_ai_for_enhanced_filtering`
- **Type**: Boolean
- **Default**: `false`
- **Description**: Enables AI-based exception checking for messages that match keywords

#### `ai_exception_rules`
- **Type**: Array of strings
- **Description**: List of patterns or contexts that should be filtered out
- **Examples**:
  - `"news about other countries or regions"`
  - `"international events not affecting [country]"`
  - `"foreign political developments"`
  - `"sports events in other countries"`
  - `"weather reports from foreign locations"`

## How It Works

### Processing Flow

1. **Keyword Matching**: Message is first checked against significant/trivial keywords
2. **Language Detection**: System determines message language (enhanced Arabic detection)
3. **Exception Checking**: If AI enhanced filtering is enabled:
   - Message is analyzed against exception rules
   - AI determines if message is actually relevant to target country
   - Exception check occurs in both direct keyword matching and AI analysis phases

### AI Analysis Process

The system sends the message to OpenAI with:
- The original message text
- Target country context
- Exception rules to check against
- Request to determine geographical relevance

### Dual-Phase Filtering

1. **Direct Keyword Phase**: Exception checking during regular keyword matching
2. **AI Analysis Phase**: Additional exception validation during AI-powered analysis

## Example Scenarios

### Before AI Exception Filtering
```
Message: "Breaking: Cyber attack hits government servers in Syria"
Keywords Matched: "breaking", "cyber attack", "government"
Classification: SIGNIFICANT ❌ (False Positive)
```

### After AI Exception Filtering
```
Message: "Breaking: Cyber attack hits government servers in Syria"
Keywords Matched: "breaking", "cyber attack", "government"
Exception Check: ✅ "news about other countries" - FILTERED OUT
Classification: TRIVIAL ✅ (Correctly Filtered)
```

## Best Practices

### Exception Rule Design

1. **Be Specific**: Include country-specific rules
   ```json
   "international events not affecting Iraq"
   ```

2. **Cover Common Patterns**:
   ```json
   [
     "news about other countries or regions",
     "foreign political developments", 
     "overseas incidents or accidents",
     "international sports events",
     "weather reports from other locations"
   ]
   ```

3. **Avoid Over-Filtering**: Don't make rules too broad
   ```json
   // ❌ Too broad
   "any international news"
   
   // ✅ More specific
   "international events not affecting Singapore"
   ```

### Performance Considerations

1. **API Costs**: Each exception check uses OpenAI API credits
2. **Processing Time**: Adds ~1-2 seconds per message analysis
3. **Selective Enabling**: Only enable for countries with high false positive rates

## Implementation Details

### Core Functions

#### `_checkExceptionRules(message_text, country_name, exception_rules)`
- Validates message against exception rules
- Returns boolean indicating if message should be filtered
- Located in `src/integrations/openai_utils.py`

#### Enhanced `isMessageSignificant()` 
- Integrates exception checking into message classification
- Handles both keyword-based and AI-based filtering
- Located in `src/core/message_processor.py`

### Logging

The system logs exception checking activities:
```
[INFO] AI Exception Check: Message about Syria filtered out for Iraq
[DEBUG] Exception rules applied: ['news about other countries or regions']
```

## Troubleshooting

### Common Issues

1. **High API Costs**
   - **Solution**: Reduce `ai_exception_rules` to most essential patterns
   - **Alternative**: Use selective enabling based on keyword confidence

2. **Over-Filtering**
   - **Symptom**: Too many legitimate messages being marked as trivial
   - **Solution**: Refine exception rules to be more specific

3. **Under-Filtering**
   - **Symptom**: Still getting false positives
   - **Solution**: Add more specific exception patterns

### Testing Exception Rules

Use the test framework to validate your rules:

```bash
# Test specific exception rules
python tests/test_ai_exception_filtering.py

# Test with sample messages
python scripts/run_tests.py --test-ai-exceptions
```

## Configuration Examples

### Conservative Setup (Low API Usage)
```json
{
  "use_ai_for_enhanced_filtering": true,
  "ai_exception_rules": [
    "news about other countries or regions"
  ]
}
```

### Comprehensive Setup (Higher Accuracy)
```json
{
  "use_ai_for_enhanced_filtering": true,
  "ai_exception_rules": [
    "news about other countries or regions",
    "international events not affecting Iraq",
    "foreign political developments",
    "overseas incidents or accidents",
    "weather reports from other locations",
    "sports events in foreign countries"
  ]
}
```

### Country-Specific Example (Iraq)
```json
{
  "use_ai_for_enhanced_filtering": true,
  "ai_exception_rules": [
    "news about Syria, Iran, Turkey, or other Middle Eastern countries not affecting Iraq",
    "international conflicts not involving Iraq",
    "foreign government policies not impacting Iraq",
    "regional incidents outside Iraqi borders"
  ]
}
```

## Integration Notes

### Existing Features
- Works alongside existing keyword matching
- Compatible with AI-powered translation
- Integrates with language detection enhancements

### Future Enhancements
- Caching for repeated exception patterns
- Machine learning model for local pattern recognition
- Dynamic rule adjustment based on accuracy feedback

## Support

For questions about AI Exception Filtering:
1. Check the logs for detailed processing information
2. Test with sample messages using the test framework
3. Review API usage in OpenAI dashboard
4. Adjust exception rules based on observed patterns

---

**Last Updated**: December 2024  
**Version**: 1.0  
**Related Documents**: EFFICIENT_FETCHING_SYSTEM.md, TRANSLATION_GUIDE.md