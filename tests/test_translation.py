#!/usr/bin/env python3
"""
Test script for translation functionality using new translation architecture
Tests both OpenAI and Google Translate methods, as well as configuration options
"""
import sys
import os
import json

# Add the project path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.integrations.openai_utils import OpenAIProcessor
from src.integrations.translation_utils import TranslationProcessor
from src.core.message_processor import MessageProcessor

def test_translation_utils():
    """Test the new TranslationProcessor functionality"""
    
    # Load config to get OpenAI key
    try:
        with open('config/config.json', 'r') as f:
            config = json.load(f)
        
        openai_key = config.get('OPEN_AI_KEY', '')
        if not openai_key:
            print("❌ OpenAI API key not found in config")
            return
            
        openai_processor = OpenAIProcessor(openai_key)
        translation_processor = TranslationProcessor(openai_processor=openai_processor)
        
        # Test messages for translation functionality
        test_messages = [
            {
                'text': 'Hello, how are you today?',
                'expected_english': True,
                'description': 'Simple English text - should not be translated'
            },
            {
                'text': 'أخبار عاجلة: زلزال كبير يضرب المنطقة',
                'expected_english': False,
                'description': 'Arabic text (earthquake news) - should be translated'
            },
            {
                'text': 'احتجاج في بغداد',
                'expected_english': False,
                'description': 'Arabic text (protest in Baghdad) - should be translated'
            },
            {
                'text': 'Bonjour, comment allez-vous?',
                'expected_english': False,
                'description': 'French text - should be translated'
            },
            {
                'text': 'Breaking news from Iraq',
                'expected_english': True,
                'description': 'English breaking news - should not be translated'
            }
        ]
        
        print("🧪 Testing New Translation Architecture\n")
        print("=" * 80)
        
        # Test 1: Google Translate method
        print("TEST 1: Google Translate Translation Method")
        print("-" * 50)
        
        for i, test in enumerate(test_messages, 1):
            print(f"\nTest 1.{i}: {test['description']}")
            print(f"Original: {test['text']}")
            try:
                result = translation_processor.translate(text=test['text'], use_ai=False)
                print(f"Success: {result['success']}")
                print(f"Detected Language: {result['detected_language']}")
                print(f"Was Translated: {result['was_translated']}")
                print(f"Translation Method: {result['translation_method']}")
                print(f"Translated Text: {result['translated_text']}")
                print("✅ Google Translate test completed")
            except Exception as e:
                print(f"❌ Google Translate test failed: {e}")
        
        print("\n" + "=" * 80)
        
        # Test 2: OpenAI translation method
        print("TEST 2: OpenAI Translation Method")
        print("-" * 50)
        
        for i, test in enumerate(test_messages, 1):
            print(f"\nTest 2.{i}: {test['description']}")
            print(f"Original: {test['text']}")
            try:
                result = translation_processor.translate(text=test['text'], use_ai=True)
                print(f"Success: {result['success']}")
                print(f"Detected Language: {result['detected_language']}")
                print(f"Was Translated: {result['was_translated']}")
                print(f"Translation Method: {result['translation_method']}")
                print(f"Translated Text: {result['translated_text']}")
                print("✅ OpenAI translation test completed")
            except Exception as e:
                print(f"❌ OpenAI translation test failed: {e}")
        
        print("\n" + "=" * 80)
        # Test 3: MessageProcessor integration with new translation settings
        print("TEST 3: MessageProcessor Translation Integration")
        print("-" * 50)
        
        iraq_config = config.get('COUNTRIES', {}).get('iraq', {})
        message_processor = MessageProcessor(openai_processor=openai_processor)
        
        # Test with different translation configurations
        test_configs = [
            {
                'name': 'Google Translate for all messages',
                'config': {
                    'message_filtering': {
                        'use_ai_for_translation': False,
                        'translate_trivial_msgs': True,
                        'use_ai_for_message_filtering': False
                    }
                }
            },
            {
                'name': 'OpenAI for all messages',
                'config': {
                    'message_filtering': {
                        'use_ai_for_translation': True,
                        'translate_trivial_msgs': True,
                        'use_ai_for_message_filtering': False
                    }
                }
            },
            {
                'name': 'Skip trivial message translation',
                'config': {
                    'message_filtering': {
                        'use_ai_for_translation': False,
                        'translate_trivial_msgs': False,
                        'use_ai_for_message_filtering': False
                    }
                }
            }
        ]
        
        test_message = "احتجاج في بغداد اليوم"  # Arabic: "Protest in Baghdad today"
        
        for config_test in test_configs:
            print(f"\nTesting: {config_test['name']}")
            print(f"Message: {test_message}")
            try:
                # Test significance analysis first
                is_significant, keywords, method, lang_info = message_processor.isMessageSignificant(
                    test_message, country_config=config_test['config'])
                print(f"Significance: {'Significant' if is_significant else 'Trivial'} ({method})")
                
                # Test translation
                translation_result = message_processor.translateMessage(
                    test_message, country_config=config_test['config'])
                print(f"Translation Success: {translation_result['success']}")
                print(f"Was Translated: {translation_result['was_translated']}")
                print(f"Translation Method: {translation_result['translation_method']}")
                print(f"Translated Text: {translation_result['translated_text']}")
                print("✅ MessageProcessor integration test completed")
            except Exception as e:
                print(f"❌ MessageProcessor integration test failed: {e}")
        
        print("\n" + "=" * 80)
        
        # Test 4: Backward compatibility with OpenAI utils
        print("TEST 4: Backward Compatibility with OpenAI Utils")
        print("-" * 50)
        
        print("\nTesting OpenAI detectLanguageAndTranslate method:")
        test_text = "أخبار عاجلة من العراق"
        try:
            is_english, translated_text, detected_lang = openai_processor.detectLanguageAndTranslate(test_text)
            print(f"Original: {test_text}")
            print(f"Detected Language: {detected_lang}")
            print(f"Is English: {is_english}")
            print(f"Translated: {translated_text}")
            print("✅ Backward compatibility test completed")
        except Exception as e:
            print(f"❌ Backward compatibility test failed: {e}")
            
    except Exception as e:
        print(f"❌ Failed to run tests: {e}")


def test_translation():
    """Legacy test function name for backward compatibility"""
    test_translation_utils()


if __name__ == "__main__":
    test_translation_utils()