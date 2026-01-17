import pytest
import threading
from unittest.mock import MagicMock, patch
from app.services.screener_service import ScreenerService
from tests.mocks.mock_market_repositories import MockScreenerRepository

class TestScreenerService:
    @pytest.fixture
    def service(self):
        service = ScreenerService()
        service.repo = MockScreenerRepository()
        # Reset cache
        service._scraping_status_cache = {}
        service._active_threads = {}
        return service

    def test_clean_numeric_value(self, service):
        assert service.clean_numeric_value("1,000.50") == 1000.50
        assert service.clean_numeric_value("50 %") == 50.0
        assert service.clean_numeric_value("₹ 100") == 100.0
        assert service.clean_numeric_value(None) is None
        assert service.clean_numeric_value("Invalid") is None

    @patch("app.services.screener_service.requests.Session")
    def test_fetch_soup_success(self, mock_session, service):
        mock_resp = MagicMock()
        mock_resp.text = "<html><title>Test | Screener</title></html>"
        mock_resp.status_code = 200
        mock_session.return_value.get.return_value = mock_resp
        
        # Reset singleton session for test
        ScreenerService._session = None
        
        soup = service.fetch_soup("http://test.com")
        assert soup.title.text == "Test | Screener"

    def test_start_scraping_job_creation(self, service):
        # We Mock the repository's get_active_symbols to return valid symbols
        # process_scraping_async calls get_active_symbols
        # We want to test that start_scraping spawns a thread and updates cache
        
        job_id = "job_123"
        with patch.object(service, "process_scraping_async") as mock_process:
            service.start_scraping(job_id, "user")
            
            assert job_id in service._active_threads
            assert service._active_threads[job_id].is_alive
            # Wait for thread (mocked process usually runs instantly if not patched, 
            # here we patched the target so thread runs the mock)
        
    def test_get_status_from_cache(self, service):
        job_id = "job_cache"
        service._scraping_status_cache[job_id] = {"status": "PROCESSING", "percentage": 50}
        
        status = service.get_status(job_id)
        assert status["status"] == "PROCESSING"
        assert status["percentage"] == 50
    
    def test_parse_company_name(self, service):
        from bs4 import BeautifulSoup
        html = "<html><title>Reliance Industries Ltd share price</title><h1>Reliance Industries</h1></html>"
        soup = BeautifulSoup(html, "html.parser")
        name = service.parse_company_name(soup)
        assert name == "Reliance Industries Ltd"

    # More complex logic dealing with _process_scraping_async involves many calls 
    # to repo.write_detailed_log etc.
    # Since we have the MockScreenerRepository handling those methods (storing to list),
    # we can try to test the actual logic if we mock the network part.

    @patch("app.services.screener_service.requests.Session")
    def test_scraping_flow_logic(self, mock_session, service):
        # Setup specific HTML return
        html_content = """
        <html>
            <title>TCS share price</title>
            <div id="top-ratios">
                Market Cap ₹ 10,00,000 Cr
                Current Price ₹ 3,000
            </div>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.text = html_content
        mock_resp.raise_for_status = MagicMock()
        mock_session.return_value.get.return_value = mock_resp
        ScreenerService._session = None

        # Run process synchronously
        service.process_scraping_async("job_flow", "test")
        
        # Check repo for inserted metrics
        # Mock repo inserts into self.metrics
        # We expect Market Cap and Current Price
        metrics = service.repo.metrics
        
        # NOTE: parse_header_fundamentals search pattern validity check
        # "Market Cap\s*₹\s*([0-9,\.]+)\s*Cr"
        # Our HTML text: "Market Cap ₹ 10,00,000 Cr" -> Matches 10,00,000
        
        # Since we have 2 symbols in Mock Repo (Reliance, TCS)
        # It runs for both. 
        # Total metrics should be > 0
        assert len(metrics) > 0
        
        # Verify specific metric
        tcs_mcap = next((m for m in metrics if m['symbol'] == 'TCS' and m['metric'] == 'Market Cap (Cr)'), None)
        # Note: formatting symbol logic in service: TCS -> TCS
        # RELIANCE -> RELIANCE
        
        assert tcs_mcap is not None
        assert tcs_mcap['value'] == 1000000.0

