import pytest
import pandas as pd
import io
from app.services.symbols_service import SymbolsService
from tests.mocks.mock_market_repositories import MockSymbolsRepository

class TestSymbolsService:
    @pytest.fixture
    def service(self):
        service = SymbolsService()
        service.repo = MockSymbolsRepository()
        # Mock methods that hit DB if needed
        # But SymbolsService hits repo.get_db_connection().
        # We need MockSymbolsRepository to support get_db_connection similar to MockScreenerRepository
        # Or we mock the repo attribute entirely with MagicMock if we only test logic that doesn't hit DB deeply yet.
        return service

    def test_apply_transformation_script_basic(self, service):
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        script = """
final_df = df.copy()
final_df['C'] = final_df['A'] + final_df['B']
"""
        result = service.apply_transformation_script(df, script)
        assert "C" in result.columns
        assert result.iloc[0]["C"] == 4

    def test_process_manual_upload_preview_csv(self, service):
        # Create dummy CSV
        csv_content = b"symbol,exchange\nTCS,NSE\nINFY,NSE"
        user_info = {"id": 1, "username": "tester"}
        
        # We need to mock repo.get_transformation_script returning None (no script)
        # Mocking the repository instance method dynamically
        service.repo.get_transformation_script = lambda x: None
        
        result = service.process_manual_upload_preview(csv_content, "test.csv", None, user_info)
        
        assert result["total_rows"] == 2
        assert "preview_id" in result
        
        # Verify cache
        preview_id = result["preview_id"]
        assert preview_id in service._preview_cache
        assert service._preview_cache[preview_id]["new_rows"] == 2

    def test_apply_transformation_validation_error(self, service):
        df = pd.DataFrame({"A": [1]})
        script = "x = 1" # No final_df or df modification returned (if logic checks locals)
        
        # service logic checks if 'final_df' in locals OR 'df' modified.
        # This script does neither.
        with pytest.raises(ValueError) as exc:
            service.apply_transformation_script(df, script)
        assert "Transformation script must create" in str(exc.value)

