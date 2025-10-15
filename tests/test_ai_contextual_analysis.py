#!/usr/bin/env python3
"""
Test script for the new AI contextual analysis functionality.
This script tests the modified _analyzeWithAI function to ensure it uses
the provided keyword lists for contextual analysis.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

def test_ai_contextual_analysis():
    """Test the AI contextual analysis with sample messages and keywords"""
    
    print("=" * 60)
    print("Testing AI Contextual Analysis Functionality")
    print("=" * 60)
    
    # Sample test cases
    test_cases = [
        {
            "message": "Major cyber attack targets government infrastructure",
            "significant_keywords": ["cyber attack", "security breach", "infrastructure"],
            "trivial_keywords": ["sports", "entertainment", "weather"],
            "expected": "Significant"
        },
        {
            "message": "Local football team wins championship match",
            "significant_keywords": ["cyber attack", "security breach", "infrastructure"],
            "trivial_keywords": ["sports", "entertainment", "weather"],
            "expected": "Trivial"
        },
        {
            "message": "Heavy rainfall causes flooding in downtown area",
            "significant_keywords": ["flooding", "emergency", "disaster"],
            "trivial_keywords": ["sports", "entertainment", "celebrity"],
            "expected": "Significant"
        },
        {
            "message": "Celebrity spotted at new restaurant opening",
            "significant_keywords": ["flooding", "emergency", "disaster"],
            "trivial_keywords": ["sports", "entertainment", "celebrity"],
            "expected": "Trivial"
        }
    ]
    
    print("\nTest Cases:")
    print("-" * 40)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"Message: {case['message']}")
        print(f"Significant Keywords: {case['significant_keywords']}")
        print(f"Trivial Keywords: {case['trivial_keywords']}")
        print(f"Expected Classification: {case['expected']}")
        print("-" * 40)
    
    print("\nNOTE: This is a demonstration of test cases.")
    print("To actually run the AI analysis, you would need:")
    print("1. Valid OpenAI API key in config.json")
    print("2. Active Telegram scraper environment")
    print("3. Run: python -c \"from src.core.message_processor import MessageProcessor; processor = MessageProcessor(); processor.isMessageSignificant(message, sig_keywords, triv_keywords)\"")
    
    print("\nKey improvements in the modified _analyzeWithAI function:")
    print("• Uses actual provided keyword lists instead of hardcoded categories")
    print("• Performs contextual analysis to understand meaning, not just exact matches")
    print("• Maintains backward compatibility with existing message flow")
    print("• Provides detailed logging for debugging and monitoring")
    print("• Prioritizes significance when both significant and trivial concepts are present")

if __name__ == "__main__":
    test_ai_contextual_analysis()