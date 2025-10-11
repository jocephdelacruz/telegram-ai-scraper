#!/usr/bin/env python3
"""
Quick test to verify MessageProcessor language detection works without OpenAI
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core.message_processor import MessageProcessor

def test_language_detection():
    """Test language detection without OpenAI processor"""
    processor = MessageProcessor()  # No OpenAI processor provided
    
    test_cases = [
        ("protest in Baghdad today", "english"),
        ("احتجاج في بغداد اليوم", "arabic"),
        ("urgent news from Iraq", "english"),
        ("أخبار عاجلة من العراق", "arabic"),
        ("sports update", "english"),
        ("رياضة اليوم", "arabic"),
        ("Hello world", "english"),
        ("مرحبا", "arabic"),
        ("123 numbers only", "english"),  # Should default to english with latin chars
        ("مختلط mixed text العربي", "arabic"),  # Mixed should detect arabic due to arabic script
    ]
    
    print("🧪 Testing Language Detection (No OpenAI)")
    print("=" * 50)
    
    for text, expected in test_cases:
        detected = processor.detectLanguage(text)
        status = "✅" if detected == expected else "❌"
        print(f"{status} '{text}' -> Detected: {detected}, Expected: {expected}")
    
    print("\n🧪 Testing Message Processing Without OpenAI")
    print("=" * 50)
    
    # Test with Iraq config but no OpenAI processor
    iraq_config = {
        "name": "Iraq",
        "message_filtering": {
            "use_ai_for_message_filtering": False,  # Disable AI
            "significant_keywords": [
                ["protest", "احتجاج"],
                ["urgent", "عاجل"],
                ["demonstration", "مظاهرة"]
            ],
            "trivial_keywords": [
                ["sports", "رياضة"],
                ["entertainment", "ترفيه"]
            ],
            "exclude_keywords": [
                ["advertisement", "إعلان"],
                ["sale", "تخفيضات"]
            ]
        }
    }
    
    test_messages = [
        "احتجاج في بغداد",  # Arabic significant
        "protest in Baghdad",  # English significant
        "رياضة اليوم",  # Arabic trivial
        "sports news today",  # English trivial
        "إعلان مهم",  # Arabic exclude
        "advertisement here",  # English exclude
        "random message about weather"  # No match, should be trivial since AI disabled
    ]
    
    for message in test_messages:
        is_significant, keywords, method, translation_info = processor.isMessageSignificant(
            message, country_config=iraq_config
        )
        
        detected_lang = translation_info['original_language']
        print(f"Message: '{message}' ({detected_lang})")
        print(f"  -> {'Significant' if is_significant else 'Trivial'} ({method})")
        print(f"  -> Keywords: {keywords}")
        print()

if __name__ == "__main__":
    test_language_detection()