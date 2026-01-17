import pytest
from unittest.mock import MagicMock
from app.services.announcements_service import AnnouncementsService
from tests.mocks.mock_market_repositories import MockAnnouncementsRepository

class TestAnnouncementsService:
    @pytest.fixture
    def service(self):
        service = AnnouncementsService()
        # We need to ensure service uses the mocked repo.
        # Service instantiates repo in __init__.
        service.repo = MockAnnouncementsRepository() 
        # MockAnnouncementsRepository from previous step needs `insert_announcement` method matching interface?
        # Let's check `mock_market_repositories.py` content from previous turn...
        # It had `self.announcements = []`.
        # We likely need to add methods to the Mock if they weren't fully fleshed out.
        
        # Defining methods dynamically for the test if the class was thin
        service.repo.insert_announcement = lambda x: (service.repo.announcements.append(x) or True)
        service.repo.get_announcements = lambda **k: (service.repo.announcements, len(service.repo.announcements))
        service.repo.get_announcement = lambda id: next((a for a in service.repo.announcements if a.get('id')==id), None)
        
        return service

    def test_insert_and_retrieve(self, service):
        data = {"id": "1", "title": "Div Declaration", "symbol": "TCS"}
        service.insert_announcement(data)
        
        items, total = service.get_announcements()
        assert total == 1
        assert items[0]['symbol'] == "TCS"
        
    def test_get_by_id(self, service):
        service.insert_announcement({"id": "100", "title": "X"})
        item = service.get_announcement_by_id("100")
        assert item is not None
        assert item['title'] == "X"
