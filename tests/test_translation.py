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
        
        # Test cases (including Iraq dual-language and AI toggle)
        iraq_config = config.get('COUNTRIES', {}).get('iraq', {})
        test_messages = [
            {
                'text': 'protest in Baghdad',
                'expected_english': True,
                'description': 'Iraq English significant keyword',
                'country_config': iraq_config
            },
            {
                'text': 'احتجاج في بغداد',
                'expected_english': False,
                'description': 'Iraq Arabic significant keyword',
                'country_config': iraq_config
            },
            {
                'text': 'This is a sports update',
                'expected_english': True,
                'description': 'Iraq English trivial keyword',
                'country_config': iraq_config
            },
            {
                'text': 'رياضة اليوم',
                'expected_english': False,
                'description': 'Iraq Arabic trivial keyword',
                'country_config': iraq_config
            },
            {
                'text': 'advertisement: buy now!',
                'expected_english': True,
                'description': 'Iraq English exclude keyword',
                'country_config': iraq_config
            },
            {
                'text': 'إعلان هام',
                'expected_english': False,
                'description': 'Iraq Arabic exclude keyword',
                'country_config': iraq_config
            },
            {
                'text': 'Breaking news: Major earthquake hits the region',
                'expected_english': True,
                'description': 'English text',
                'country_config': None
            },
            {
                'text': 'أخبار عاجلة: زلزال كبير يضرب المنطقة',
                'expected_english': False,
                'description': 'Arabic text (earthquake news)',
                'country_config': None
            },
            {
                'text': 'Hello, how are you today?',
                'expected_english': True,
                'description': 'Simple English text',
                'country_config': None
            },
            {
                'text': 'Bonjour, comment allez-vous?',
                'expected_english': False,
                'description': 'French text',
                'country_config': None
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
                # Test significance analysis with translation and country config
                is_significant, keywords, method, translation_info = processor.isMessageSignificant(
                    test['text'], country_config=test.get('country_config'))
                print(f"Significance: {'Significant' if is_significant else 'Trivial'}")
                print(f"Method: {method}")
                print(f"Translation Info: {translation_info}")
                print("✅ Test completed successfully")
            except Exception as e:
                print(f"❌ Test failed: {e}")
            print("-" * 60)
        # Test AI filtering toggle for Iraq
        if iraq_config:
            print("\nTesting AI filtering toggle for Iraq...")
            iraq_config_ai_off = dict(iraq_config)
            iraq_config_ai_off['message_filtering'] = dict(iraq_config_ai_off['message_filtering'])
            iraq_config_ai_off['message_filtering']['use_ai_for_message_filtering'] = False
            ambiguous_text = "This message does not match any keyword but is about a protest in the city."
            is_significant, keywords, method, translation_info = processor.isMessageSignificant(
                ambiguous_text, country_config=iraq_config_ai_off)
            print(f"AI Filtering OFF: Significance: {'Significant' if is_significant else 'Trivial'}, Method: {method}")
            iraq_config_ai_on = dict(iraq_config)
            iraq_config_ai_on['message_filtering'] = dict(iraq_config_ai_on['message_filtering'])
            iraq_config_ai_on['message_filtering']['use_ai_for_message_filtering'] = True
            is_significant, keywords, method, translation_info = processor.isMessageSignificant(
                ambiguous_text, country_config=iraq_config_ai_on)
            print(f"AI Filtering ON: Significance: {'Significant' if is_significant else 'Trivial'}, Method: {method}")
            print("-" * 60)
            
    except Exception as e:
        print(f"❌ Failed to run tests: {e}")

if __name__ == "__main__":
    test_translation()