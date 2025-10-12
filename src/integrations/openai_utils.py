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
   openai_model = "gpt-4o-mini"                    # Use gpt-4o-mini which supports max_tokens parameter
   openai_model_embed = ""
   #openai_model = "gpt-3.5-turbo"                 # This can be used in Free Tier
   openai_embed_model = "text-embedding-3-small"   # You can also use 'text-embedding-3-small' for a more accurate vector representation of the articles (3072 vs 1536)
   max_tokens = 4096
   temperature = 0.7


   def __init__(self, key=""):
      self._error_count = 0
      
      try:
         if key != "":
            #self.openai_client = OpenAI()      # This can be used if I'll set first the OPENAI_API_KEY env variable in the server
            self.openai_client = OpenAI(api_key=key)
            # List available models as a test request -- used to test connection
         else:
            LOGGER.writeLog('OpenAIProcessor: init - Failed to retrieve OPENAI_API_KEY')
            
            # Send critical exception to admin for missing API key
            try:
               from .teams_utils import send_configuration_error
               send_configuration_error(
                  "config.json",
                  "OpenAI API key not provided or empty",
                  "Add valid OPEN_AI_KEY to config.json"
               )
            except Exception as admin_error:
               LOGGER.writeLog(f"Failed to send OpenAI config error to admin: {admin_error}")
                  
      except Exception as e:
         LOGGER.writeLog(f'OpenAIProcessor: init - Exception: {e}')
         
         # Send critical exception to admin for initialization failure
         try:
            from .teams_utils import send_critical_exception
            send_critical_exception(
               "OpenAIInitializationError",
               str(e),
               "OpenAIProcessor.__init__",
               additional_context={"has_api_key": key != ""}
            )
         except Exception as admin_error:
            LOGGER.writeLog(f"Failed to send OpenAI initialization error to admin: {admin_error}")
               
      self.apikey = key


   def _isLikelyEnglish(self, text):
      """
      Quick heuristic check to determine if text is likely English.
      This helps avoid unnecessary API calls for obviously English text.
      """
      # Import MessageProcessor for language detection
      from src.core.message_processor import MessageProcessor
      processor = MessageProcessor()
      return processor.detectLanguage(text) == 'english'


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
         self._error_count += 1
         
         # Send critical exception to admin for OpenAI API failures
         if self._error_count % 10 == 0:  # Every 10th error
            try:
               from .teams_utils import send_critical_exception
               send_critical_exception(
                  "OpenAIAPIError",
                  str(e),
                  "OpenAIProcessor.detectLanguageAndTranslate",
                  additional_context={
                     "text_length": len(text) if text else 0,
                     "total_errors": self._error_count,
                     "model": self.openai_model
                  }
               )
            except Exception as admin_error:
               LOGGER.writeLog(f"Failed to send OpenAI API error to admin: {admin_error}")
         
         # On error, assume English and return original text
         return True, text, "Unknown"


   def isMessageSignificant(self, message, significant_keywords=None, trivial_keywords=None, exclude_keywords=None, country_config=None):
      """
      Backward compatibility wrapper that delegates to MessageProcessor.
      This method is deprecated - use MessageProcessor.isMessageSignificant() directly for better performance.
      """
      try:
         from src.core.message_processor import MessageProcessor
         processor = MessageProcessor(openai_processor=self)
         return processor.isMessageSignificant(message, significant_keywords, trivial_keywords, exclude_keywords, country_config)
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
         
         # Send critical exception to admin for AI analysis failures
         try:
            from .teams_utils import send_critical_exception
            send_critical_exception(
               "OpenAIAnalysisError",
               str(e),
               "OpenAIProcessor._analyzeWithAI",
               additional_context={
                  "message_length": len(message) if message else 0,
                  "significant_keywords_count": len(significant_keywords) if significant_keywords else 0,
                  "model": self.openai_model
               }
            )
         except Exception as admin_error:
            LOGGER.writeLog(f"Failed to send OpenAI analysis error to admin: {admin_error}")
         
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