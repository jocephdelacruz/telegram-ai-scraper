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
      Enhanced with additional AI criteria for refined significance determination.
      
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
         additional_criteria = []
         if country_config and 'message_filtering' in country_config:
            filtering = country_config['message_filtering']
            use_enhanced_filtering = filtering.get('use_ai_for_enhanced_filtering', False)
            additional_criteria = filtering.get('additional_ai_criteria', [])
         
         LOGGER.writeLog(f'OpenAIProcessor: Starting AI contextual analysis with {len(significant_keywords_list)} significant keywords, enhanced filtering: {use_enhanced_filtering}')
         
         # Build additional criteria context if enhanced filtering is enabled
         additional_context = ""
         if use_enhanced_filtering and additional_criteria:
            criteria_text = "\n".join([f"- {criteria}" for criteria in additional_criteria])
            additional_context = f"""
            
         ADDITIONAL SIGNIFICANCE CRITERIA:
         After finding keyword matches, ALL of the following criteria MUST ALSO BE MET for the message to remain classified as SIGNIFICANT:
         {criteria_text}
         
         If the message matches significant keywords but fails ANY of the additional criteria above, classify it as Trivial.
            """
         
         prompt = f"""
         Analyze the following message and determine if it is significant based on the provided significant keywords list.

         SIGNIFICANT KEYWORDS/TOPICS: {', '.join(significant_keywords_list) if significant_keywords_list else 'None provided'}

         STRICT CLASSIFICATION RULES:
         1. The message is ONLY significant if it directly relates to, discusses, or has contextual meaning similar to ONE OR MORE of the provided SIGNIFICANT keywords
         2. Be precise - do not classify as significant unless you can clearly identify which specific significant keyword(s) the message relates to
         3. If you classify as Significant, you MUST identify which specific keyword from the significant list best matches the message context. Return the keyword IN ENGLISH regardless of the original language.{additional_context}

         Your response format:
         - If Significant: "Significant: [specific keyword from the significant list that best matches - ALWAYS IN ENGLISH]"
         - If Trivial: "Trivial"

         Message to analyze: "{message}"

         Remember: Only classify as Significant if the message clearly relates to one of the specific significant keywords provided{"" if not additional_context else " AND meets all additional criteria"}. Always return the matched keyword in English.
         """

         response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[{"role": "system", "content": "You are an intelligence analyst. Classify messages as significant only if they clearly relate to the provided significant keywords and meet all additional criteria when specified."},
                        {"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=0.2  # Lower temperature for more consistent and conservative analysis
         )

         if response.choices[0] and response.choices[0].message.content:
            answer = response.choices[0].message.content.strip()
            
            if answer.startswith("Significant:"):
               # Extract the matched keyword from the response (should already be in English per prompt instructions)
               matched_keyword = answer.replace("Significant:", "").strip()
               LOGGER.writeLog(f'OpenAIProcessor: AI classified as Significant with keyword: {matched_keyword}')
               return True, [matched_keyword], "ai_contextual_analysis"
               
            elif answer == "Trivial":
               LOGGER.writeLog(f'OpenAIProcessor: AI classified as Trivial')
               return False, [], "ai_contextual_analysis"
         
         # Default to trivial if no clear response
         LOGGER.writeLog(f'OpenAIProcessor: Unable to classify message using AI contextual analysis, defaulting to Trivial')
         return False, [], "ai_contextual_default"
         
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
                  "significant_keywords_count": len(significant_keywords_list),
                  "enhanced_filtering": use_enhanced_filtering
               }
            )
         except Exception as admin_error:
            LOGGER.writeLog(f"Failed to send AI analysis error to admin: {admin_error}")
         
         return False, [], "ai_contextual_error"


   def _checkAdditionalCriteria(self, message, additional_criteria, country_config=None):
      """
      Check if a message meets additional AI criteria after finding significant keyword matches.
      This is used as a refinement filter to ensure messages are truly relevant to the target country.
      
      Args:
          message (str): The message text to analyze
          additional_criteria (list): List of criteria that must ALL be met
          country_config (dict): Optional country-specific configuration
          
      Returns:
          tuple: (meets_criteria, failed_criteria, reason)
      """
      try:
         if not additional_criteria or len(additional_criteria) == 0:
            LOGGER.writeLog('OpenAIProcessor: No additional criteria provided, message passes by default')
            return True, None, "no_additional_criteria"
         
         country_name = "the target country"
         if country_config:
            country_name = country_config.get('name', 'the target country')
         
         LOGGER.writeLog(f'OpenAIProcessor: Checking message against {len(additional_criteria)} additional criteria for {country_name}')
         
         # Build criteria context
         criteria_text = "\n".join([f"- {criteria}" for criteria in additional_criteria])
         
         prompt = f"""
         Analyze the following message to determine if it meets ALL of the additional significance criteria listed below.

         TARGET COUNTRY: {country_name}
         
         ADDITIONAL CRITERIA (ALL must be satisfied for the message to remain significant):
         {criteria_text}

         ANALYSIS INSTRUCTIONS:
         1. Read the message carefully and understand its context
         2. Check if the message satisfies ALL of the criteria above
         3. Be precise - the message must meet EVERY criteria to pass
         4. Consider the geographic context and relevance to {country_name}

         MESSAGE TO ANALYZE: "{message}"

         RESPONSE FORMAT:
         - If meets ALL criteria: "PASS"
         - If fails any criteria: "FAIL: [briefly explain which criteria failed]"

         Remember: ALL criteria must be satisfied for the message to pass. If even one criteria is not met, respond with FAIL.
         """

         response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[{"role": "system", "content": "You are a precise content analyst. A message must meet ALL additional criteria to pass. Be thorough and strict in your evaluation."},
                        {"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=0.2  # Very low temperature for consistent criteria checking
         )

         if response.choices[0] and response.choices[0].message.content:
            answer = response.choices[0].message.content.strip()
            
            if answer == "PASS":
               LOGGER.writeLog(f'OpenAIProcessor: Message meets all additional criteria')
               return True, None, "ai_criteria_passed"
               
            elif answer.startswith("FAIL:"):
               # Extract the failed criteria explanation
               failed_reason = answer.replace("FAIL:", "").strip()
               LOGGER.writeLog(f'OpenAIProcessor: Message failed additional criteria: {failed_reason}')
               return False, failed_reason, "ai_criteria_failed"
         
         # Default to fail if no clear response (conservative approach)
         LOGGER.writeLog(f'OpenAIProcessor: Unable to determine criteria status, defaulting to FAIL')
         return False, "unclear_response", "ai_criteria_default"
         
      except Exception as e:
         LOGGER.writeLog(f'OpenAIProcessor: _checkAdditionalCriteria - Exception: {e}')
         
         # Send critical exception to admin for criteria checking failures
         try:
            from .teams_utils import send_critical_exception
            send_critical_exception(
               "OpenAICriteriaCheckError",
               str(e),
               "OpenAIProcessor._checkAdditionalCriteria",
               additional_context={
                  "message_length": len(message) if message else 0,
                  "criteria_count": len(additional_criteria) if additional_criteria else 0,
                  "country_name": country_name,
                  "model": self.openai_model
               }
            )
         except Exception as admin_error:
            LOGGER.writeLog(f"Failed to send criteria check error to admin: {admin_error}")
         
         # On error, default to fail (conservative approach)
         return False, "technical_error", "ai_criteria_error"


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