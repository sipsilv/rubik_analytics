import time
import logging
from .db import ensure_schema, get_db, insert_raw_result, mark_extracted
from .extractor import extract_urls, scrape_url, ocr_image
from .normalizer import normalize_text
import os
from .config import BATCH_SIZE

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TelegramExtractionWorker")

def process_batch():
    db = get_db()
    try:
        # Fetch unextracted rows
        # Columns: listing_id, telegram_chat_id, telegram_msg_id, source_handle, message_text, caption_text, media_type, has_media, file_id, file_name, urls, received_at
        query = f"""
            SELECT listing_id, telegram_chat_id, telegram_msg_id, source_handle, 
                   message_text, caption_text, media_type, has_media, file_id, file_path, received_at
            FROM telegram_listing 
            WHERE is_extracted = FALSE 
            ORDER BY received_at ASC 
            LIMIT {BATCH_SIZE}
        """
        rows = db.run_listing_query(query, fetch='all')
    except Exception as e:
        logger.error(f"Error fetching batch: {e}")
        return 0

    if not rows:
        return 0

    success_count = 0
    for row in rows:
        # Unpack
        (listing_id, chat_id, msg_id, handle, 
         msg_text, cap_text, media_type, has_media, file_id, file_path, received_at) = row
        
        try:
            # 1. Text Extraction
            telegram_text = (msg_text or "")
            caption_text = (cap_text or "")
            full_source_text = f"{telegram_text} {caption_text}"
            
            # 2. Link Extraction & Scraping
            found_urls = extract_urls(full_source_text)
            link_texts = []
            for url in found_urls:
                scraped = scrape_url(url)
                if scraped:
                    link_texts.append(scraped)
            link_text_combined = " ".join(link_texts)

            # 3. OCR (Image only)
            image_ocr_text = ""
            if has_media and media_type == 'image' and file_path and os.path.exists(file_path):
                try:
                    with open(file_path, "rb") as f:
                        img_bytes = f.read()
                    image_ocr_text = ocr_image(file_id or "local", image_data=img_bytes)
                except Exception as e:
                    logger.error(f"Failed to read image for OCR: {e}")

            # 4. Combine
            combined_parts = [
                telegram_text,
                caption_text,
                link_text_combined,
                image_ocr_text
            ]
            combined_text = " ".join([p for p in combined_parts if p]).strip()

            # 5. Normalize
            norm_text = normalize_text(combined_text)

            # 6. Write to Output
            out_data = {
                'listing_id': listing_id,
                'telegram_chat_id': chat_id,
                'telegram_msg_id': msg_id,
                'source_handle': handle,
                'telegram_text': telegram_text,
                'caption_text': caption_text,
                'link_text': link_text_combined,
                'image_ocr_text': image_ocr_text,
                'combined_text': combined_text,
                'normalized_text': norm_text,
                'file_id': file_id, # critical for deduplication of media
                'received_at': received_at
            }
            insert_raw_result(out_data)

            # 7. Mark Extracted
            mark_extracted(listing_id)
            success_count += 1
            
        except Exception as e:
            logger.error(f"Failed to process listing_id {listing_id}: {e}")
            # Continue to next row, do NOT crash
            
    return success_count

def run_worker():
    logger.info("Starting Telegram Extraction Worker...")
    ensure_schema()
    logger.info("Schema verified.")
    
    while True:
        try:
            count = process_batch()
            if count == 0:
                time.sleep(5) # Idle wait
            else:
                logger.info(f"Processed {count} items.")
        except Exception as e:
            logger.error(f"Worker Loop Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_worker()
