import sys
import os
import re
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core import log_handling as lh
from src.integrations.openai_utils import OpenAIProcessor


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
    
    def detectLanguage(self, text):
        """
        Detect the language of the text using heuristic analysis.
        Returns the detected language: 'english', 'arabic', or 'unknown'
        
        This method replaces the AI-based language detection for better performance
        and cost optimization when working with dual-language keyword systems.
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
            
            # Common Arabic words and particles
            common_arabic_words = [
                'في', 'من', 'إلى', 'على', 'عن', 'مع', 'كل', 'هذا', 'هذه', 'ذلك', 'تلك',
                'التي', 'الذي', 'التي', 'لكن', 'أو', 'أم', 'إذا', 'عند', 'بعد', 'قبل',
                'حول', 'ضد', 'تحت', 'فوق', 'أمام', 'خلف', 'جانب', 'داخل', 'خارج', 'بين',
                'أثناء', 'خلال', 'عبر', 'حتى', 'منذ', 'لدى', 'لديه', 'لديها', 'معه', 'معها',
                'له', 'لها', 'لهم', 'لهن', 'منه', 'منها', 'منهم', 'منهن', 'إليه', 'إليها',
                'عليه', 'عليها', 'عنه', 'عنها', 'فيه', 'فيها', 'به', 'بها', 'كما', 'إن',
                'أن', 'كان', 'كانت', 'يكون', 'تكون', 'سوف', 'قد', 'لقد', 'قام', 'قامت',
                'يقول', 'تقول', 'قال', 'قالت', 'أقول', 'نقول', 'أعلن', 'أعلنت', 'يعلن',
                'الآن', 'اليوم', 'أمس', 'غدا', 'هنا', 'هناك', 'هنالك', 'حيث', 'أين', 'متى',
                'كيف', 'ماذا', 'لماذا', 'من', 'أي', 'كم', 'عاجل', 'أخبار', 'جديد', 'مهم'
            ]
            
            # Convert to lowercase for comparison and split into words
            text_lower = text.lower()
            words = text_lower.split()
            
            if len(words) < 2:
                # For very short messages, check character types
                has_arabic_chars = any('\u0600' <= char <= '\u06FF' for char in text)
                has_latin_chars = any('a' <= char.lower() <= 'z' for char in text)
                
                if has_arabic_chars and not has_latin_chars:
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
            
            LOGGER.writeLog(f'MessageProcessor: Language detection - English ratio: {english_ratio:.2f}, Arabic ratio: {arabic_ratio:.2f}, Arabic script: {has_arabic_script}, Latin script: {has_latin_script}')
            
            # Decision logic
            if has_arabic_script and arabic_ratio > 0.1:
                return 'arabic'
            elif has_latin_script and english_ratio > 0.2:
                return 'english'
            elif has_arabic_script and not has_latin_script:
                return 'arabic'
            elif has_latin_script and not has_arabic_script:
                return 'english'
            elif arabic_ratio > english_ratio:
                return 'arabic'
            elif english_ratio > arabic_ratio:
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
                'original_language': detected_language.title(),
                'translated_text': None
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
            
            sig_keywords = get_keywords(significant_keywords)
            triv_keywords = get_keywords(trivial_keywords)
            excl_keywords = get_keywords(exclude_keywords)
            
            LOGGER.writeLog(f'MessageProcessor: Using {detected_language} keywords - Significant: {len(sig_keywords)}, Trivial: {len(triv_keywords)}, Exclude: {len(excl_keywords)}')
            
            # Exclude check - highest priority
            for keyword in excl_keywords:
                if self._matchesWholeWord(keyword, analysis_text):
                    LOGGER.writeLog(f'MessageProcessor: Message excluded due to keyword: {keyword}')
                    return False, [], "excluded", translation_info
            
            # Find keyword matches
            matched_significant = [kw for kw in sig_keywords if self._matchesWholeWord(kw, analysis_text)]
            matched_trivial = [kw for kw in triv_keywords if self._matchesWholeWord(kw, analysis_text)]
            
            # Classification logic
            if matched_significant and matched_trivial:
                LOGGER.writeLog(f'MessageProcessor: Mixed keywords found - Significant: {matched_significant}, Trivial: {matched_trivial}')
                if use_ai and self.openai_processor:
                    # Use AI to resolve ambiguous cases
                    LOGGER.writeLog(f'MessageProcessor: Using AI analysis for mixed keywords')
                    return self._analyzeWithAI(analysis_text, sig_keywords, triv_keywords, country_config, translation_info)
                else:
                    # Default to significant if AI is disabled
                    LOGGER.writeLog(f'MessageProcessor: AI disabled, defaulting to significant for mixed keywords')
                    return True, matched_significant, "keyword_significant", translation_info
            
            elif matched_significant and not matched_trivial:
                LOGGER.writeLog(f'MessageProcessor: Message classified as Significant by keywords: {matched_significant}')
                return True, matched_significant, "keyword_significant", translation_info
            
            elif matched_trivial and not matched_significant:
                LOGGER.writeLog(f'MessageProcessor: Message classified as Trivial by keywords: {matched_trivial}')
                return False, matched_trivial, "keyword_trivial", translation_info
            
            else:
                # No keywords matched
                LOGGER.writeLog(f'MessageProcessor: No keywords matched')
                if use_ai and self.openai_processor:
                    LOGGER.writeLog(f'MessageProcessor: Using AI analysis for unmatched message')
                    return self._analyzeWithAI(analysis_text, sig_keywords, triv_keywords, country_config, translation_info)
                else:
                    LOGGER.writeLog(f'MessageProcessor: AI disabled, defaulting to trivial for unmatched message')
                    return False, [], "no_match_trivial", translation_info
                    
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
            
            return False, [], "error", {'is_english': True, 'original_language': 'Unknown', 'translated_text': None}
    
    def _analyzeWithAI(self, message, significant_keywords, trivial_keywords, country_config, translation_info):
        """
        Delegate AI analysis to OpenAIProcessor when keyword matching is inconclusive.
        """
        if not self.openai_processor:
            LOGGER.writeLog('MessageProcessor: No OpenAI processor available for AI analysis')
            return False, [], "ai_unavailable", translation_info
        
        try:
            # Check if message needs translation for AI analysis
            if translation_info['original_language'].lower() != 'english':
                # Get translation for AI analysis
                LOGGER.writeLog('MessageProcessor: Getting translation for AI analysis')
                is_english, translated_text, detected_lang = self.openai_processor.detectLanguageAndTranslate(message)
                if not is_english and translated_text != message:
                    message_for_ai = translated_text
                    translation_info['translated_text'] = translated_text
                else:
                    message_for_ai = message
            else:
                message_for_ai = message
            
            # Use OpenAI for analysis
            is_significant, keywords, method = self.openai_processor._analyzeWithAI(
                message_for_ai, significant_keywords, trivial_keywords, country_config
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
                        "translation_required": translation_info.get('original_language', 'Unknown') != 'English'
                    }
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send AI analysis error to admin: {admin_error}")
            
            return False, [], "ai_error", translation_info