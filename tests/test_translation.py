#!/usr/bin/env python3
"""
Test script for translation functionality in OpenAI utils
"""
import sys
import os
import json

# Add the project path
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from src.integrations.openai_utils import OpenAIProcessor

def test_translation():
    """Test the translation functionality"""
    
    # Load config to get OpenAI key
    try:
        with open('config/config.json', 'r') as f:
            config = json.load(f)
        
        openai_key = config.get('OPEN_AI_KEY', '')
        if not openai_key:
            print("❌ OpenAI API key not found in config")
            return
            
        processor = OpenAIProcessor(openai_key)
        
        # Test cases
        test_messages = [
            {
                'text': 'Breaking news: Major earthquake hits the region',
                'expected_english': True,
                'description': 'English text'
            },
            {
                'text': 'أخبار عاجلة: زلزال كبير يضرب المنطقة',
                'expected_english': False,
                'description': 'Arabic text (earthquake news)'
            },
            {
                'text': 'Hello, how are you today?',
                'expected_english': True,
                'description': 'Simple English text'
            },
            {
                'text': 'Bonjour, comment allez-vous?',
                'expected_english': False,
                'description': 'French text'
            }
        ]
        
        print("🧪 Testing Translation Functionality\n")
        
        for i, test in enumerate(test_messages, 1):
            print(f"Test {i}: {test['description']}")
            print(f"Original: {test['text']}")
            
            try:
                is_english, translated_text, detected_language = processor.detectLanguageAndTranslate(test['text'])
                
                print(f"Detected Language: {detected_language}")
                print(f"Is English: {is_english}")
                print(f"Translated: {translated_text}")
                
                # Test significance analysis with translation
                is_significant, keywords, method, translation_info = processor.isMessageSignificant(test['text'])
                
                print(f"Significance: {'Significant' if is_significant else 'Trivial'}")
                print(f"Method: {method}")
                print(f"Translation Info: {translation_info}")
                
                print("✅ Test completed successfully")
                
            except Exception as e:
                print(f"❌ Test failed: {e}")
            
            print("-" * 60)
            
    except Exception as e:
        print(f"❌ Failed to run tests: {e}")

if __name__ == "__main__":
    test_translation()