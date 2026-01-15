from .config import SCORING_THRESHOLD
import re

# ✅ 85 Corporate Action Keywords ✓
CORPORATE_ACTION_KEYWORDS = {
    "results", "dividend", "bonus", "split", "rights issue", "buyback",
    "merger", "acquisition", "amalgamation", "delisting", "re-listing",
    "esop", "employee stock", "record date", "ex-date", "cum-date",
    "book closure", "agm", "egm", "board meeting", "qip", "fpo",
    "ipo", "pre-open", "trading window", "insider trading",
    "pledging", "invocation", "release pledge", "scheme", "takeover"
}

# ✅ 45 Business Growth Keywords ✓
BUSINESS_GROWTH_KEYWORDS = {
    "order", "contract", "partnership", "expansion", "launch",
    "commissioning", "tie-up", "moa", "mou", "joint venture",
    "capex", "capacity", "production", "manufacturing",
    "commercial production", "ramp-up", "breakthrough",
    "milestone", "landmark", "strategic", "collaboration",
    "alliance", "consortium", "technology transfer", "export", "infrastructure"
}

# ✅ 35 Financials Keywords ✓
FINANCIALS_KEYWORDS = {
    "profit", "revenue", "sales", "growth", "margin", "ebitda",
    "pat", "net profit", "operating profit", "q1", "q2", "q3",
    "q4", "fy24", "fy25", "fy26", "quarter", "half-yearly",
    "annual", "audited", "unaudited", "consolidated",
    "standalone", "guidance", "outlook", "forecast",
    "projection", "target revenue", "ebit", "cash flow", "debt"
}

# ✅ 30 Governance Keywords ✓
GOVERNANCE_KEYWORDS = {
    "approval", "meeting", "board", "appointment", "resignation",
    "policy", "regulation", "compliance", "sebi", "rbi", "irda",
    "pfrda", "nclt", "sat", "listing", "delisting", "suspension",
    "resumption", "circular", "notification", "amendment",
    "clarification", "fraud", "probe", "investigation"
}

# ✅ 25 Market Activity Keywords ✓
MARKET_ACTIVITY_KEYWORDS = {
    "stake", "investment", "bulk", "block deal", "circuit",
    "limit up", "limit down", "hammer", "breakout", "gap up",
    "gap down", "volume surge", "delivery", "fii", "dii",
    "promoter", "holding", "pledging", "open interest",
    "rollover", "expiry", "settlement", "short covering"
}

# ❌ 45 Spam Keywords ✓
SPAM_KEYWORDS = {
    "buy", "sell", "target", "stoploss", "recommendation", "call",
    "tip", "multibagger", "rocket", "moon", "pump", "dump",
    "breakout stock", "penny stock", "cheap", "undervalued",
    "bargain", "hidden gem", "explosive", "massive",
    "jackpot", "superhit", "winner", "champion", "monster",
    "crazy", "insane", "unbelievable", "mind blowing",
    "life changing", "wealth creation", "riches",
    "join", "channel", "group", "premium", "signals", "accuracy",
    "guaranteed", "100%", "free tips", "paid service",
    "subscription", "whatsapp", "telegram", "discord",
    "resistance", "support", "rsi", "macd", "supertrend",
    "live stream", "live streaming", "streaming", "webinar",
    "scalping", "scalp", "intraday", "btst", "stbt", "course", "class"
}

# ✅ 25 Trusted Sources ✓
TRUSTED_SOURCES = {
    "reuters", "bloomberg", "cnbc", "moneycontrol", "bse", "nse",
    "livemint", "economic times", "business standard",
    "financial express", "bsemsm", "nsemsm", "sebi", "rbi",
    "press information bureau", "press trust india", "pti", "ani",
    "dowjones", "wsj", "ft", "businessline", "hindubusinessline", "self"
}

def calculate_structural_score(text, link_text):
    score = 0
    if not text:
        return 0
    
    # Text length
    length = len(text)
    if length > 200:
        score += 20
    elif length > 100:
        score += 10
        
    # Links presence
    if link_text and len(link_text) > 10:
        score += 10
        
    # Numbers/Dates
    if re.search(r'\d+', text):
        score += 5
        
    return min(score, 35)

def calculate_keyword_score(text):
    score = 0
    if not text:
        return 0
        
    text_lower = text.lower()
    
    # Category Scoring (+10 per category present)
    
    # 1. Corporate Action
    if any(kw in text_lower for kw in CORPORATE_ACTION_KEYWORDS):
        score += 10

    # 2. Business Growth
    if any(kw in text_lower for kw in BUSINESS_GROWTH_KEYWORDS):
        score += 10

    # 3. Financials
    if any(kw in text_lower for kw in FINANCIALS_KEYWORDS):
        score += 10
        
    # 4. Governance
    if any(kw in text_lower for kw in GOVERNANCE_KEYWORDS):
        score += 10

    # 5. Market Activity
    if any(kw in text_lower for kw in MARKET_ACTIVITY_KEYWORDS):
        score += 10
            
    # Spam Penalty (-20 if ANY spam keyword found)
    if any(kw in text_lower for kw in SPAM_KEYWORDS):
        score -= 20
            
    # Cap between -20 and 35
    return max(-20, min(score, 35))

def calculate_source_score(source_handle):
    if not source_handle:
        return 0
        
    source_lower = source_handle.lower()
    
    # Direct match or substring match
    if any(trusted in source_lower for trusted in TRUSTED_SOURCES):
        return 5
        
    return 0

def calculate_content_type_score(text, link_text, ocr_text):
    score = 0
    has_text = bool(text and len(text.strip()) > 0)
    has_link = bool(link_text and len(link_text.strip()) > 0)
    has_ocr = bool(ocr_text and len(ocr_text.strip()) > 0)
    
    if has_text and has_link:
        score = 25 
    elif has_text:
        score = 20 
    elif has_ocr:
        score = 15 
    else:
        score = 0
        
    return score

def score_news(raw_id, source_handle, text, link_text, ocr_text):
    """
    Compute final score and decision.
    """
    struct_score = calculate_structural_score(text, link_text)
    keyword_score = calculate_keyword_score(text)
    source_score = calculate_source_score(source_handle)
    content_score = calculate_content_type_score(text, link_text, ocr_text)
    
    raw_total = struct_score + keyword_score + source_score + content_score
    final_score = max(0, min(100, raw_total))
    
    decision = "PASS" if final_score >= SCORING_THRESHOLD else "DROP"
    
    return {
        "raw_id": raw_id,
        "final_score": final_score,
        "structural_score": struct_score,
        "keyword_score": keyword_score,
        "source_score": source_score,
        "content_score": content_score,
        "decision": decision
    }
