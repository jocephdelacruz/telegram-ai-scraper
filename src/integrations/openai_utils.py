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


   def translateToEnglish(self, text, source_language="Unknown"):
      """
      Translate text to English without language detection (for when language is already known)
      
      Args:
         text (str): Text to translate
         source_language (str): Known source language (optional, for context)
         
      Returns:
         tuple: (success, translated_text)
      """
      try:
         if not text or not text.strip():
            return False, text
            
         prompt = f"""
         Translate the following text to English. If it's already in English, return it as is.
         {"Source language: " + source_language if source_language != "Unknown" else ""}
         
         Text to translate: "{text}"
         
         Provide only the English translation without any additional explanation.
         """

         response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[
               {"role": "system", "content": "You are a professional translator. Provide accurate English translations."},
               {"role": "user", "content": prompt}
            ],
            max_tokens=self.max_tokens,
            temperature=0.3  # Lower temperature for more consistent translations
         )

         if response.choices[0] and response.choices[0].message.content:
            translated_text = response.choices[0].message.content.strip()
            
            # Remove any quotes that might be added by the AI
            if translated_text.startswith('"') and translated_text.endswith('"'):
               translated_text = translated_text[1:-1]
            elif translated_text.startswith("'") and translated_text.endswith("'"):
               translated_text = translated_text[1:-1]
            
            LOGGER.writeLog(f'OpenAIProcessor: Translation successful from {source_language} to English')
            return True, translated_text
         
         # Fallback
         LOGGER.writeLog('OpenAIProcessor: Translation failed, no response content')
         return False, text
         
      except Exception as e:
         LOGGER.writeLog(f'OpenAIProcessor: translateToEnglish - Exception: {e}')
         self._error_count += 1
         
         # Send critical exception to admin for OpenAI translation failures
         if self._error_count % 10 == 0:  # Every 10th error
            try:
               from .teams_utils import send_critical_exception
               send_critical_exception(
                  "OpenAITranslationOnlyError",
                  str(e),
                  "OpenAIProcessor.translateToEnglish",
                  additional_context={
                     "text_length": len(text) if text else 0,
                     "source_language": source_language,
                     "error_count": self._error_count
                  }
               )
            except Exception as admin_error:
               LOGGER.writeLog(f"Failed to send OpenAI translation error to admin: {admin_error}")
         
         return False, text


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
      """
      Internal method to analyze message using OpenAI when keyword filtering is inconclusive.
      
      This method uses contextual analysis to determine if a message relates to the provided
      significant keywords, and identifies which specific keyword concept matches the message.
      Enhanced with exception rules to filter out country-irrelevant content.
      
      Args:
          message (str): The message text to analyze
          significant_keywords (list): List of keywords/topics that indicate significance
          trivial_keywords (list): List of keywords/topics that indicate triviality  
          country_config (dict): Optional country-specific configuration
          
      Returns:
          tuple: (is_significant, matched_keywords, classification_method)
      """
      try:
         # Prepare keyword lists for AI analysis
         significant_keywords_list = significant_keywords or []
         trivial_keywords_list = trivial_keywords or []
         
         # Check for enhanced filtering configuration
         use_enhanced_filtering = False
         exception_rules = []
         if country_config and 'message_filtering' in country_config:
            filtering = country_config['message_filtering']
            use_enhanced_filtering = filtering.get('use_ai_for_enhanced_filtering', False)
            exception_rules = filtering.get('ai_exception_rules', [])
         
         LOGGER.writeLog(f'OpenAIProcessor: Starting AI contextual analysis with {len(significant_keywords_list)} significant and {len(trivial_keywords_list)} trivial keywords, enhanced filtering: {use_enhanced_filtering}')
         
         # Build country-specific context for AI
         country_context = ""
         country_name = "Iraq"
         if country_config:
            country_name = country_config.get('name', 'Iraq')
            country_context = f"""
            
         Country-specific context for {country_name}:
         Consider regional context and local significance when analyzing the message.
            """
         
         # Build exception rules context if enhanced filtering is enabled
         exception_context = ""
         if use_enhanced_filtering and exception_rules:
            exception_text = "\n".join([f"- {rule}" for rule in exception_rules])
            exception_context = f"""
            
         ADDITIONAL EXCLUSION CRITERIA:
         Even if the message relates to significant keywords, it should be classified as TRIVIAL if it matches any of these exception rules:
         {exception_text}
         
         Apply these exclusion criteria strictly - if the message matches any exception rule, classify as Trivial regardless of keyword matches.
            """
         
         prompt = f"""
         Analyze the following message and determine if it is significant based STRICTLY on the provided significant keywords list.

         SIGNIFICANT KEYWORDS/TOPICS: {', '.join(significant_keywords_list) if significant_keywords_list else 'None provided'}

         STRICT CLASSIFICATION RULES:
         1. The message is ONLY significant if it directly relates to, discusses, or has contextual meaning similar to ONE OR MORE of the provided SIGNIFICANT keywords
         2. Be very strict - do not classify as significant unless you can clearly identify which specific significant keyword(s) the message relates to
         3. General topics like education, routine announcements, or everyday activities should be classified as Trivial UNLESS they specifically relate to the significant keywords
         4. If you classify as Significant, you MUST identify which specific keyword from the significant list best matches the message context{exception_context}

         Your response format:
         - If Significant: "Significant: [specific keyword from the significant list that best matches]"
         - If Trivial: "Trivial"

         Message to analyze: "{message}"{country_context}

         Remember: Be extremely strict. Only classify as Significant if the message clearly and directly relates to one of the specific significant keywords provided{"" if not exception_context else " AND does not match any exclusion criteria"}.
         """

         response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[{"role": "system", "content": "You are a strict intelligence analyst. Only classify messages as significant if they clearly relate to the provided significant keywords. Be conservative and precise."},
                        {"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=0.2  # Lower temperature for more consistent and conservative analysis
         )

         if response.choices[0] and response.choices[0].message.content:
            answer = response.choices[0].message.content.strip()
            
            if answer.startswith("Significant:"):
               # Extract the matched keyword from the response
               matched_keyword = answer.replace("Significant:", "").strip()
               
               # Translate the keyword to English if it's not already in English
               if matched_keyword and not self._isLikelyEnglish(matched_keyword):
                  try:
                     success, translated_keyword = self.translateToEnglish(matched_keyword)
                     if success:
                        matched_keyword = translated_keyword
                  except Exception as translate_error:
                     LOGGER.writeLog(f'OpenAIProcessor: Failed to translate matched keyword "{matched_keyword}": {translate_error}')
               
               # Enhanced filtering: Second-pass exception check if enabled and exception rules not in prompt
               if use_enhanced_filtering and exception_rules and not exception_context:
                  LOGGER.writeLog(f'OpenAIProcessor: Performing second-pass exception rule validation for significant message')
                  matches_exception, matched_rule, reason = self._checkExceptionRules(message, exception_rules, country_config)
                  
                  if matches_exception:
                     LOGGER.writeLog(f'OpenAIProcessor: Message excluded by second-pass exception check: {matched_rule}')
                     return False, [], f"ai_excluded_by_exception_{reason}"
                  else:
                     LOGGER.writeLog(f'OpenAIProcessor: Message passed second-pass exception check')
               
               LOGGER.writeLog(f'OpenAIProcessor: Message classified as Significant by AI - Matched keyword: {matched_keyword}')
               return True, [matched_keyword] if matched_keyword else [], "ai_significant_contextual"
               
            elif answer == "Trivial":
               LOGGER.writeLog(f'OpenAIProcessor: Message classified as Trivial by AI using strict keyword contextual analysis')
               return False, [], "ai_trivial_contextual"
         
         # Default to trivial if no clear response
         LOGGER.writeLog(f'OpenAIProcessor: Unable to classify message using AI contextual analysis, defaulting to Trivial')
         return False, [], "ai_contextual_default"
         
      except Exception as e:
         LOGGER.writeLog(f'OpenAIProcessor: _analyzeWithAI - Exception: {e}')
         
         # Send critical exception to admin for AI analysis failures
         try:
            from .teams_utils import send_critical_exception
            send_critical_exception(
               "OpenAIStrictAnalysisError",
               str(e),
               "OpenAIProcessor._analyzeWithAI",
               additional_context={
                  "message_length": len(message) if message else 0,
                  "significant_keywords_count": len(significant_keywords) if significant_keywords else 0,
                  "trivial_keywords_count": len(trivial_keywords) if trivial_keywords else 0,
                  "model": self.openai_model,
                  "analysis_type": "strict_keyword_contextual"
               }
            )
         except Exception as admin_error:
            LOGGER.writeLog(f"Failed to send OpenAI strict analysis error to admin: {admin_error}")
         
         return False, [], "ai_strict_error"


   def _checkExceptionRules(self, message, exception_rules, country_config=None):
      """
      Check if a message context matches any of the provided exception rules.
      This is used to filter out messages that match keywords but don't actually 
      relate to the target country or specific criteria.
      
      Args:
          message (str): The message text to analyze
          exception_rules (list): List of exception rule strings to check against
          country_config (dict): Optional country-specific configuration
          
      Returns:
          tuple: (matches_exception, matched_rule, reason)
      """
      try:
         if not exception_rules or len(exception_rules) == 0:
            LOGGER.writeLog('OpenAIProcessor: No exception rules provided, skipping exception check')
            return False, None, "no_exception_rules"
         
         country_name = "the target country"
         if country_config:
            country_name = country_config.get('name', 'the target country')
         
         LOGGER.writeLog(f'OpenAIProcessor: Checking message against {len(exception_rules)} exception rules for {country_name}')
         
         # Build exception rules context
         rules_text = "\n".join([f"- {rule}" for rule in exception_rules])
         
         prompt = f"""
         Analyze the following message to determine if it should be EXCLUDED from significance classification based on the provided exception rules.

         TARGET COUNTRY: {country_name}
         
         EXCEPTION RULES (if ANY of these apply, the message should be marked as NOT significant):
         {rules_text}

         ANALYSIS INSTRUCTIONS:
         1. Read the message carefully and understand its context
         2. Check if the message matches ANY of the exception rules above
         3. Be precise - only exclude if there's a clear match to an exception rule
         4. Consider the geographic context and relevance to {country_name}

         MESSAGE TO ANALYZE: "{message}"

         RESPONSE FORMAT:
         - If matches an exception rule: "EXCLUDE: [specific rule that applies]"
         - If does not match any exception rule: "INCLUDE"

         Remember: Only exclude if the message clearly violates one of the specific exception rules listed above.
         """

         response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[{"role": "system", "content": "You are a precise content analyst. Only exclude messages if they clearly match the provided exception rules."},
                        {"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=0.2  # Very low temperature for consistent exception checking
         )

         if response.choices[0] and response.choices[0].message.content:
            answer = response.choices[0].message.content.strip()
            
            if answer.startswith("EXCLUDE:"):
               # Extract the matched exception rule
               matched_rule = answer.replace("EXCLUDE:", "").strip()
               LOGGER.writeLog(f'OpenAIProcessor: Message excluded by exception rule: {matched_rule}')
               return True, matched_rule, "ai_exception_matched"
               
            elif answer == "INCLUDE":
               LOGGER.writeLog(f'OpenAIProcessor: Message passed exception rule check - no exclusions apply')
               return False, None, "ai_exception_passed"
         
         # Default to include if no clear response
         LOGGER.writeLog(f'OpenAIProcessor: Unable to determine exception status, defaulting to INCLUDE')
         return False, None, "ai_exception_default"
         
      except Exception as e:
         LOGGER.writeLog(f'OpenAIProcessor: _checkExceptionRules - Exception: {e}')
         
         # Send critical exception to admin for exception checking failures
         try:
            from .teams_utils import send_critical_exception
            send_critical_exception(
               "OpenAIExceptionCheckError",
               str(e),
               "OpenAIProcessor._checkExceptionRules",
               additional_context={
                  "message_length": len(message) if message else 0,
                  "exception_rules_count": len(exception_rules) if exception_rules else 0,
                  "country_name": country_name,
                  "model": self.openai_model
               }
            )
         except Exception as admin_error:
            LOGGER.writeLog(f"Failed to send OpenAI exception check error to admin: {admin_error}")
         
         # On error, default to include (don't exclude due to technical issues)
         return False, None, "ai_exception_error"


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