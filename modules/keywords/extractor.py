import re
from collections import Counter
from typing import Dict, List, Tuple, Any


class KeywordExtractor:
    """
    Extracts unigrams, bigrams, and trigrams from page contents
    using statistical and algorithmic text processing (Non-AI).
    """

    # رایج‌ترین Stop Words (کلمات اضافه‌ای که ارزش سئو ندارند - قابل توسعه برای فارسی و انگلیسی)
    DEFAULT_STOP_WORDS = {
        # فارسی
        "و", "در", "به", "از", "که", "این", "را", "با", "است", "لذا", "برای",
        "آن", "یک", "شود", "شد", "خود", "ها", "های", "تا", "کرد", "بر", "اما",
        "داره", "شده", "بود", "است", "ای", "تو", "ما", "شما", "آن‌ها", "من",
        # انگلیسی (در صورت وجود محتوای انگلیسی)
        "the", "and", "to", "of", "a", "in", "is", "it", "you", "that",
        "he", "was", "for", "on", "are", "with", "as", "i", "his", "they"
    }

    def __init__(self, stop_words: set = None, min_word_length: int = 2):
        self.stop_words = stop_words if stop_words is not None else self.DEFAULT_STOP_WORDS
        self.min_word_length = min_word_length

    def clean_and_tokenize(self, text: str) -> List[str]:
        """
        Cleans text, removes punctuation/numbers/stop words, and returns tokens.
        """
        if not text or not isinstance(text, str):
            return []

        # تبدیل به حروف کوچک (برای زبان‌های لاتین؛ روی فارسی بی‌تأثیر است)
        text = text.lower()

        # حذف کاراکترهای خاص و ارقام، حفظ حروف الفبا و فاصله (پشتیبانی از حروف فارسی و انگلیسی)
        # الگو کاراکترهای متداول الفبای فارسی و انگلیسی را نگه می‌دارد
        cleaned_text = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', text)

        # تقسیم متن به کلمات بر اساس فاصله
        tokens = cleaned_text.split()

        # فیلتر کردن کلمات کوتاه و Stop Words
        filtered_tokens = [
            token.strip() for token in tokens
            if len(token.strip()) >= self.min_word_length and token.strip() not in self.stop_words
        ]

        return filtered_tokens

    def extract_ngrams(self, tokens: List[str], n: int) -> List[str]:
        """
        Generates n-grams from a list of tokens.
        """
        if len(tokens) < n:
            return []
        
        return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]

    def extract_page_keywords(self, text_content: str) -> Dict[str, Dict[str, Any]]:
        """
        Extracts unigrams, bigrams, and trigrams with their raw frequencies for a single page.
        """
        tokens = self.clean_and_tokenize(text_content)

        unigrams = self.extract_ngrams(tokens, 1)
        bigrams = self.extract_ngrams(tokens, 2)
        trigrams = self.extract_ngrams(tokens, 3)

        # محاسبه فراوانی (Frequency)
        unigram_counts = Counter(unigrams)
        bigram_counts = Counter(bigrams)
        trigram_counts = Counter(trigrams)

        return {
            "unigrams": dict(unigram_counts),
            "bigrams": dict(bigram_counts),
            "trigrams": dict(trigram_counts),
            "total_tokens": len(tokens)
        }

    def extract_run_keywords(self, page_contents_list: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """
        Processes a list of page contents (retrieved from PageContentRepository)
        and extracts keywords for each page while maintaining page ID relationships.
        """
        results = {}

        for page_item in page_contents_list:
            page_id = page_item.get("page_id")
            text_content = page_item.get("text_content", "")

            if not page_id:
                continue

            page_keywords = self.extract_page_keywords(text_content)
            results[page_id] = {
                "url": page_item.get("url"),
                "analysis_run_id": page_item.get("analysis_run_id"),
                **page_keywords
            }

        return results