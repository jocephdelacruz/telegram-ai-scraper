# Translation Feature Usage Guide

## Overview

The Telegram AI Scraper now supports automatic translation of non-English messages. Here's how the new functionality works:

## How Translation Works

1. **Automatic Detection**: When a message is received, the system first checks if it's in English using smart heuristics
2. **Cost-Effective Processing**: If the text appears to be English (contains common English words and no non-Latin characters), it skips the AI translation step
3. **AI Translation**: For non-English text, a single OpenAI API call detects the language and provides an English translation
4. **Analysis on English Text**: All significance analysis (keywords and AI reasoning) is performed on the English text
5. **Dual Storage**: Both original and translated text are stored for reference

## New Excel Fields

The following fields have been added to the Excel output:

- **Original_Text**: The original message text before any translation
- **Original_Language**: The detected language of the original message (e.g., "Arabic", "French")
- **Was_Translated**: Boolean (TRUE/FALSE) indicating if translation was performed
- **Message_Text**: Contains the English text (either translated or original if already English)

## Teams Notifications

Teams alerts now show enhanced information for translated messages:

- **Translation Status**: Indicates if the message was translated
- **Original Language**: Shows the detected source language
- **Dual Content**: Displays both the English translation and a snippet of the original text
- **Original Text Section**: Shows the original text in its native language (truncated for readability)

## Cost Optimization Features

1. **Heuristic Pre-filtering**: Checks for common English words and character patterns before using AI
2. **Single API Call**: Combines language detection and translation in one OpenAI request
3. **Smart Caching**: Avoids repeated translation attempts for obviously English content

## Testing the Feature

You can test the translation feature using the provided test script:

```bash
cd /home/ubuntu/TelegramScraper/telegram-ai-scraper
python3 test_translation.py
```

This will test various message types including:
- English text (should not be translated)
- Arabic text (should be translated)
- French text (should be translated)
- Mixed content

## Supported Languages

The system can handle any language supported by OpenAI, including:

- **Arabic**: أخبار عاجلة
- **French**: Nouvelles de dernière minute
- **Spanish**: Noticias de última hora
- **German**: Eilmeldungen
- **Chinese**: 突发新闻
- **Russian**: Срочные новости
- **And many more...**

## Configuration

No additional configuration is required. The translation feature uses your existing OpenAI API key and is automatically enabled for all processed messages.

## Performance Impact

- **Minimal for English Text**: Heuristic checks add negligible processing time
- **Single API Call for Non-English**: Uses same OpenAI budget as significance analysis
- **Improved Accuracy**: Keyword filtering works better on translated English text
- **Better Coverage**: Can now process messages from Arabic, Asian, and European channels

## Monitoring

Translation activities are logged in the OpenAI log file (`logs/openai.log`):
- Language detection results
- Translation attempts
- Heuristic filtering decisions
- API call optimization

## Example Output

### Before (English message):
```
Message_Text: "Breaking news: Major earthquake hits region"
Original_Text: "Breaking news: Major earthquake hits region"
Original_Language: "English"
Was_Translated: FALSE
```

### After (Arabic message):
```
Message_Text: "Breaking news: Major earthquake hits region"
Original_Text: "أخبار عاجلة: زلزال كبير يضرب المنطقة"
Original_Language: "Arabic"
Was_Translated: TRUE
```