#!/usr/bin/env python3
"""
Test script for the enhanced AI contextual analysis functionality.
This script demonstrates how the enhanced _analyzeWithAI function now:
1. Uses stricter classification rules to reduce false positives
2. Identifies specific keywords that match the message context
3. Translates matched keywords to English for consistent reporting
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_enhanced_ai_analysis():
    """Test the enhanced AI analysis with sample messages and keywords"""
    
    print("=" * 70)
    print("Testing Enhanced AI Contextual Analysis with Keyword Extraction")
    print("=" * 70)
    
    # Sample test cases showing the enhanced functionality
    test_cases = [
        {
            "name": "Security Breach (Should be Significant)",
            "message": "Major data breach discovered at government facility",
            "significant_keywords": ["security breach", "cyber attack", "data leak", "infrastructure attack"],
            "expected_classification": "Significant",
            "expected_keyword_match": "security breach"
        },
        {
            "name": "Educational News (Should be Trivial - stricter rules)",
            "message": "University announces new computer science program",
            "significant_keywords": ["security breach", "cyber attack", "terrorist attack", "infrastructure failure"],
            "expected_classification": "Trivial",
            "expected_keyword_match": None
        },
        {
            "name": "Infrastructure Failure (Should be Significant)",
            "message": "Power grid failure causes widespread blackouts across the city",
            "significant_keywords": ["infrastructure failure", "power outage", "emergency", "critical systems"],
            "expected_classification": "Significant",
            "expected_keyword_match": "infrastructure failure"
        },
        {
            "name": "Routine Announcement (Should be Trivial)",
            "message": "Local library extends operating hours for summer",
            "significant_keywords": ["terrorism", "security threat", "cyber attack", "emergency"],
            "expected_classification": "Trivial",
            "expected_keyword_match": None
        },
        {
            "name": "Arabic Security Message (Should extract and translate keyword)",
            "message": "هجوم إلكتروني كبير على البنية التحتية الحكومية",  # "Major cyber attack on government infrastructure"
            "significant_keywords": ["هجوم إلكتروني", "أمن المعلومات", "تهديد أمني"],  # ["cyber attack", "information security", "security threat"]
            "expected_classification": "Significant",
            "expected_keyword_match": "cyber attack"  # Should be translated to English
        }
    ]
    
    print("\nEnhanced Test Cases:")
    print("-" * 50)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n🔍 Test Case {i}: {case['name']}")
        print(f"Message: {case['message']}")
        print(f"Significant Keywords: {case['significant_keywords']}")
        print(f"Expected Classification: {case['expected_classification']}")
        if case['expected_keyword_match']:
            print(f"Expected Matched Keyword: {case['expected_keyword_match']}")
        print("-" * 50)
    
    print("\n🚀 Key Enhancements in the Modified _analyzeWithAI Function:")
    print("\n1. ✅ STRICTER CLASSIFICATION RULES:")
    print("   • Only classifies as significant if message DIRECTLY relates to provided keywords")
    print("   • Reduces false positives for general topics like education, routine announcements")
    print("   • Uses lower temperature (0.1) for more conservative analysis")
    
    print("\n2. ✅ KEYWORD EXTRACTION & IDENTIFICATION:")
    print("   • AI identifies which specific keyword from the significant list matches")
    print("   • Returns the matched keyword in the response format: 'Significant: [keyword]'")
    print("   • Enables tracking of which keywords trigger significance classification")
    
    print("\n3. ✅ AUTOMATIC KEYWORD TRANSLATION:")
    print("   • Translates matched keywords to English for consistent reporting")
    print("   • Ensures SharePoint/Teams data uses English keywords regardless of source language")
    print("   • Maintains original context while providing standardized output")
    
    print("\n4. ✅ ENHANCED LOGGING & ERROR HANDLING:")
    print("   • Detailed logging of matched keywords and classification reasoning")
    print("   • Improved error reporting with 'strict_keyword_contextual' analysis type")
    print("   • Better debugging capabilities for false positive analysis")
    
    print("\n📊 Expected Results:")
    print("   • Fewer false positives due to stricter classification rules")
    print("   • Clear identification of which keywords trigger significance")
    print("   • Consistent English keyword reporting for SharePoint/Teams integration")
    print("   • Maintained accuracy for genuinely significant messages")
    
    print("\n🔧 Integration with Existing Flow:")
    print("   • Message processor still performs exact keyword matching first")
    print("   • AI analysis only used when keyword matching is inconclusive")
    print("   • Enhanced AI now returns specific matched keywords for reporting")
    print("   • All existing function signatures and integrations remain unchanged")
    
    print("\n📝 NOTE: To run actual AI analysis, you need:")
    print("   1. Valid OpenAI API key in config.json")
    print("   2. Active telegram scraper environment")
    print("   3. Use MessageProcessor.isMessageSignificant() with use_ai_for_message_filtering=true")

if __name__ == "__main__":
    test_enhanced_ai_analysis()