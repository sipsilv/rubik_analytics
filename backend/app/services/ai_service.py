"""
AI Service Abstraction Layer
Provides a modular interface for AI-powered feature request analysis.
Easily swappable between different AI providers (OpenAI, Anthropic, etc.)
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import os

class AIServiceInterface(ABC):
    """Abstract interface for AI services"""
    
    @abstractmethod
    async def analyze_feature_request(
        self, 
        description: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a feature request and return structured analysis.
        
        Returns:
            {
                "summary": str,
                "category": str,  # UI, Backend, Performance, Analytics, Security
                "complexity": str,  # Low, Medium, High
                "impacted_modules": list[str],
                "suggested_steps": list[str]
            }
        """
        pass

class MockAIService(AIServiceInterface):
    """
    Mock AI Service for development/testing.
    Returns structured analysis without calling external APIs.
    """
    
    async def analyze_feature_request(
        self, 
        description: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate mock AI analysis based on keywords in description"""
        
        description_lower = description.lower()
        
        # Determine category
        if any(word in description_lower for word in ['ui', 'interface', 'button', 'page', 'design', 'layout']):
            category = "UI"
        elif any(word in description_lower for word in ['api', 'database', 'backend', 'server', 'endpoint']):
            category = "Backend"
        elif any(word in description_lower for word in ['slow', 'performance', 'speed', 'optimize', 'cache']):
            category = "Performance"
        elif any(word in description_lower for word in ['chart', 'graph', 'analytics', 'report', 'dashboard', 'data']):
            category = "Analytics"
        elif any(word in description_lower for word in ['security', 'auth', 'permission', 'access', 'encrypt']):
            category = "Security"
        else:
            category = "UI"  # Default
        
        # Determine complexity
        word_count = len(description.split())
        if word_count < 20:
            complexity = "Low"
        elif word_count < 50:
            complexity = "Medium"
        else:
            complexity = "High"
        
        # Generate summary
        summary = f"Feature request for: {description[:100]}{'...' if len(description) > 100 else ''}"
        
        # Determine impacted modules
        modules = []
        if category == "UI":
            modules = ["frontend/components", "frontend/app"]
        elif category == "Backend":
            modules = ["backend/app/api", "backend/app/models"]
        elif category == "Analytics":
            modules = ["frontend/app/(main)/analytics", "backend/app/api/v1"]
        else:
            modules = ["Multiple modules"]
        
        # Generate suggested steps
        steps = [
            f"1. Analyze requirements for {category.lower()} changes",
            f"2. Design implementation approach",
            f"3. Create necessary components/models",
            f"4. Implement core functionality",
            f"5. Add tests and documentation",
            f"6. Review and deploy"
        ]
        
        return {
            "summary": summary,
            "category": category,
            "complexity": complexity,
            "impacted_modules": modules,
            "suggested_steps": steps
        }

class OpenAIService(AIServiceInterface):
    """
    OpenAI-based AI Service.
    Requires OPENAI_API_KEY environment variable.
    """
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
    
    async def analyze_feature_request(
        self, 
        description: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze feature request using OpenAI API"""
        try:
            import openai
            
            client = openai.OpenAI(api_key=self.api_key)
            
            context_str = ""
            if context:
                context_str = f"\nContext: Page={context.get('page', 'N/A')}, Module={context.get('module', 'N/A')}"
            
            prompt = f"""Analyze the following feature request and provide a structured analysis in JSON format.

Feature Request: {description}{context_str}

Provide analysis in this exact JSON format:
{{
    "summary": "Brief summary of the feature request",
    "category": "One of: UI, Backend, Performance, Analytics, Security",
    "complexity": "One of: Low, Medium, High",
    "impacted_modules": ["module1", "module2"],
    "suggested_steps": ["step1", "step2", "step3"]
}}

Return ONLY valid JSON, no additional text."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Using cost-effective model
                messages=[
                    {"role": "system", "content": "You are a technical analyst that provides structured feature request analysis. Always return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            analysis = json.loads(content)
            
            # Validate and ensure all required fields
            return {
                "summary": analysis.get("summary", "Feature request analysis"),
                "category": analysis.get("category", "UI"),
                "complexity": analysis.get("complexity", "Medium"),
                "impacted_modules": analysis.get("impacted_modules", []),
                "suggested_steps": analysis.get("suggested_steps", [])
            }
            
        except Exception as e:
            # Fallback to mock service on error
            print(f"OpenAI service error: {e}")
            mock_service = MockAIService()
            return await mock_service.analyze_feature_request(description, context)

def get_ai_service() -> AIServiceInterface:
    """
    Factory function to get the appropriate AI service.
    Checks environment variables to determine which service to use.
    """
    # Check for OpenAI API key
    if os.getenv("OPENAI_API_KEY"):
        try:
            return OpenAIService()
        except Exception as e:
            print(f"Failed to initialize OpenAI service: {e}, falling back to MockAIService")
            return MockAIService()
    
    # Default to mock service for development
    return MockAIService()
