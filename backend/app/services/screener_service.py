import logging
import threading
import time
import requests
import re
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import traceback

from app.repositories.screener_repository import ScreenerRepository

logger = logging.getLogger(__name__)

class ScreenerService:
    # Shared state for background tasks
    _scraping_status_cache: Dict[str, Dict] = {}
    _stop_flags: Dict[int, bool] = {}
    _active_threads: Dict[str, threading.Thread] = {}
    _connection_jobs: Dict[int, str] = {}
    
    _stop_flags_lock = threading.Lock()
    _threads_lock = threading.Lock()
    _connection_jobs_lock = threading.Lock()
    _session = None
    _session_lock = threading.Lock()
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
        "Referer": "https://www.screener.in/"
    }

    def __init__(self):
        self.repo = ScreenerRepository()

    @classmethod
    def get_session(cls):
        if cls._session is None:
            with cls._session_lock:
                if cls._session is None:
                    cls._session = requests.Session()
                    adapter = requests.adapters.HTTPAdapter(
                        pool_connections=10, pool_maxsize=20, max_retries=2
                    )
                    cls._session.mount('http://', adapter)
                    cls._session.mount('https://', adapter)
        return cls._session

    def fetch_soup(self, url: str) -> BeautifulSoup:
        session = self.get_session()
        try:
            resp = session.get(url, headers=self.HEADERS, timeout=10, stream=False)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching URL {url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch URL {url}: {e}")
            raise

    # ... [Parsing Helpers from models/screener.py] ...
    
    def parse_company_name(self, soup: BeautifulSoup) -> Optional[str]:
        try:
            if soup.title:
                title_text = soup.title.get_text()
                match = re.search(r'^([^|]+?)\s+share\s+price', title_text, re.IGNORECASE)
                if match: return match.group(1).strip()
            
            h1 = soup.find('h1')
            if h1:
                company_name = h1.get_text().strip()
                if company_name and len(company_name) > 2: return company_name
            
            meta_name = soup.find('meta', {'property': 'og:title'}) or soup.find('meta', {'name': 'title'})
            if meta_name and meta_name.get('content'):
                match = re.search(r'^([^|]+?)\s+share\s+price', meta_name.get('content'), re.IGNORECASE)
                if match: return match.group(1).strip()
            return None
        except Exception as e:
            logger.error(f"Error parsing company name: {e}")
            return None

    def parse_header_fundamentals(self, soup: BeautifulSoup) -> dict:
        txt = soup.get_text("\n")
        def grab(pattern):
            m = re.search(pattern, txt)
            return m.group(1).strip() if m else None
        data = {}
        data["Market Cap (Cr)"] = grab(r"Market Cap\s*₹\s*([0-9,\.]+)\s*Cr")
        data["Current Price"] = grab(r"Current Price\s*₹\s*([0-9,\.]+)")
        data["High / Low"] = grab(r"High\s*/\s*Low\s*₹\s*([0-9,\. /]+)")
        data["Stock P/E"] = grab(r"Stock P/E\s*([0-9\.]+)")
        data["Book Value"] = grab(r"Book Value\s*₹\s*([0-9,\.]+)")
        data["Dividend Yield %"] = grab(r"Dividend Yield\s*([0-9\.]+)\s*%")
        data["ROCE %"] = grab(r"ROCE\s*([0-9\.]+)\s*%")
        data["ROE %"] = grab(r"ROE\s*([0-9\.]+)\s*%")
        data["Face Value"] = grab(r"Face Value\s*₹\s*([0-9,\.]+)")
        return data

    def parse_peer_table(self, soup: BeautifulSoup) -> Optional[pd.DataFrame]:
        try:
            tables = pd.read_html(str(soup))
            for df in tables:
                cols = " ".join([str(c) for c in df.columns])
                if "CMP Rs." in cols and "P/E" in cols: return df
            return None
        except: return None

    def parse_section_table(self, soup: BeautifulSoup, heading_text: str) -> Optional[pd.DataFrame]:
        try:
            h = soup.find(lambda tag: tag.name in ["h2", "h3"] and heading_text in tag.get_text())
            if not h: return None
            table = h.find_next("table")
            if not table: return None
            dfs = pd.read_html(str(table))
            return dfs[0] if dfs else None
        except: return None

    def clean_numeric_value(self, value: Any) -> Optional[float]:
        if value is None: return None
        if isinstance(value, (int, float)): return float(value)
        if isinstance(value, str):
            cleaned = re.sub(r'[₹,\s%]', '', value.strip())
            if '/' in cleaned: cleaned = cleaned.split('/')[0].strip()
            try: return float(cleaned)
            except: return None
        return None

    def format_symbol_for_url(self, symbol: str, exchange: str) -> str:
        if exchange.upper() == 'BSE': return str(symbol).strip()
        else: return str(symbol).strip().upper().replace(' ', '').replace('-', '').replace('.', '')

    def _insert_financial_table(self, conn, df, symbol, exchange, statement_name, statement_group) -> int:
        records = 0
        try:
            if df is not None and not df.empty and len(df.columns) >= 2:
                metric_col = df.columns[0]
                year_cols = df.columns[1:]
                for _, row in df.iterrows():
                    metric_name = str(row[metric_col]).strip() if pd.notna(row.get(metric_col)) else None
                    if not metric_name or metric_name.lower() in ['nan', 'none', '']: continue
                    for year_col in year_cols:
                        period_key = str(year_col).strip()
                        if not period_key or period_key.lower() in ['nan', 'none', '']: continue
                        metric_value = row.get(year_col)
                        if pd.notna(metric_value) and str(metric_value).strip():
                            num_val = self.clean_numeric_value(metric_value)
                            if num_val is not None:
                                unit = None
                                m_str = str(metric_name).lower()
                                if 'crore' in m_str or 'cr' in m_str: unit = "Cr"
                                elif '%' in str(metric_value) or 'ratio' in m_str or 'percent' in m_str: unit = "%"
                                elif '₹' in str(metric_value) or 'rs' in m_str: unit = "₹"
                                self.repo.insert_metric(conn, "COMPANY", None, symbol, exchange, "ANNUAL", period_key, statement_group, metric_name, num_val, unit)
                                records += 1
        except Exception as e:
            logger.debug(f"Error inserting {statement_name} for {symbol}: {e}")
        return records

    def scrape_symbol_logic(self, symbol: str, exchange: str, conn, base_url: Optional[str] = None) -> dict:
        """Main scraping logic for a symbol"""
        if not symbol or not symbol.strip():
             return {"success": False, "records_inserted": 0, "error": "Invalid symbol"}
        
        symbol_for_url = self.format_symbol_for_url(symbol, exchange)
        url = base_url.strip().replace('{symbol}', symbol_for_url) if base_url else f"https://www.screener.in/company/{symbol_for_url}/"
        if '/consolidated/' not in url: url = url.rstrip('/') + '/consolidated/'
        
        records_inserted = 0
        extracted_name = None
        try:
            soup = self.fetch_soup(url)
            snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            extracted_name = self.parse_company_name(soup)
            
            # Header
            header_data = self.parse_header_fundamentals(soup)
            for k, v in header_data.items():
                if v:
                    num = self.clean_numeric_value(v)
                    unit = "%" if "%" in k else "₹" if "₹" in str(v) else None
                    self.repo.insert_metric(conn, "COMPANY", None, symbol_for_url, exchange, "SNAPSHOT", snapshot_date, "MARKET", k, num, unit)
                    records_inserted += 1
            
            # Peer
            peer_df = self.parse_peer_table(soup)
            if peer_df is not None and not peer_df.empty:
                first_col = peer_df.columns[0]
                for _, row in peer_df.iterrows():
                    peer_name = str(row[first_col]).strip() if pd.notna(row.get(first_col)) else None
                    if peer_name and peer_name.lower() not in ['nan','none','']:
                        for col in peer_df.columns[1:]:
                            val = row.get(col)
                            if pd.notna(val):
                                num = self.clean_numeric_value(val)
                                if num is not None:
                                    unit = "%" if "%" in str(col) else "₹" if "Rs." in str(col) else None
                                    self.repo.insert_metric(conn, "PEER", symbol_for_url, peer_name, exchange, "SNAPSHOT", snapshot_date, "PEER", str(col), num, unit)
                                    records_inserted += 1
            
            # Financials
            records_inserted += self._insert_financial_table(conn, self.parse_section_table(soup, "Profit & Loss"), symbol_for_url, exchange, "Profit & Loss", "Profit & Loss")
            records_inserted += self._insert_financial_table(conn, self.parse_section_table(soup, "Balance Sheet"), symbol_for_url, exchange, "Balance Sheet", "Balance Sheet")
            records_inserted += self._insert_financial_table(conn, self.parse_section_table(soup, "Cash Flows"), symbol_for_url, exchange, "Cash Flows", "Cash Flows")
            records_inserted += self._insert_financial_table(conn, self.parse_section_table(soup, "Ratios"), symbol_for_url, exchange, "Ratios", "Ratios")
            
            return {
                "symbol": symbol_for_url, "exchange": exchange, "success": True, 
                "records_inserted": records_inserted, "company_name": extracted_name
            }
        except Exception as e:
            logger.error(f"Error scraping {symbol}: {e}")
            return {"symbol": symbol_for_url, "exchange": exchange, "success": False, "records_inserted": 0, "error": str(e)}

    # Top-level Orchestrator
    def process_scraping_async(self, job_id: str, triggered_by: str, connection_id: Optional[int] = None):
        """Background task for scraping"""
        started_at = datetime.now(timezone.utc)
        start_time = time.time()
        
        try:
            self._scraping_status_cache[job_id] = {
                "status": "PROCESSING", "total_symbols": 0, "symbols_processed": 0, 
                "symbols_succeeded": 0, "symbols_failed": 0, "total_records_inserted": 0, 
                "percentage": 0, "triggered_by": triggered_by, "connection_id": connection_id, "errors": []
            }
            if connection_id:
                with self._connection_jobs_lock:
                    self._connection_jobs[connection_id] = job_id
            
            # Get symbols
            temp_conn = self.repo.get_db_connection()
            symbols = self.repo.get_active_symbols(temp_conn)
            temp_conn.close()
            total_symbols = len(symbols)
            self._scraping_status_cache[job_id]["total_symbols"] = total_symbols
            
            if total_symbols == 0:
                self._handle_job_end(job_id, connection_id, "FAILED", ["No active symbols found"], 0, 0, 0, 0, started_at, triggered_by)
                return

            # Prepare connection
            conn_details = None
            if connection_id:
                with self._stop_flags_lock:
                    self._stop_flags[connection_id] = False
                # fetch details
                c_conn = self.repo.get_db_connection()
                res = c_conn.execute("SELECT connection_name, connection_type, base_url FROM screener_connections WHERE id = ?", [connection_id]).fetchone()
                c_conn.close()
                if res: conn_details = {"name": res[0], "type": res[1], "url": res[2]}
                
                # Log START
                l_conn = self.repo.get_db_connection()
                self.repo.write_detailed_log(l_conn, job_id, connection_id, conn_details['name'], None, None, "START", f"Started. Symbols: {total_symbols}", total_symbols=total_symbols)
                l_conn.close()

            symbols_succeeded = 0
            symbols_failed = 0
            total_records = 0
            errors = []
            
            for idx, symbol_info in enumerate(symbols):
                # Check stop flag
                if connection_id:
                    with self._stop_flags_lock:
                        if self._stop_flags.get(connection_id, False):
                            self._handle_job_end(job_id, connection_id, "STOPPED", errors + ["Stopped by user"], symbols_succeeded, symbols_failed, total_records, total_symbols, started_at, triggered_by)
                            return

                symbol_clean = symbol_info.get("symbol", "").strip()
                display_name = symbol_info.get("display_name", symbol_clean)
                exchange = symbol_info.get("exchange", "").upper()
                
                self._scraping_status_cache[job_id]["current_symbol"] = display_name
                self._scraping_status_cache[job_id]["current_exchange"] = exchange
                
                s_conn = self.repo.get_db_connection()
                try:
                    c_name = conn_details['name'] if conn_details else None
                    self.repo.write_detailed_log(s_conn, job_id, connection_id, c_name, symbol_clean, exchange, "FETCH", f"Fetching {display_name} ({idx+1}/{total_symbols})", company_name=display_name, symbol_index=idx+1, total_symbols=total_symbols)
                    
                    base_u = conn_details['url'] if conn_details else None
                    res = self.scrape_symbol_logic(symbol_clean, exchange, s_conn, base_u)
                    
                    time.sleep(1) # Rate limit
                    
                    if res["success"]:
                        symbols_succeeded += 1
                        total_records += res["records_inserted"]
                        self.repo.write_detailed_log(s_conn, job_id, connection_id, c_name, symbol_clean, exchange, "INSERT", f"Scraped {res['records_inserted']} records", company_name=display_name, symbol_index=idx+1, total_symbols=total_symbols, records_count=res["records_inserted"])
                    else:
                        symbols_failed += 1
                        err = res.get("error", "Unknown")
                        errors.append(f"{display_name}: {err}")
                        self.repo.write_detailed_log(s_conn, job_id, connection_id, c_name, symbol_clean, exchange, "ERROR", f"Failed: {err}", company_name=display_name, symbol_index=idx+1, total_symbols=total_symbols)
                
                except Exception as e:
                     symbols_failed += 1
                     errors.append(f"{display_name}: {str(e)}")
                finally:
                    s_conn.close()
                
                self._update_cache(job_id, idx+1, symbols_succeeded, symbols_failed, total_records, total_symbols)

            self._handle_job_end(job_id, connection_id, "COMPLETED" if symbols_failed == 0 else "COMPLETED (Partial)", errors, symbols_succeeded, symbols_failed, total_records, total_symbols, started_at, triggered_by)

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            self._handle_job_end(job_id, connection_id, "FAILED", [str(e)], 0, 0, 0, 0, started_at, triggered_by)

    def _update_cache(self, job_id, processed, succeeded, failed, records, total):
        if job_id in self._scraping_status_cache:
            c = self._scraping_status_cache[job_id]
            c["symbols_processed"] = processed
            c["symbols_succeeded"] = succeeded
            c["symbols_failed"] = failed
            c["total_records_inserted"] = records
            c["percentage"] = int((processed / total) * 100) if total else 0

    def _handle_job_end(self, job_id, connection_id, status, errors, suc, fail, recs, total, started_at, triggered_by):
        ended_at = datetime.now(timezone.utc)
        if job_id in self._scraping_status_cache:
            self._scraping_status_cache[job_id]["status"] = status
            self._scraping_status_cache[job_id]["errors"] = errors[:10]
            self._scraping_status_cache[job_id]["percentage"] = 100
            self._scraping_status_cache[job_id]["current_symbol"] = None
        
        with self._threads_lock:
            if job_id in self._active_threads: del self._active_threads[job_id]
        
        if connection_id:
             with self._connection_jobs_lock:
                 if connection_id in self._connection_jobs: del self._connection_jobs[connection_id]
             
             conn_status = "Completed"
             if status == "STOPPED": conn_status = "Stopped"
             elif status == "FAILED": conn_status = "Failed"
             
             # Update connection status
             try:
                 c = self.repo.get_db_connection()
                 c.execute("UPDATE screener_connections SET status=?, last_run=?, records_loaded=?, updated_at=? WHERE id=?", 
                           [conn_status, ended_at, recs, ended_at, connection_id])
                 c.close()
             except Exception as e:
                 logger.error(f"Failed to update connection status: {e}")

        # Save log
        try:
             c = self.repo.get_db_connection()
             self.repo.save_scraping_log(c, job_id, triggered_by, started_at, ended_at, status, total, total if status!="STOPPED" else (suc+fail), suc, fail, recs, errors[:10])
             c.close()
        except: pass

    def start_scraping(self, job_id: str, triggered_by: str, connection_id: Optional[int] = None):
        t = threading.Thread(target=self.process_scraping_async, args=(job_id, triggered_by, connection_id))
        with self._threads_lock:
            self._active_threads[job_id] = t
        t.start()
    
    def stop_scraping(self, connection_id: int):
        with self._stop_flags_lock:
            self._stop_flags[connection_id] = True

    def get_status(self, job_id: str):
        if job_id in self._scraping_status_cache:
            return self._scraping_status_cache[job_id]
        
        # Check DB
        conn = None
        try:
            conn = self.repo.get_db_connection()
            result = conn.execute("""
                SELECT job_id, triggered_by, started_at, ended_at, duration_seconds,
                       total_symbols, symbols_processed, symbols_succeeded, symbols_failed,
                       total_records_inserted, status, error_summary
                FROM screener_scraping_logs
                WHERE job_id = ?
            """, [job_id]).fetchone()
            
            if result:
                 return {
                    "job_id": result[0],
                    "status": result[10],
                    "total_symbols": result[5],
                    "symbols_processed": result[6],
                    "symbols_succeeded": result[7],
                    "symbols_failed": result[8],
                    "total_records_inserted": result[9],
                    "percentage": 100 if result[10] in ["COMPLETED", "COMPLETED (Partial)", "FAILED", "STOPPED"] else 0,
                    "triggered_by": result[1],
                    "started_at": result[2],
                    "ended_at": result[3],
                    "duration_seconds": result[4],
                    "errors": result[11].split("; ") if result[11] else []
                 }
            return None
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return None
        finally:
            if conn: conn.close()

    def get_stats(self):
        conn = None
        try:
            conn = self.repo.get_db_connection()
            last_run = conn.execute("SELECT started_at, status FROM screener_scraping_logs ORDER BY started_at DESC LIMIT 1").fetchone()
            total_records = conn.execute("SELECT COUNT(*) FROM screener_data").fetchone()[0]
            
            active_symbols = self.repo.get_active_symbols(conn)
            
            conn_stats = conn.execute("SELECT status, count(*) FROM screener_connections GROUP BY status").fetchall()
            connections_summary = {s[0]: s[1] for s in conn_stats}
            
            return {
                "last_run": last_run[0] if last_run else None,
                "last_run_status": last_run[1] if last_run else None,
                "active_symbols_param": len(active_symbols),
                "total_records": total_records,
                "connections_summary": connections_summary
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
        finally:
            if conn: conn.close()

    def get_scraping_history(self, limit: int = 20):
        conn = None
        try:
            conn = self.repo.get_db_connection()
            rows = conn.execute(f"""
                SELECT job_id, triggered_by, started_at, ended_at, duration_seconds, status, total_symbols, symbols_succeeded, total_records_inserted
                FROM screener_scraping_logs
                ORDER BY started_at DESC
                LIMIT {limit}
            """).fetchall()
            
            return [
                {
                    "job_id": r[0], "triggered_by": r[1], "started_at": r[2], "ended_at": r[3],
                    "duration": r[4], "status": r[5], "total_symbols": r[6], "succeeded": r[7], "records": r[8]
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []
        finally:
             if conn: conn.close()
    
    def get_connections(self):
        conn = None
        try:
             conn = self.repo.get_db_connection()
             cols = [c[0] for c in conn.execute("DESCRIBE screener_connections").fetchall()]
             rows = conn.execute("SELECT * FROM screener_connections ORDER BY id").fetchall()
             return [dict(zip(cols, row)) for row in rows]
        except Exception as e:
             logger.error(f"Error getting connections: {e}")
             return []
        finally:
             if conn: conn.close()

    def update_connection(self, connection_id: int, data: dict):
        conn = None
        try:
             conn = self.repo.get_db_connection()
             fields = []
             values = []
             for k, v in data.items():
                 fields.append(f"{k} = ?")
                 values.append(v)
             values.append(connection_id)
             
             if not fields: return
             
             sql = f"UPDATE screener_connections SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
             conn.execute(sql, values)
        except Exception as e:
             logger.error(f"Error updating connection: {e}")
             raise
        finally:
             if conn: conn.close()
