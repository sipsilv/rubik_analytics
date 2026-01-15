import logging
import json
from .db import ensure_schema, get_eligible_news, insert_enriched_news, mark_failed
from ..ai_enrichment_config_manager import get_active_enrichment_config
from ..ai_connection_manager import get_ai_adapter_for_connection
from .config import BATCH_SIZE

logger = logging.getLogger(__name__)

class AIEnrichmentProcessor:
    def __init__(self):
        self.active_config = None
        self.adapter = None

    def refresh_config(self):
        """Reload active configuration and adapter."""
        try:
            self.active_config = get_active_enrichment_config()
            if not self.active_config:
                logger.warning("No active AI enrichment configuration found.")
                self.adapter = None
                return False
            
            self.adapter = get_ai_adapter_for_connection(self.active_config["connection_id"])
            if not self.adapter:
                logger.error(f"Failed to initialize adapter for connection {self.active_config['connection_id']}")
                return False
            
            # Use model from config if specified, otherwise adapter uses connection default
            if self.active_config.get("model_name"):
                self.adapter.model = self.active_config["model_name"]
                
            return True
        except Exception as e:
            logger.error(f"Error refreshing AI config: {e}")
            return False

    def process_batch(self, limit=BATCH_SIZE):
        """Process a batch of eligible news."""
        if not self.refresh_config():
            return 0

        eligible_news = get_eligible_news(limit=limit)
        if not eligible_news:
            return 0

        count = 0
        for news_item in eligible_news:
            # news_item schema: news_id, received_date, combined_text, original_url
            news_id, received_date, text, original_url = news_item
            
            try:
                import time
                start_time = time.time()
                enriched_data = self.enrich_news(text)
                latency_ms = int((time.time() - start_time) * 1000)

                if enriched_data:
                    insert_enriched_news(
                        news_id=news_id,
                        received_date=received_date,
                        ai_data=enriched_data,
                        ai_model=self.adapter.model,
                        ai_config_id=self.active_config["config_id"],
                        latency_ms=latency_ms,
                        original_url=original_url
                    )
                    count += 1
                    logger.info(f"Successfully enriched news_id {news_id} in {latency_ms}ms")
                else:
                    mark_failed(news_id, "AI returned empty or invalid data")
            except Exception as e:
                logger.error(f"Failed to enrich news_id {news_id}: {e}")
                mark_failed(news_id, str(e))
                
        return count

    def enrich_news(self, text):
        """Call AI to enrich news text with retries."""
        if not self.adapter or not self.active_config:
            return None

        prompt_template = self.active_config["prompt_text"]
        prompt = prompt_template.replace("{{COMBINED_TEXT}}", text)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # The adapter is expected to return a dict (parsed JSON)
                return self.adapter.process(prompt)
            except Exception as e:
                logger.warning(f"AI enrichment attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"AI enrichment failed after {max_retries} attempts.")
                    return None
                import time
                time.sleep(2 ** attempt) # Exponential backoff
        
        return None

def run_once():
    """Helper to run one batch from CLI or worker."""
    ensure_schema()
    processor = AIEnrichmentProcessor()
    return processor.process_batch()
