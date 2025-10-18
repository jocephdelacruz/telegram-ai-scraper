import sys
import os
import re
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core import log_handling as lh
from src.integrations.openai_utils import OpenAIProcessor
from src.integrations.translation_utils import TranslationProcessor


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "telegram_tasks.log")
LOG_TZ = "Asia/Manila"
LOGGER = lh.LogHandling(LOG_FILE, LOG_TZ)


class MessageProcessor:
    """
    Handles message processing logic without direct OpenAI calls.
    This class focuses on language detection and keyword matching,
    delegating AI-based analysis to OpenAIProcessor when needed.
    """
    
    def __init__(self, openai_processor=None):
        self.openai_processor = openai_processor
        self.translation_processor = TranslationProcessor(openai_processor=openai_processor)
    

    def detectLanguage(self, text):
        """
        Detect the language of the text using enhanced heuristic analysis.
        Returns the detected language: 'english', 'arabic', or 'unknown'
        
        Enhanced to better detect Arabic text even when mixed with English URLs/text.
        Prioritizes Arabic when substantial Arabic characters are present.
        """
        try:
            # Common English words that appear frequently
            common_english_words = [
                'the', 'and', 'is', 'in', 'to', 'of', 'a', 'for', 'with', 'on', 'at', 'by',
                'this', 'that', 'from', 'they', 'we', 'be', 'have', 'an', 'as', 'are', 'was',
                'but', 'not', 'or', 'had', 'will', 'would', 'there', 'been', 'their', 'were',
                'which', 'all', 'if', 'more', 'when', 'who', 'what', 'so', 'no', 'out', 'up',
                'he', 'she', 'it', 'my', 'your', 'his', 'her', 'its', 'our', 'us', 'them',
                'those', 'these', 'about', 'now', 'time', 'can', 'said', 'each', 'get', 'has',
                'him', 'old', 'see', 'two', 'way', 'may', 'come', 'could', 'work', 'first',
                'after', 'back', 'other', 'many', 'than', 'then', 'new', 'some', 'take', 'day'
            ]
            
            # Expanded Arabic words and particles for better detection
            common_arabic_words = [
                # Original common words
                'في', 'من', 'إلى', 'على', 'عن', 'مع', 'كل', 'هذا', 'هذه', 'ذلك', 'تلك',
                'التي', 'الذي', 'لكن', 'أو', 'أم', 'إذا', 'عند', 'بعد', 'قبل',
                'حول', 'ضد', 'تحت', 'فوق', 'أمام', 'خلف', 'جانب', 'داخل', 'خارج', 'بين',
                'أثناء', 'خلال', 'عبر', 'حتى', 'منذ', 'لدى', 'لديه', 'لديها', 'معه', 'معها',
                'له', 'لها', 'لهم', 'لهن', 'منه', 'منها', 'منهم', 'منهن', 'إليه', 'إليها',
                'عليه', 'عليها', 'عنه', 'عنها', 'فيه', 'فيها', 'به', 'بها', 'كما', 'إن',
                'أن', 'كان', 'كانت', 'يكون', 'تكون', 'سوف', 'قد', 'لقد', 'قام', 'قامت',
                'يقول', 'تقول', 'قال', 'قالت', 'أقول', 'نقول', 'أعلن', 'أعلنت', 'يعلن',
                'الآن', 'اليوم', 'أمس', 'غدا', 'هنا', 'هناك', 'هنالك', 'حيث', 'أين', 'متى',
                'كيف', 'ماذا', 'لماذا', 'من', 'أي', 'كم', 'عاجل', 'أخبار', 'جديد', 'مهم',
                # Additional common Arabic words for better detection
                'الجامعة', 'بارزاني', 'السليمانية', 'نموذج', 'التعليم', 'الحر', 'بالعراق',
                'الأميركية', 'رسخت', 'نيجيرفان', 'العراق', 'العربية', 'الدولة', 'الحكومة',
                'الرئيس', 'الوزير', 'المجلس', 'البرلمان', 'الشعب', 'المواطن', 'البلد',
                'المدينة', 'القرية', 'الشارع', 'البيت', 'المكتب', 'المدرسة', 'المستشفى',
                'الشركة', 'المصنع', 'السوق', 'المتجر', 'المطعم', 'الفندق', 'المطار',
                'الطريق', 'الجسر', 'النهر', 'البحر', 'الجبل', 'الصحراء', 'الغابة'
            ]
            
            # Convert to lowercase for comparison and split into words
            text_lower = text.lower()
            words = text_lower.split()
            
            if len(words) < 2:
                # For very short messages, check character types
                has_arabic_chars = any('\u0600' <= char <= '\u06FF' for char in text)
                has_latin_chars = any('a' <= char.lower() <= 'z' for char in text)
                
                if has_arabic_chars:
                    return 'arabic'
                elif has_latin_chars and not has_arabic_chars:
                    return 'english'
                else:
                    return 'unknown'
            
            # Count matches for each language
            english_matches = sum(1 for word in words if any(eng_word in word for eng_word in common_english_words))
            arabic_matches = sum(1 for word in words if word in common_arabic_words)
            
            # Calculate ratios
            total_words = len(words)
            english_ratio = english_matches / total_words
            arabic_ratio = arabic_matches / total_words
            
            # Check for script characteristics
            has_arabic_script = any('\u0600' <= char <= '\u06FF' for char in text)
            has_latin_script = any('a' <= char.lower() <= 'z' for char in text)
            
            # Enhanced Arabic character analysis
            total_chars = len(text.replace(' ', '').replace('\n', ''))  # Count non-whitespace characters
            arabic_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF')  # Count Arabic characters
            arabic_char_ratio = arabic_chars / total_chars if total_chars > 0 else 0
            
            # Filter out URLs and technical text for cleaner analysis
            text_without_urls = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
            text_without_urls = re.sub(r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', text_without_urls)  # Remove domain-like patterns
            content_words = [word for word in text_without_urls.lower().split() if len(word) > 2 and not re.match(r'^[a-z0-9.:/-]+$', word)]
            
            LOGGER.writeLog(f'MessageProcessor: Language detection - English ratio: {english_ratio:.2f}, Arabic ratio: {arabic_ratio:.2f}, Arabic char ratio: {arabic_char_ratio:.2f}, Arabic script: {has_arabic_script}, Latin script: {has_latin_script}')
            
            # Enhanced decision logic prioritizing Arabic content
            # Priority 1: High Arabic character content (substantial Arabic text)
            if arabic_char_ratio > 0.3:  # More than 30% Arabic characters
                LOGGER.writeLog(f'MessageProcessor: High Arabic character ratio ({arabic_char_ratio:.2f}) - classifying as Arabic')
                return 'arabic'
            
            # Priority 2: Pure script types
            if has_arabic_script and not has_latin_script:
                return 'arabic'
            elif has_latin_script and not has_arabic_script:
                return 'english'
            
            # Priority 3: Mixed content with word-based analysis
            if has_arabic_script and has_latin_script:
                # For mixed content, check if Arabic words are substantial
                if arabic_char_ratio > 0.15 and (arabic_ratio > 0.05 or arabic_matches > 0):
                    LOGGER.writeLog(f'MessageProcessor: Mixed content with substantial Arabic ({arabic_char_ratio:.2f} chars, {arabic_ratio:.2f} words) - classifying as Arabic')
                    return 'arabic'
                elif english_ratio > 0.2:
                    return 'english'
            
            # Priority 4: Word ratio comparison with Arabic preference
            if arabic_ratio > 0 and arabic_ratio >= english_ratio:
                return 'arabic'
            elif english_ratio > arabic_ratio:
                return 'english'
            
            # Fallback: Check for any Arabic content
            if has_arabic_script:
                return 'arabic'
            elif has_latin_script:
                return 'english'
            else:
                return 'unknown'
                
        except Exception as e:
            LOGGER.writeLog(f'MessageProcessor: detectLanguage - Exception: {e}')
            
            # Send critical exception to admin if language detection fails frequently
            if not hasattr(self, '_language_detection_errors'):
                self._language_detection_errors = 1
            else:
                self._language_detection_errors += 1
                
            if self._language_detection_errors % 50 == 0:  # Every 50 errors
                try:
                    from src.integrations.teams_utils import send_critical_exception
                    send_critical_exception(
                        "LanguageDetectionError",
                        str(e),
                        "MessageProcessor.detectLanguage",
                        additional_context={
                            "total_errors": self._language_detection_errors,
                            "text_length": len(text) if text else 0
                        }
                    )
                except Exception as admin_error:
                    LOGGER.writeLog(f"Failed to send language detection error to admin: {admin_error}")
            
            return 'unknown'
    

    def _isLikelyEnglish(self, text):
        """
        Legacy method for backward compatibility.
        Use detectLanguage() for more accurate language detection.
        """
        return self.detectLanguage(text) == 'english'
    

    def _matchesWholeWord(self, keyword, text):
        """
        Helper function for whole-word keyword matching to prevent false positives.
        """
        if not keyword:
            return False
        # Use word boundaries to match whole words only
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        return bool(re.search(pattern, text.lower()))
    

    def isMessageSignificant(self, message, significant_keywords=None, trivial_keywords=None, exclude_keywords=None, country_config=None):
        """
        Determine if a message is significant using dual-language keyword matching
        and optional AI analysis fallback.
        
        This method prioritizes keyword matching over AI analysis for cost optimization
        and performance improvement, especially for countries with dual-language support.
        """
        try:
            # Detect language without translation
            detected_language = self.detectLanguage(message)
            LOGGER.writeLog(f'MessageProcessor: Language detected: {detected_language}')
            
            # Initialize translation info (no translation performed at this stage)
            translation_info = {
                'is_english': detected_language == 'english',
                'original_language': detected_language.title()
            }
            
            # Use country-specific keywords if provided
            use_ai = True
            if country_config and 'message_filtering' in country_config:
                filtering = country_config['message_filtering']
                significant_keywords = filtering.get('significant_keywords', significant_keywords or [])
                trivial_keywords = filtering.get('trivial_keywords', trivial_keywords or [])
                exclude_keywords = filtering.get('exclude_keywords', exclude_keywords or [])
                use_ai = filtering.get('use_ai_for_message_filtering', True)
            
            # Set defaults if still None
            if significant_keywords is None:
                significant_keywords = [["breaking news", "أخبار عاجلة"], ["alert", "تنبيه"], ["urgent", "عاجل"], ["emergency", "طارئ"], ["crisis", "أزمة"]]
            if trivial_keywords is None:
                trivial_keywords = [["weather", "طقس"], ["sports", "رياضة"], ["entertainment", "ترفيه"], ["celebrity", "مشاهير"]]
            if exclude_keywords is None:
                exclude_keywords = [["advertisement", "إعلان"], ["promo", "ترويج"], ["discount", "خصم"], ["sale", "تخفيضات"]]
            
            # Determine which language index to use for keyword matching
            lang_idx = 0 if detected_language == 'english' else 1
            analysis_text = message  # Always use original message for direct keyword matching
            
            # Extract keywords for the detected language
            def get_keywords(keyword_list):
                keywords = []
                for kw in keyword_list:
                    if isinstance(kw, list) and len(kw) > lang_idx:
                        keywords.append(kw[lang_idx])
                    elif isinstance(kw, str):
                        # Handle legacy single-language keywords
                        keywords.append(kw)
                return keywords
            
            # Helper function to get English equivalent of matched keyword
            def get_english_keyword(matched_keyword, keyword_list):
                """Find the English equivalent of a matched keyword from the original keyword pairs"""
                for kw in keyword_list:
                    if isinstance(kw, list):
                        # Check if the matched keyword is in any position of the pair
                        if matched_keyword in kw:
                            # Always return the English version (index 0)
                            return kw[0] if len(kw) > 0 else matched_keyword
                    elif isinstance(kw, str) and kw == matched_keyword:
                        # Single string keyword - assume it's already in English
                        return matched_keyword
                return matched_keyword  # Fallback to original if not found
            
            sig_keywords = get_keywords(significant_keywords)
            triv_keywords = get_keywords(trivial_keywords)
            excl_keywords = get_keywords(exclude_keywords)
            
            LOGGER.writeLog(f'MessageProcessor: Using {detected_language} keywords - Significant: {len(sig_keywords)}, Trivial: {len(triv_keywords)}, Exclude: {len(excl_keywords)}')
            
            # Exclude check - highest priority
            for keyword in excl_keywords:
                if self._matchesWholeWord(keyword, analysis_text):
                    LOGGER.writeLog(f'MessageProcessor: Message excluded due to keyword: {keyword}')
                    return False, [], "excluded", translation_info
            
            # Find keyword matches (using language-specific keywords for matching)
            matched_significant_native = [kw for kw in sig_keywords if self._matchesWholeWord(kw, analysis_text)]
            matched_trivial_native = [kw for kw in triv_keywords if self._matchesWholeWord(kw, analysis_text)]
            
            # Convert matched keywords to English equivalents for consistent reporting
            matched_significant = [get_english_keyword(kw, significant_keywords) for kw in matched_significant_native]
            matched_trivial = [get_english_keyword(kw, trivial_keywords) for kw in matched_trivial_native]
            
            # Classification logic
            if matched_significant:
                LOGGER.writeLog(f'MessageProcessor: Message classified as Significant by keywords (English): {matched_significant}')
                LOGGER.writeLog(f'MessageProcessor: Native keywords that matched: {matched_significant_native}')
                
                # Enhanced filtering: Check additional criteria if enabled
                use_enhanced_filtering = False
                additional_criteria = []
                if country_config and 'message_filtering' in country_config:
                    filtering = country_config['message_filtering']
                    use_enhanced_filtering = filtering.get('use_ai_for_enhanced_filtering', False)
                    additional_criteria = filtering.get('additional_ai_criteria', [])
                
                if use_enhanced_filtering and additional_criteria and self.openai_processor:
                    LOGGER.writeLog(f'MessageProcessor: Performing enhanced filtering with {len(additional_criteria)} additional criteria')
                    try:
                        meets_criteria, failed_criteria, reason = self.openai_processor._checkAdditionalCriteria(
                            message, additional_criteria, country_config
                        )
                        
                        if not meets_criteria:
                            LOGGER.writeLog(f'MessageProcessor: Significant message failed additional criteria: {failed_criteria}')
                            return False, [], f"failed_additional_criteria_{reason}", translation_info
                        else:
                            LOGGER.writeLog(f'MessageProcessor: Message passed enhanced filtering - meets all additional criteria')
                    except Exception as e:
                        LOGGER.writeLog(f'MessageProcessor: Enhanced filtering failed, proceeding with original classification: {e}')
                        # Continue with original classification if criteria checking fails
                
                return True, matched_significant, "the list of SIGNIFICANT keywords", translation_info

            elif matched_trivial and not matched_significant:
                LOGGER.writeLog(f'MessageProcessor: Message classified as Trivial by keywords (English): {matched_trivial}')
                LOGGER.writeLog(f'MessageProcessor: Native keywords that matched: {matched_trivial_native}')
                return False, matched_trivial, "the list of TRIVIAL keywords", translation_info

            else:
                # No keywords matched
                LOGGER.writeLog(f'MessageProcessor: No keywords matched')
                if use_ai and self.openai_processor:
                    LOGGER.writeLog(f'MessageProcessor: Using AI analysis for unmatched message')
                    return self._analyzeWithAI(analysis_text, sig_keywords, triv_keywords, country_config, translation_info)
                else:
                    LOGGER.writeLog(f'MessageProcessor: AI disabled, defaulting to trivial for unmatched message')
                    return False, [], "no matching keywords across all keyword lists", translation_info
                    
        except Exception as e:
            LOGGER.writeLog(f'MessageProcessor: isMessageSignificant - Exception: {e}')
            
            # Send critical exception to admin for message processing errors
            try:
                from src.integrations.teams_utils import send_critical_exception
                send_critical_exception(
                    "MessageProcessingError",
                    str(e),
                    "MessageProcessor.isMessageSignificant",
                    additional_context={
                        "message_length": len(message) if message else 0,
                        "use_ai": use_ai if 'use_ai' in locals() else None,
                        "significant_keywords_count": len(significant_keywords) if significant_keywords else 0
                    }
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send message processing error to admin: {admin_error}")
            
            return False, [], "error", {'is_english': True, 'original_language': 'Unknown'}
    

    def _analyzeWithAI(self, message, significant_keywords, trivial_keywords, country_config, translation_info):
        """
        Delegate AI analysis to OpenAIProcessor when keyword matching is inconclusive.
        OpenAI can analyze non-English messages directly without pre-translation.
        """
        if not self.openai_processor:
            LOGGER.writeLog('MessageProcessor: No OpenAI processor available for AI analysis')
            return False, [], "ai_unavailable", translation_info
        
        try:
            # Use OpenAI for analysis - it can handle non-English messages directly
            is_significant, keywords, method = self.openai_processor._analyzeWithAI(
                message, significant_keywords, trivial_keywords, country_config
            )
            
            return is_significant, keywords, method, translation_info
            
        except Exception as e:
            LOGGER.writeLog(f'MessageProcessor: _analyzeWithAI - Exception: {e}')
            
            # Send critical exception to admin for AI analysis errors
            try:
                from src.integrations.teams_utils import send_critical_exception
                send_critical_exception(
                    "AIAnalysisError",
                    str(e),
                    "MessageProcessor._analyzeWithAI",
                    additional_context={
                        "message_length": len(message) if message else 0,
                        "original_language": translation_info.get('original_language', 'Unknown')
                    }
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send AI analysis error to admin: {admin_error}")
            
            return False, [], "ai_error", translation_info
    

    def translateMessage(self, message, country_config=None, source_language=None):
        """
        Translate a message to English using configured translation method.
        
        Args:
            message (str): The message text to translate
            country_config (dict): Country-specific configuration containing translation settings
            source_language (str): Already detected source language (avoids redundant detection)
            
        Returns:
            dict: Translation result containing:
                - success (bool): Whether translation was successful
                - translated_text (str): The translated text (or original if no translation needed)
                - original_text (str): The original message text
                - detected_language (str): The detected language of the original text
                - was_translated (bool): Whether translation actually occurred
                - translation_method (str): The method used for translation
        """
        try:
            if not message or not message.strip():
                LOGGER.writeLog('MessageProcessor: Empty message provided for translation')
                return {
                    'success': False,
                    'translated_text': message or '',
                    'original_text': message or '',
                    'detected_language': 'Unknown',
                    'was_translated': False,
                    'translation_method': 'empty_message'
                }
            
            # Get translation settings from country config
            use_ai_for_translation = False
            if country_config and 'message_filtering' in country_config:
                filtering = country_config['message_filtering']
                use_ai_for_translation = filtering.get('use_ai_for_translation', False)
            
            LOGGER.writeLog(f'MessageProcessor: Translating message using {"OpenAI" if use_ai_for_translation else "Google Translate"}')
            
            # Use the translation processor with provided language info to avoid redundant detection
            translation_result = self.translation_processor.translate(
                text=message,
                use_ai=use_ai_for_translation,
                source_language=source_language
            )
            
            # Log translation result
            if translation_result['was_translated']:
                LOGGER.writeLog(f'MessageProcessor: Message translated from {translation_result["detected_language"]} to English using {translation_result["translation_method"]}')
            else:
                LOGGER.writeLog(f'MessageProcessor: Message already in English or translation not needed')
            
            return translation_result
            
        except Exception as e:
            LOGGER.writeLog(f'MessageProcessor: translateMessage - Exception: {e}')
            
            # Send critical exception to admin for translation errors
            try:
                from src.integrations.teams_utils import send_critical_exception
                send_critical_exception(
                    "MessageTranslationError",
                    str(e),
                    "MessageProcessor.translateMessage",
                    additional_context={
                        "message_length": len(message) if message else 0,
                        "use_ai": use_ai_for_translation if 'use_ai_for_translation' in locals() else None
                    }
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send message translation error to admin: {admin_error}")
            
            return {
                'success': False,
                'translated_text': message or '',
                'original_text': message or '',
                'detected_language': 'Unknown',
                'was_translated': False,
                'translation_method': 'error'
            }