import hashlib
from .config import JACCARD_THRESHOLD

def compute_hash(text, file_id=None):
    """
    Compute SHA256 hash of normalized text + file_id.
    """
    s = (text or "") + (file_id or "")
    if not s:
        return hashlib.sha256(b"").hexdigest()
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

def get_tokens(text):
    """
    Tokenize text for Jaccard similarity (set of words).
    """
    if not text:
        return set()
    return set(text.split())

def compute_jaccard_similarity(text1, text2):
    """
    Compute Jaccard similarity between two texts.
    """
    tokens1 = get_tokens(text1)
    tokens2 = get_tokens(text2)
    
    if not tokens1 and not tokens2:
        return 1.0  # Both empty
    if not tokens1 or not tokens2:
        return 0.0
        
    intersection = len(tokens1.intersection(tokens2))
    union = len(tokens1.union(tokens2))
    
    return intersection / union

def find_near_duplicate(current_text, candidates):
    """
    Find if current_text is similar to any candidate.
    candidates: list of (raw_id, text)
    Returns: duplicate_of_raw_id if found, else None.
    """
    current_tokens = get_tokens(current_text)
    if not current_tokens:
        return None
        
    for cand_id, cand_text in candidates:
        cand_tokens = get_tokens(cand_text)
        if not cand_tokens:
            continue
            
        intersection = len(current_tokens.intersection(cand_tokens))
        union = len(current_tokens.union(cand_tokens))
        
        similarity = intersection / union if union > 0 else 0.0
        
        if similarity >= JACCARD_THRESHOLD:
            return cand_id
            
    return None
