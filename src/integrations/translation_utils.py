import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core import log_handling as lh
from googletrans import Translator
import time
import re


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "translation.log")
LOG_TZ = "Asia/Manila"
LOGGER = lh.LogHandling(LOG_FILE, LOG_TZ)


class TranslationProcessor:
    """
    Handles message translation using multiple backends:
    - Google Translate (via googletrans library) - free but rate limited
    - OpenAI translation (via OpenAIProcessor) - paid but more reliable
    """
    
    def __init__(self, openai_processor=None):
        self.openai_processor = openai_processor
        self.google_translator = None
        self._google_error_count = 0
        self._initialize_google_translator()
    
    
    def _initialize_google_translator(self):
        """Initialize Google Translator with error handling"""
        try:
            self.google_translator = Translator()
            LOGGER.writeLog('TranslationProcessor: Google Translator initialized successfully')
        except Exception as e:
            LOGGER.writeLog(f'TranslationProcessor: Failed to initialize Google Translator: {e}')
            self.google_translator = None
    
    
    def detectLanguage(self, text):
        """
        Detect the language of the text using MessageProcessor's language detection.
        Returns the detected language: 'english', 'arabic', or 'unknown'
        
        This method delegates to MessageProcessor for consistent language detection across the system.
        """
        try:
            # Import MessageProcessor for language detection
            from src.core.message_processor import MessageProcessor
            processor = MessageProcessor()
            return processor.detectLanguage(text)
        except Exception as e:
            LOGGER.writeLog(f'TranslationProcessor: detectLanguage - Exception: {e}')
            return 'unknown'
    
    
    def translateWithGoogle(self, text, target_lang='en', source_lang=None):
        """
        Translate text using Google Translate (free but rate limited)
        
        Args:
            text (str): Text to translate
            target_lang (str): Target language code (default: 'en' for English)
            source_lang (str): Source language if already known (optional)
            
        Returns:
            tuple: (success, translated_text, detected_language)
        """
        try:
            if not self.google_translator:
                self._initialize_google_translator()
                if not self.google_translator:
                    return False, text, 'unknown'
            
            # Add small delay to avoid rate limiting
            time.sleep(0.1)
            
            # Use provided source language or detect it
            if source_lang:
                detected_lang = source_lang
                LOGGER.writeLog(f'TranslationProcessor: Using provided source language: {source_lang}')
            else:
                # Detect language only if not provided
                detection = self.google_translator.detect(text)
                detected_lang = detection.lang if detection else 'unknown'
                LOGGER.writeLog(f'TranslationProcessor: Detected language: {detected_lang}')
            
            # Skip translation if already in target language
            if detected_lang == target_lang or (detected_lang == 'en' and target_lang == 'en'):
                LOGGER.writeLog(f'TranslationProcessor: Text already in target language ({target_lang})')
                return True, text, detected_lang
            
            # Perform translation
            result = self.google_translator.translate(text, dest=target_lang)
            translated_text = result.text if result else text
            
            LOGGER.writeLog(f'TranslationProcessor: Google translation successful - {detected_lang} -> {target_lang}')
            
            # Reset error count on success
            self._google_error_count = 0
            
            return True, translated_text, detected_lang
            
        except Exception as e:
            LOGGER.writeLog(f'TranslationProcessor: Google translation failed: {e}')
            self._google_error_count += 1
            
            # Send critical exception to admin for frequent Google Translate failures
            if self._google_error_count % 20 == 0:  # Every 20th error
                try:
                    from .teams_utils import send_critical_exception
                    send_critical_exception(
                        "GoogleTranslationError",
                        str(e),
                        "TranslationProcessor.translateWithGoogle",
                        additional_context={
                            "error_count": self._google_error_count,
                            "text_length": len(text) if text else 0,
                            "target_language": target_lang
                        }
                    )
                except Exception as admin_error:
                    LOGGER.writeLog(f"Failed to send Google translation error to admin: {admin_error}")
            
            return False, text, 'unknown'
    
    
    def translateWithOpenAI(self, text, target_lang='English', source_lang=None):
        """
        Translate text using OpenAI (paid but more reliable)
        
        Args:
            text (str): Text to translate
            target_lang (str): Target language name (default: 'English')
            source_lang (str): Source language if already known (optional)
            
        Returns:
            tuple: (success, translated_text, detected_language)
        """
        try:
            if not self.openai_processor:
                LOGGER.writeLog('TranslationProcessor: No OpenAI processor available for translation')
                return False, text, 'unknown'
            
            # Use source language if provided, otherwise use full detection
            if source_lang and source_lang.lower() not in ['unknown', 'english']:
                # Use translation-only method for efficiency
                success, translated_text = self.openai_processor.translateToEnglish(text, source_lang)
                detected_lang = source_lang
                
                if success and translated_text != text:
                    LOGGER.writeLog(f'TranslationProcessor: OpenAI translation-only successful - {source_lang} -> {target_lang}')
                    return True, translated_text, detected_lang
                elif success:
                    LOGGER.writeLog(f'TranslationProcessor: OpenAI detected text is already in {target_lang}')
                    return True, text, detected_lang
                else:
                    LOGGER.writeLog(f'TranslationProcessor: OpenAI translation-only failed, falling back to full detection')
                    # Fall through to full detection method
            
            # Use OpenAI's detectLanguageAndTranslate method as fallback or primary
            is_english, translated_text, detected_lang = self.openai_processor.detectLanguageAndTranslate(text)
            
            if translated_text and translated_text != text:
                LOGGER.writeLog(f'TranslationProcessor: OpenAI full detection+translation successful - {detected_lang} -> {target_lang}')
                return True, translated_text, detected_lang
            else:
                LOGGER.writeLog(f'TranslationProcessor: OpenAI detected text is already in {target_lang}')
                return True, text, detected_lang
                
        except Exception as e:
            LOGGER.writeLog(f'TranslationProcessor: OpenAI translation failed: {e}')
            
            # Send critical exception to admin for OpenAI translation failures
            try:
                from .teams_utils import send_critical_exception
                send_critical_exception(
                    "OpenAITranslationError",
                    str(e),
                    "TranslationProcessor.translateWithOpenAI",
                    additional_context={
                        "text_length": len(text) if text else 0,
                        "target_language": target_lang
                    }
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send OpenAI translation error to admin: {admin_error}")
            
            return False, text, 'unknown'
    
    
    def translate(self, text, use_ai=False, target_lang='en', source_language=None):
        """
        Main translation method that chooses between Google Translate and OpenAI
        
        Args:
            text (str): Text to translate
            use_ai (bool): If True, use OpenAI; if False, use Google Translate
            target_lang (str): Target language ('en' for Google, 'English' for OpenAI)
            source_language (str): Source language if already known (avoids redundant detection)
            
        Returns:
            dict: Translation result with success status, translated text, and metadata
        """
        try:
            # Use provided source language or detect it
            if source_language:
                detected_lang = source_language.lower()
                LOGGER.writeLog(f'TranslationProcessor: Using provided source language: {source_language}')
            else:
                # Quick check if text is already in English (only if source not provided)
                detected_lang = self.detectLanguage(text)
                LOGGER.writeLog(f'TranslationProcessor: Detected language: {detected_lang}')
            
            # Skip translation if already in English
            if detected_lang == 'english':
                LOGGER.writeLog('TranslationProcessor: Text is English, skipping translation')
                return {
                    'success': True,
                    'translated_text': text,
                    'original_text': text,
                    'detected_language': 'English',
                    'was_translated': False,
                    'translation_method': 'none_required'
                }
            
            # Map language codes for Google Translate
            google_lang_code = 'ar' if detected_lang == 'arabic' else 'auto'
            
            # Choose translation method
            if use_ai:
                success, translated_text, detected_language = self.translateWithOpenAI(text, 'English', source_language)
                method = 'openai'
            else:
                success, translated_text, detected_language = self.translateWithGoogle(text, 'en', google_lang_code if google_lang_code != 'auto' else None)
                method = 'google'
            
            # Fallback to the other method if primary fails
            if not success and use_ai:
                LOGGER.writeLog('TranslationProcessor: OpenAI failed, falling back to Google Translate')
                success, translated_text, detected_language = self.translateWithGoogle(text, 'en')
                method = 'google_fallback'
            elif not success and not use_ai:
                LOGGER.writeLog('TranslationProcessor: Google Translate failed, falling back to OpenAI')
                success, translated_text, detected_language = self.translateWithOpenAI(text, 'English', source_language)
                method = 'openai_fallback'
            
            return {
                'success': success,
                'translated_text': translated_text if success else text,
                'original_text': text,
                'detected_language': detected_language.title() if detected_language else 'Unknown',
                'was_translated': success and translated_text != text,
                'translation_method': method
            }
            
        except Exception as e:
            LOGGER.writeLog(f'TranslationProcessor: translate - Exception: {e}')
            
            # Send critical exception to admin for translation failures
            try:
                from .teams_utils import send_critical_exception
                send_critical_exception(
                    "TranslationProcessorError",
                    str(e),
                    "TranslationProcessor.translate",
                    additional_context={
                        "text_length": len(text) if text else 0,
                        "use_ai": use_ai,
                        "target_language": target_lang
                    }
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send translation processor error to admin: {admin_error}")
            
            return {
                'success': False,
                'translated_text': text,
                'original_text': text,
                'detected_language': 'Unknown',
                'was_translated': False,
                'translation_method': 'error'
            }