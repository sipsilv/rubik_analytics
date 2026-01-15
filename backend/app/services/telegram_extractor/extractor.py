import re
import requests
import hashlib
import os
import logging
from bs4 import BeautifulSoup
from PIL import Image
import pytesseract
import io
import json
from .config import LINK_CACHE_DIR, OCR_CACHE_DIR, REQ_HEADERS

logger = logging.getLogger(__name__)

# Compile Regex
URL_REGEX = r'(https?://\S+)'

def extract_urls(text):
    """
    Finds all URLs in a text string.
    """
    if not text:
        return []
    return re.findall(URL_REGEX, text)

def get_cache_path(directory, key):
    """
    Generates a file path for a cache key (md5 hash).
    """
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    hashed = hashlib.md5(key.encode('utf-8')).hexdigest()
    return os.path.join(directory, f"{hashed}.txt")

def scrape_url(url):
    """
    Scrapes the content of a URL. Returns text content.
    Uses disk caching to avoid hitting the same URL multiple times.
    """
    try:
        cache_path = get_cache_path(LINK_CACHE_DIR, url)
        
        # Check Cache
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        # Fetch
        logger.info(f"Scraping URL: {url}")
        resp = requests.get(url, headers=REQ_HEADERS, timeout=10)
        resp.raise_for_status()
        
        # Parse
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # Remove scripts and styles
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Limit length to avoid DB bloat
        clean_text = clean_text[:5000] 
        
        # Save to Cache
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write(clean_text)
            
        return clean_text
        
    except Exception as e:
        logger.warning(f"Failed to scrape {url}: {e}")
# Global Tesseract Check
TESSERACT_AVAILABLE = False

def check_tesseract():
    global TESSERACT_AVAILABLE
    
    # 1. Check if configured in PATH
    try:
        pytesseract.get_tesseract_version()
        logger.info("Tesseract found in PATH.")
        TESSERACT_AVAILABLE = True
        return
    except:
        pass
        
    # 1a. Check ENV Variable
    env_path = os.getenv("TESSERACT_PATH")
    if env_path and os.path.exists(env_path):
        pytesseract.pytesseract.tesseract_cmd = env_path
        logger.info(f"Tesseract found via ENV at {env_path}")
        TESSERACT_AVAILABLE = True
        return

    # 2. Check common Windows paths
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"c:\Users\jallu\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            try:
                pytesseract.get_tesseract_version()
                logger.info(f"Tesseract found at {path}")
                TESSERACT_AVAILABLE = True
                return
            except:
                continue
                
    # 3. Not found
    TESSERACT_AVAILABLE = False
    logger.warning("Tesseract OCR not found in PATH or standard locations. OCR features disabled.")

# Run check on module load
check_tesseract()

def ocr_image(file_id, image_data=None, image_path=None):
    """
    Performs OCR on an image.
    Args:
        file_id: Unique ID for caching.
        image_data: Bytes of the image.
        image_path: Path to image file.
    """
    if not TESSERACT_AVAILABLE:
        return ""

    try:
        cache_path = get_cache_path(OCR_CACHE_DIR, file_id)
        
        # Check Cache
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        # Load Image
        image = None
        if image_data:
            image = Image.open(io.BytesIO(image_data))
        elif image_path:
            image = Image.open(image_path)
            
        if not image:
            return ""
            
        logger.info(f"Performing OCR on {file_id}")
        text = pytesseract.image_to_string(image)
        
        # Save to Cache
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write(text)
            
        return text
        
    except Exception as e:
        logger.warning(f"OCR Failed for {file_id}: {e}")
        return ""
        
    except Exception as e:
        logger.error(f"OCR Failed for {file_id}: {e}")
        return ""
