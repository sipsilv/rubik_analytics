import pytest
from app.services.ai_enrichment_config_manager import AIEnrichmentConfigManager

class TestAIEnrichmentConfigManager:
    @pytest.fixture
    def manager(self):
        return AIEnrichmentConfigManager("tests/mocks/dummy_config.json")

    def test_default_config(self, manager):
        # Should load defaults if file missing
        cfg = manager.get_config()
        assert isinstance(cfg, dict)
        assert "providers" in cfg

    def test_update_config(self, manager):
        manager.update_config("providers", {"openai": "key"})
        cfg = manager.get_config()
        assert cfg["providers"]["openai"] == "key"
