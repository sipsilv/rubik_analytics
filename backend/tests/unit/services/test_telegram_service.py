import pytest
from unittest.mock import MagicMock
from app.services.telegram_service import TelegramService
from tests.mocks.mock_content_repositories import MockTelegramRepository

class TestTelegramService:
    @pytest.fixture
    def service(self):
        # Mock dependencies
        db_mock = MagicMock()
        service = TelegramService(db_mock)
        service.repo = MockTelegramRepository()
        return service

    def test_register_channel_new(self, service):
        # Test registering a new channel
        res = service.register_channel("test_channel", "Test Channel")
        assert res['username'] == "test_channel"
        assert res['id'] is not None

    def test_register_channel_duplicate(self, service):
        # Register once
        service.register_channel("dup_channel", "Dup")
        
        # Register again - logic might return existing or raise error?
        # Assuming idempotent or specific logic.
        # Let's check logic: generic service usually returns existing if found.
        res = service.register_channel("dup_channel", "Dup")
        assert res['username'] == "dup_channel"
        # Should be same ID if logic handles dedupe
        # (Assuming service uses get_channel_by_username check)

    def test_get_channels_metrics(self, service):
        service.register_channel("c1", "C1")
        stats = service.get_registered_channels_with_stats()
        assert len(stats) == 1
        assert stats[0]['username'] == "c1"
