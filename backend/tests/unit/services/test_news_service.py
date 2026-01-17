import pytest
from app.services.news_service import NewsService
from tests.mocks.mock_content_repositories import MockNewsRepository

class TestNewsService:
    @pytest.fixture
    def service(self):
        service = NewsService()
        service.repo = MockNewsRepository()
        return service

    def test_fetch_news(self, service):
        # Insert mock data
        service.repo.insert_news(None, {"title": "Test News", "source": "Reuters"})
        
        news, total = service.get_latest_news(limit=5)
        assert total == 1
        assert news[0]["title"] == "Test News"

    def test_empty_news(self, service):
        news, total = service.get_latest_news()
        assert total == 0
        assert news == []
