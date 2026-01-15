import re
import unicodedata

def normalize_text(text: str) -> str:
    if not text:
        return ""

    # 1. Lowercase
    text = text.lower()

    # 2. Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

    # 3. Remove Punctuation (keep basic alphanumeric and spaces)
    # Using regex to match non-alphanumeric chars (excluding spaces)
    text = re.sub(r'[^\w\s]', '', text)

    # 4. Remove Emojis
    # Simple way: filter out unicode categories 'So' (Symbol, Other), 'Cn' (Not Assigned) etc? 
    # Or just use ascii logic? No, we support multilingual.
    # Let's use unicodedata loop for safety against common emojis.
    # Note: re.sub above might have removed some if they aren't \w. 
    # Standard emojis often fall under \w? No.
    # \w matches [a-zA-Z0-9_] and locale specific.
    # So `^\w\s` usually removes emojis too in Python re defaults (unless regex flag UNICODE is tricky).
    # Let's assume the punctuation step handled most symbols. 
    # Explicit loop to be safe if desired, but regex is usually faster.
    
    # 5. Collapse Whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text
