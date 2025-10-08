import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from openai import OpenAI     # import the OpenAI Python library for calling the OpenAI API
from src.core import log_handling as lh     # My custom class for log handling

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "openai.log")
LOG_TZ = "Asia/Manila"
LOGGER = lh.LogHandling(LOG_FILE, LOG_TZ)


class OpenAIProcessor:
   apikey = ""
   openai_client = None
   #openai_model = "gpt-4o-mini"                    # You can switch to "gpt-4o" for a smarter AI (but more than x50 the price)
   openai_model = "gpt-5-mini"                    # You can switch to "gpt-5" for a smarter AI (but x5 the price)
   openai_model_embed = ""
   #openai_model = "gpt-3.5-turbo"                 # This can be used in Free Tier
   openai_embed_model = "text-embedding-3-small"   # You can also use 'text-embedding-3-small' for a more accurate vector representation of the articles (3072 vs 1536)
   max_tokens = 4096
   temperature = 0.7


   def __init__(self, key=""):
      try:
         if key != "":
            #self.openai_client = OpenAI()      # This can be used if I'll set first the OPENAI_API_KEY env variable in the server
            self.openai_client = OpenAI(api_key=key)
            # List available models as a test request -- used to test connection
         else:
            LOGGER.writeLog('OpenAIProcessor: init - Failed to retrieve OPENAI_API_KEY')
      except Exception as e:
         LOGGER.writeLog(f'OpenAIProcessor: init - Exception: {e}')
      self.apikey = key


   def _isLikelyEnglish(self, text):
      """
      Quick heuristic check to determine if text is likely English.
      This helps avoid unnecessary API calls for obviously English text.
      """
      # Common English words that appear frequently
      common_english_words = [
         'the', 'and', 'is', 'in', 'to', 'of', 'a', 'for', 'with', 'on', 'at', 'by',
         'this', 'that', 'from', 'they', 'we', 'be', 'have', 'an', 'as', 'are', 'was',
         'but', 'not', 'or', 'had', 'will', 'would', 'there', 'been', 'their'
      ]
      
      # Convert to lowercase for comparison
      text_lower = text.lower()
      words = text_lower.split()
      
      if len(words) < 3:
         # For very short messages, default to checking with AI
         return False
      
      # Count how many common English words are present
      english_word_count = sum(1 for word in words if any(eng_word in word for eng_word in common_english_words))
      
      # If more than 25% of words contain common English words, likely English
      english_ratio = english_word_count / len(words)
      
      # Also check for non-Latin characters (Arabic, Chinese, etc.)
      has_non_latin = any(ord(char) > 127 for char in text if char.isalpha())
      
      # If high English word ratio and no non-Latin characters, likely English
      if english_ratio > 0.25 and not has_non_latin:
         return True
      
      return False


   def detectLanguageAndTranslate(self, text):
      """
      Detect if text is in English, and translate to English if not.
      Returns tuple: (is_english, translated_text, original_language)
      Cost-effective: Uses heuristic check first, then single API call for detection and translation.
      """
      try:
         # Quick heuristic check first to save API calls
         if self._isLikelyEnglish(text):
            LOGGER.writeLog('OpenAIProcessor: Text appears to be English (heuristic), skipping translation')
            return True, text, "English"
         
         # If not obviously English, use AI for detection and translation
         prompt = f"""
         Analyze the following text and determine:
         1. What language it is written in
         2. If it's not English, provide an English translation
         3. If it's already English, just return the original text

         Please respond in this exact format:
         Language: [detected language]
         Translation: [English translation or original text if already English]

         Text to analyze: "{text}"
         """

         response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[
               {"role": "system", "content": "You are a language detection and translation assistant. Be accurate and concise."},
               {"role": "user", "content": prompt}
            ],
            max_tokens=self.max_tokens,
            temperature=0.3  # Lower temperature for more consistent output format
         )

         if response.choices[0] and response.choices[0].message.content:
            result = response.choices[0].message.content.strip()
            
            # Parse the response
            lines = result.split('\n')
            detected_language = "Unknown"
            translated_text = text  # Default to original text
            
            for line in lines:
               if line.startswith("Language:"):
                  detected_language = line.replace("Language:", "").strip()
               elif line.startswith("Translation:"):
                  translated_text = line.replace("Translation:", "").strip()
            
            is_english = detected_language.lower() in ['english', 'en', 'eng']
            
            LOGGER.writeLog(f'OpenAIProcessor: Language detected: {detected_language}, Is English: {is_english}')
            
            return is_english, translated_text, detected_language
         
         # Default fallback
         LOGGER.writeLog('OpenAIProcessor: Language detection failed, assuming English')
         return True, text, "English"
         
      except Exception as e:
         LOGGER.writeLog(f'OpenAIProcessor: detectLanguageAndTranslate - Exception: {e}')
         # On error, assume English and return original text
         return True, text, "Unknown"


   def isMessageSignificant(self, message, significant_keywords=None, trivial_keywords=None, exclude_keywords=None, country_config=None):
      try:
         # First, detect language and translate if necessary
         is_english, translated_message, detected_language = self.detectLanguageAndTranslate(message)
         
         # Store translation info for later use
         translation_info = {
            'is_english': is_english,
            'original_language': detected_language,
            'translated_text': translated_message if not is_english else None
         }
         
         # Use translated text for analysis (or original if already English)
         analysis_text = translated_message
         
         # Use country-specific keywords if provided
         if country_config and 'message_filtering' in country_config:
            filtering = country_config['message_filtering']
            significant_keywords = filtering.get('significant_keywords', significant_keywords or [])
            trivial_keywords = filtering.get('trivial_keywords', trivial_keywords or [])
            exclude_keywords = filtering.get('exclude_keywords', exclude_keywords or [])
         
         # Set defaults if still None
         if significant_keywords is None:
            significant_keywords = ["breaking news", "alert", "urgent", "emergency", "crisis"]
         if trivial_keywords is None:
            trivial_keywords = ["weather", "sports", "entertainment", "celebrity"]
         if exclude_keywords is None:
            exclude_keywords = ["advertisement", "promo", "discount", "sale"]
         
         # First check if message contains exclude keywords (using translated text)
         analysis_text_lower = analysis_text.lower()
         for keyword in exclude_keywords:
            if keyword.lower() in analysis_text_lower:
               LOGGER.writeLog(f'OpenAIProcessor: Message excluded due to keyword: {keyword}')
               return False, [], "excluded", translation_info

         # Check for significant keywords match
         matched_significant = []
         for keyword in significant_keywords:
            if keyword.lower() in analysis_text_lower:
               matched_significant.append(keyword)
         
         # Check for trivial keywords match
         matched_trivial = []
         for keyword in trivial_keywords:
            if keyword.lower() in analysis_text_lower:
               matched_trivial.append(keyword)
         
         # If both significant and trivial keywords match, use AI to decide
         if matched_significant and matched_trivial:
            LOGGER.writeLog(f'OpenAIProcessor: Mixed keywords found - using AI analysis')
            is_significant, keywords, method = self._analyzeWithAI(analysis_text, significant_keywords, trivial_keywords, country_config)
            return is_significant, keywords, method, translation_info
         
         # If only significant keywords match, classify as significant
         if matched_significant and not matched_trivial:
            LOGGER.writeLog(f'OpenAIProcessor: Message classified as Significant by keywords: {matched_significant}')
            return True, matched_significant, "keyword_significant", translation_info
         
         # If only trivial keywords match, classify as trivial
         if matched_trivial and not matched_significant:
            LOGGER.writeLog(f'OpenAIProcessor: Message classified as Trivial by keywords: {matched_trivial}')
            return False, matched_trivial, "keyword_trivial", translation_info
         
         # No keywords matched, use AI analysis
         LOGGER.writeLog(f'OpenAIProcessor: No keywords matched - using AI analysis')
         is_significant, keywords, method = self._analyzeWithAI(analysis_text, significant_keywords, trivial_keywords, country_config)
         return is_significant, keywords, method, translation_info
         
      except Exception as e:
         LOGGER.writeLog(f'OpenAIProcessor: isMessageSignificant - Exception: {e}')
         return False, [], "error", {'is_english': True, 'original_language': 'Unknown', 'translated_text': None}


   def _analyzeWithAI(self, message, significant_keywords, trivial_keywords, country_config=None):
      """Internal method to analyze message using OpenAI when keyword filtering is inconclusive"""
      try:
         # Build country-specific context for AI
         country_context = ""
         if country_config:
            country_name = country_config.get('name', 'this country')
            country_context = f"""
            
        Country-specific context for {country_name}:
        - Significant topics include: {', '.join(significant_keywords[:10])}{'...' if len(significant_keywords) > 10 else ''}
        - Trivial topics include: {', '.join(trivial_keywords[:10])}{'...' if len(trivial_keywords) > 10 else ''}
        
        Use this country-specific context to better classify the message.
            """
         
         prompt = f"""
         Analyze the following message and determine if it is significant news that would be important for intelligence or security analysis.

         Consider significant:
         - Breaking news or urgent alerts
         - Security incidents, cyber attacks, data breaches
         - Political developments, government actions
         - Economic disruptions or major market news
         - Natural disasters or emergencies
         - Suspicious activities or investigations
         - Infrastructure issues or outages

         Consider NOT significant (trivial):
         - Sports scores, entertainment news
         - Weather forecasts (unless extreme)
         - Celebrity gossip or lifestyle content
         - Routine announcements
         - Promotional content or advertisements{country_context}

         Message: "{message}"

         Respond with only 'Significant' or 'Trivial' without any additional explanation.
         """

         response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[{"role": "system", "content": "You are an expert intelligence analyst that evaluates message significance."},
                        {"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=0.3
         )

         if response.choices[0] and response.choices[0].message.content:
            answer = response.choices[0].message.content.strip()
            
            if answer == "Significant":
               LOGGER.writeLog(f'OpenAIProcessor: Message classified as Significant by AI')
               return True, [], "ai_significant"
            else:
               LOGGER.writeLog(f'OpenAIProcessor: Message classified as Trivial by AI')
               return False, [], "ai_trivial"
         
         # Default to trivial if no clear response
         LOGGER.writeLog(f'OpenAIProcessor: Unable to classify message, defaulting to Trivial')
         return False, [], "ai_default"
         
      except Exception as e:
         LOGGER.writeLog(f'OpenAIProcessor: _analyzeWithAI - Exception: {e}')
         return False, [], "ai_error"


   def isArticleSignificant(self, article, significant_keywords=None, trivial_keywords=None):
      """Backward compatibility method for existing code"""
      try:
         if significant_keywords is None:
            significant_keywords = ["breaking news", "alert", "urgent", "emergency", "crisis"]
         if trivial_keywords is None:
            trivial_keywords = ["weather", "sports", "entertainment", "celebrity"]
            
         prompt = f"""
         Determine if the article below is significant or trivial, and provide the answer without any additional explanation (either just the word 'Significant' or 'Trivial').
         An article can be classified as significant, if it's related to any of the topics/keywords listed here: {significant_keywords}
         An article can be classified as trivial, if they only talk about any of the following topics/keywords listed here: {trivial_keywords}
         In addition, if an article talks about topics that are both can be classified as trivial and significant, classify it as 'Significant'

         Article: {article}
         """

         response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt}],
            max_tokens=self.max_tokens
         )

         if response.choices[0] and response.choices[0].message.content:
            answer = response.choices[0].message.content.strip()
            if answer == "Significant":
               return True
         
         return False
      except Exception as e:
         LOGGER.writeLog(f'OpenAIProcessor: isArticleSignificant - Exception: {e}')
         return False


   def checkIfSimilar(self, article1, article2):
      try:
         # prompt = f"""
         # Two news articles are given below. Your task is to determine if they are related, not related, or identical (discussing the exact same topic).
         # Provide a response in one of the following categories without any additional explanation: "Identical", "Related", "Not Related".

         # Article 1: {article_1}

         # Article 2: {article_2}
         # """
         prompt = f"""
         Two news articles are given below. Your task is to determine if they are related or not.  Related meaning they are either discussing the same event/topic, or the other event is related or connected to the other (e.g. the other event happened as a result of the other)
         Provide a response in one of the following categories without any additional explanation: "Related", "Not Related".

         Article 1: {article1}

         Article 2: {article2}
         """

         response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt}],
            max_tokens=self.max_tokens
         )

         if response.choices[0] and response.choices[0].message.content:
            answer = response.choices[0].message.content.strip()
            if answer == "Identical" or answer == "Related":
               return True
         
         return False
      except Exception as e:
         LOGGER.writeLog(f'OpenAIProcessor: checkArticleSimilarity - Exception: {e}')
         return False


   def getTextEmbedValue(self, article):
      try:
         response = self.openai_client.embeddings.create(
            input=article,
            model=self.openai_embed_model
         )
         return response.data[0].embedding
      except Exception as e:
         LOGGER.writeLog(f'OpenAIProcessor: getAIEmbedValue - Exception: {e}')
         return ""