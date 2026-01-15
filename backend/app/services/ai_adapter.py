import json
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AIAdapter:
    def __init__(self, api_key: str, base_url: Optional[str] = None, model: Optional[str] = None, timeout: int = 120):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def process(self, prompt: str) -> Dict[str, Any]:
        """Process the prompt and return the enriched data."""
        raise NotImplementedError("Subclasses must implement process()")

class OpenAIAdapter(AIAdapter):
    def process(self, prompt: str) -> Dict[str, Any]:
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model or "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            content = data['choices'][0]['message']['content']
            return json.loads(content)
        except Exception as e:
            logger.error(f"OpenAI Processing Error: {e}")
            raise

class GeminiAdapter(AIAdapter):
    def process(self, prompt: str) -> Dict[str, Any]:
        # Simple implementation for Gemini API via REST
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model or 'gemini-1.5-flash'}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json"
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            content = data['candidates'][0]['content']['parts'][0]['text']
            # Clean up potential markdown code blocks if AI didn't follow mime_type strictly
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()
            return json.loads(content)
        except Exception as e:
            logger.error(f"Gemini Processing Error: {e}")
            raise

class OllamaAdapter(AIAdapter):
    def process(self, prompt: str) -> Dict[str, Any]:
        url = self.base_url or "http://localhost:11434/api/generate"
        
        # Ensure url ends with /api/generate if using Ollama
        if "/api/generate" not in url:
            if url.endswith("/"):
                url += "api/generate"
            else:
                url += "/api/generate"

        payload = {
            "model": self.model or "llama3",
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return json.loads(data['response'])
        except Exception as e:
            logger.error(f"Ollama Processing Error for {url}: {e}")
            raise

def get_adapter(provider: str, **kwargs) -> AIAdapter:
    provider = provider.upper()
    if provider == "OPENAI":
        return OpenAIAdapter(**kwargs)
    elif provider == "GEMINI":
        return GeminiAdapter(**kwargs)
    elif provider == "OLLAMA":
        return OllamaAdapter(**kwargs)
    else:
        # Generic OpenAI-compatible adapter for others (Perplexity, groq, etc)
        return OpenAIAdapter(**kwargs)
