from typing import List, Dict, Optional
from datetime import datetime

class MockScreenerRepository:
    def __init__(self):
        self.metrics = []
        self.logs = []
        self.connections = []
        self.detailed_logs = []

    # DuckDB returns connection objects which then execute. 
    # For unit testing service logic, we often mock the *result* of service calls that use the repo.
    # However, ScreenerService calls `repo.get_db_connection()`.
    # This mock needs to return a mock connection object if used directly, 
    # OR we redefine the methods that use connection to just store data in memory 
    # IF the service delegates fully.
    # 
    # Looking at service code: service gets conn, passed it to repo.
    # e.g. self.repo.insert_metric(conn, ...)
    # 
    # So we need a MockConnection and the Repo methods should use it or ignore it.

    class MockDuckDBConnection:
        def __init__(self, parent_repo):
            self.repo = parent_repo
            self.closed = False

        def execute(self, sql, params=()):
            # Very basic SQL simulator or just return MagicMock
            # For `SELECT COUNT(*)`, `SELECT job_id...`
            # This is complex to mock fully SQL.
            # 
            # Better strategy: Mock the SERVICE methods for high level, 
            # Or Mock the Repo methods to NOT use SQL but update internal list.
            # 
            # But Service passes `conn`. 
            # Service: `conn = self.repo.get_db_connection()`
            # Service: `self.repo.insert_metric(conn, ...)`
            # 
            # So if `get_db_connection` returns a dummy, and `insert_metric` ignores it 
            # and stores to list, we are good.
            return self

        def fetchone(self):
            # Return dummy values for stats
            # last_run: [started_at, status]
            return [datetime.now(), "COMPLETED"] 
        
        def fetchall(self):
            return []

        def close(self):
            self.closed = True

    def get_db_connection(self):
        return self.MockDuckDBConnection(self)

    def insert_metric(self, conn, entity, parent, symbol, exchange, p_type, p_key, grp, metric, val, unit=None):
        self.metrics.append({
            "symbol": symbol, "metric": metric, "value": val
        })

    def write_detailed_log(self, conn, job_id, conn_id, c_name, sym, exc, action, msg, **kwargs):
        self.detailed_logs.append({"job_id": job_id, "symbol": sym, "action": action, "msg": msg})

    def save_scraping_log(self, conn, job_id, trig, start, end, status, a, b, c, d, recs, errs):
        self.logs.append({"job_id": job_id, "status": status, "records": recs})

    def get_active_symbols(self, conn) -> List[Dict]:
        return [
            {"symbol": "RELIANCE", "exchange": "NSE", "display_name": "Reliance Industries"},
            {"symbol": "TCS", "exchange": "NSE", "display_name": "TCS"}
        ]

class MockSymbolsRepository:
    def __init__(self):
        self.symbols = []

class MockAnnouncementsRepository:
    def __init__(self):
        self.announcements = []
