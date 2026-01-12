"""
Screener Model for Company Fundamentals, News, and Corporate Actions
Scrapes data from screener.in and stores in unified time-series format

URL Logic:
- NSE: Uses company name (from 'name' column) - e.g., "RELIANCE" -> "https://www.screener.in/company/RELIANCE/"
- BSE: Uses exchange_token ID - e.g., "500325" -> "https://www.screener.in/company/500325/"
"""
import requests
from bs4 import BeautifulSoup
import duckdb
import os
import re
import logging
import threading
import time
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Referer": "https://www.screener.in/"
}

def get_screener_db_path() -> str:
    """Get the path to the Screener DuckDB database file"""
    data_dir = os.path.abspath(settings.DATA_DIR)
    db_dir = os.path.join(data_dir, "Company Fundamentals")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "screener.duckdb")
    return db_path

def init_screener_database():
    """Initialize DuckDB database and create unified time-series table"""
    db_path = get_screener_db_path()
    
    try:
        conn = duckdb.connect(db_path, config={'allow_unsigned_extensions': True})
        
        # Create unified time-series table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS screener_data (
                id INTEGER PRIMARY KEY,
                entity_type VARCHAR NOT NULL,
                parent_company_symbol VARCHAR,
                symbol VARCHAR NOT NULL,
                exchange VARCHAR NOT NULL,
                period_type VARCHAR NOT NULL,
                period_key VARCHAR NOT NULL,
                statement_group VARCHAR NOT NULL,
                metric_name VARCHAR NOT NULL,
                metric_value DOUBLE,
                unit VARCHAR,
                consolidated_flag VARCHAR DEFAULT 'CONSOLIDATED',
                source VARCHAR DEFAULT 'screener.in',
                captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        
        # Ensure id column auto-increments (DuckDB uses sequence)
        try:
            conn.execute("CREATE SEQUENCE IF NOT EXISTS screener_data_id_seq START 1")
        except:
            pass  # Sequence might already exist
        
        # Create indexes for efficient queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_period 
            ON screener_data(symbol, period_type, period_key)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_statement_group 
            ON screener_data(statement_group, symbol)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_entity_type 
            ON screener_data(entity_type, parent_company_symbol)
        """)
        
        # Create scraping logs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS screener_scraping_logs (
                id INTEGER PRIMARY KEY,
                job_id VARCHAR NOT NULL UNIQUE,
                triggered_by VARCHAR,
                started_at TIMESTAMP WITH TIME ZONE,
                ended_at TIMESTAMP WITH TIME ZONE,
                duration_seconds INTEGER,
                total_symbols INTEGER DEFAULT 0,
                symbols_processed INTEGER DEFAULT 0,
                symbols_succeeded INTEGER DEFAULT 0,
                symbols_failed INTEGER DEFAULT 0,
                total_records_inserted INTEGER DEFAULT 0,
                status VARCHAR DEFAULT 'PENDING',
                error_summary TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create detailed symbol-level logs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS screener_detailed_logs (
                id INTEGER PRIMARY KEY,
                job_id VARCHAR NOT NULL,
                connection_id INTEGER,
                connection_name VARCHAR,
                symbol VARCHAR,
                exchange VARCHAR,
                company_name VARCHAR,
                symbol_index INTEGER,
                total_symbols INTEGER,
                action VARCHAR NOT NULL,
                message TEXT,
                records_count INTEGER,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add new columns if they don't exist (for existing databases)
        try:
            conn.execute("ALTER TABLE screener_detailed_logs ADD COLUMN company_name VARCHAR")
        except:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE screener_detailed_logs ADD COLUMN symbol_index INTEGER")
        except:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE screener_detailed_logs ADD COLUMN total_symbols INTEGER")
        except:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE screener_detailed_logs ADD COLUMN records_count INTEGER")
        except:
            pass  # Column already exists
        
        # Create indexes for detailed logs
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_detailed_logs_job_id 
            ON screener_detailed_logs(job_id)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_detailed_logs_connection 
            ON screener_detailed_logs(connection_id, timestamp DESC)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_detailed_logs_timestamp 
            ON screener_detailed_logs(timestamp DESC)
        """)
        
        # Create connections table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS screener_connections (
                id INTEGER PRIMARY KEY,
                connection_name VARCHAR NOT NULL,
                connection_type VARCHAR NOT NULL,
                website_name VARCHAR,
                base_url VARCHAR,
                api_provider_name VARCHAR,
                auth_type VARCHAR,
                status VARCHAR DEFAULT 'Idle',
                last_run TIMESTAMP WITH TIME ZONE,
                records_loaded INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add base_url column if it doesn't exist (for existing databases)
        try:
            conn.execute("ALTER TABLE screener_connections ADD COLUMN base_url VARCHAR")
        except:
            pass  # Column already exists
        
        # Create default Screener.in connection if none exists
        try:
            existing_count = conn.execute("SELECT COUNT(*) FROM screener_connections").fetchone()[0]
            if existing_count == 0:
                max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM screener_connections").fetchone()
                next_id = max_id_result[0] if max_id_result else 1
                
                now = datetime.now(timezone.utc)
                conn.execute("""
                    INSERT INTO screener_connections 
                    (id, connection_name, connection_type, base_url, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    next_id,
                    "Screener.in Default",
                    "WEBSITE_SCRAPING",
                    "https://www.screener.in/company/{symbol}/",
                    "Idle",
                    now,
                    now
                ])
                logger.info("Created default Screener.in connection")
        except Exception as e:
            logger.warning(f"Could not create default connection: {e}")
        
        conn.close()
        logger.info(f"Screener database initialized at {db_path}")
    except Exception as e:
        logger.error(f"Failed to initialize Screener database: {e}")
        raise

def ensure_default_connection(conn: duckdb.DuckDBPyConnection):
    """Ensure a default Screener.in connection exists (internal function)"""
    try:
        existing_count = conn.execute("SELECT COUNT(*) FROM screener_connections").fetchone()[0]
        if existing_count == 0:
            max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM screener_connections").fetchone()
            next_id = max_id_result[0] if max_id_result else 1
            
            now = datetime.now(timezone.utc)
            conn.execute("""
                INSERT INTO screener_connections 
                (id, connection_name, connection_type, base_url, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                next_id,
                "Screener.in Default",
                "WEBSITE_SCRAPING",
                "https://www.screener.in/company/{symbol}/",
                "Idle",
                now,
                now
            ])
            logger.info("Created default Screener.in connection")
    except Exception as e:
        logger.warning(f"Could not ensure default connection: {e}")

def get_db_connection():
    """Get a DuckDB connection to the Screener database with proper configuration"""
    db_path = get_screener_db_path()
    if not os.path.exists(db_path):
        init_screener_database()
    
    max_retries = 3
    retry_delay = 0.5
    
    for attempt in range(max_retries):
        try:
            conn = duckdb.connect(db_path, read_only=False, config={'allow_unsigned_extensions': True})
            conn.execute("SET enable_progress_bar=false")
            conn.execute("SET threads=1")
            try:
                ensure_default_connection(conn)
            except Exception as e:
                logger.warning(f"Could not ensure default connection: {e}")
            return conn
        except Exception as e:
            if attempt < max_retries - 1:
                error_msg = str(e)
                if "being used by another process" in error_msg or "Cannot open file" in error_msg:
                    logger.warning(f"[DB] Database file is locked (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # For other errors, don't retry
                    logger.error(f"Failed to connect to Screener database at {db_path}: {e}", exc_info=True)
                    raise
            else:
                # Last attempt failed
                logger.error(f"Failed to connect to Screener database at {db_path} after {max_retries} attempts: {e}", exc_info=True)
                raise

# Create a session for connection pooling and faster requests
_session = None
_session_lock = threading.Lock()

def get_session():
    """Get or create a requests session with connection pooling"""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                _session = requests.Session()
                # Configure session for better performance
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=10,
                    pool_maxsize=20,
                    max_retries=2
                )
                _session.mount('http://', adapter)
                _session.mount('https://', adapter)
    return _session

def fetch_soup(url: str) -> BeautifulSoup:
    """Fetch and parse HTML from URL with proper headers - optimized for speed"""
    session = get_session()
    try:
        # Use session for connection pooling, reduced timeout for faster failure
        resp = session.get(url, headers=HEADERS, timeout=10, stream=False)
        resp.raise_for_status()
        # Use html.parser instead of lxml for faster parsing (lxml requires C extension)
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching URL {url}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch URL {url}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error parsing HTML from {url}: {e}")
        raise

def parse_company_name(soup: BeautifulSoup) -> Optional[str]:
    """Extract company name from screener.in page"""
    try:
        if soup.title:
            title_text = soup.title.get_text()
            match = re.search(r'^([^|]+?)\s+share\s+price', title_text, re.IGNORECASE)
            if match:
                company_name = match.group(1).strip()
                logger.info(f"[SCRAPING] Extracted company name from title: '{company_name}'")
                return company_name
        
        h1 = soup.find('h1')
        if h1:
            company_name = h1.get_text().strip()
            if company_name and len(company_name) > 2:
                logger.info(f"[SCRAPING] Extracted company name from h1: '{company_name}'")
                return company_name
        
        meta_name = soup.find('meta', {'property': 'og:title'}) or soup.find('meta', {'name': 'title'})
        if meta_name and meta_name.get('content'):
            content = meta_name.get('content')
            match = re.search(r'^([^|]+?)\s+share\s+price', content, re.IGNORECASE)
            if match:
                company_name = match.group(1).strip()
                logger.info(f"[SCRAPING] Extracted company name from meta: '{company_name}'")
                return company_name
        
        logger.warning("[SCRAPING] Could not extract company name from screener.in page")
        return None
    except Exception as e:
        logger.error(f"[SCRAPING] Error extracting company name: {e}")
        return None

def parse_header_fundamentals(soup: BeautifulSoup) -> dict:
    """Parse header fundamentals from Screener page"""
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

def parse_peer_table(soup: BeautifulSoup) -> Optional[pd.DataFrame]:
    """
    Find the peer comparison table by looking for columns like 'CMP Rs.' and 'P/E'.
    """
    try:
        tables = pd.read_html(str(soup))
        for df in tables:
            cols = [str(c) for c in df.columns]
            joined = " ".join(cols)
            if "CMP Rs." in joined and "P/E" in joined:
                return df
        return None
    except Exception as e:
        logger.debug(f"Error parsing peer table: {e}")
        return None

def parse_section_table(soup: BeautifulSoup, heading_text: str) -> Optional[pd.DataFrame]:
    """
    For blocks like 'Profit & Loss', 'Balance Sheet', 'Cash Flows', 'Ratios'.
    """
    try:
        h = soup.find(lambda tag: tag.name in ["h2", "h3"] and heading_text in tag.get_text())
        if not h:
            return None
        table = h.find_next("table")
        if not table:
            return None
        tables = pd.read_html(str(table))
        if tables:
            return tables[0]
        return None
    except Exception as e:
        logger.debug(f"Error parsing section table for '{heading_text}': {e}")
        return None

def clean_numeric_value(value: Any) -> Optional[float]:
    """Strip currency symbols, percentage signs, and commas, convert to float"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r'[₹,\s%]', '', value.strip())
        if '/' in cleaned:
            cleaned = cleaned.split('/')[0].strip()
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    return None

def format_symbol_for_url(symbol: str, exchange: str) -> str:
    """
    Format symbol for screener.in URL based on exchange
    
    Args:
        symbol: The symbol to format (company name for NSE, ID for BSE)
        exchange: Exchange code (NSE or BSE)
    
    Returns:
        Formatted symbol for URL
        - NSE: Remove spaces, convert to uppercase (e.g., "Reliance Industries" -> "RELIANCEINDUSTRIES")
        - BSE: Use ID as-is (e.g., "500325" -> "500325")
    """
    if exchange.upper() == 'BSE':
        # BSE: Use ID as-is (no formatting needed)
        return str(symbol).strip()
    else:
        # NSE: Format company name - remove spaces, convert to uppercase
        return str(symbol).strip().upper().replace(' ', '').replace('-', '').replace('.', '')

def insert_metric(
    conn: duckdb.DuckDBPyConnection,
    entity_type: str,
    parent_company_symbol: Optional[str],
    symbol: str,
    exchange: str,
    period_type: str,
    period_key: str,
    statement_group: str,
    metric_name: str,
    metric_value: Optional[float],
    unit: Optional[str] = None,
    consolidated_flag: str = "CONSOLIDATED",
    metadata: Optional[str] = None
):
    """Insert a single metric into the unified table"""
    if metric_value is None and period_type != "EVENT":
        return
    
    try:
        # Get next ID from sequence or use MAX
        try:
            next_id_result = conn.execute("SELECT nextval('screener_data_id_seq')").fetchone()
            next_id = next_id_result[0] if next_id_result else None
        except:
            # Fallback: get max ID and increment
            max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM screener_data").fetchone()
            next_id = max_id_result[0] if max_id_result else 1
        
        conn.execute("""
            INSERT INTO screener_data (
                id, entity_type, parent_company_symbol, symbol, exchange,
                period_type, period_key, statement_group, metric_name,
                metric_value, unit, consolidated_flag, source, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            next_id,
            entity_type,
            parent_company_symbol,
            symbol,  # Save the symbol as used in URL (formatted name for NSE, ID for BSE)
            exchange,
            period_type,
            period_key,
            statement_group,
            metric_name,
            metric_value,
            unit,
            consolidated_flag,
            "screener.in",
            metadata
        ])
    except Exception as e:
        logger.warning(f"Failed to insert metric {metric_name} for {symbol}: {e}")

def scrape_fundamentals(symbol: str, exchange: str, conn: duckdb.DuckDBPyConnection, base_url: Optional[str] = None) -> tuple[int, Optional[str]]:
    """
    Scrape fundamentals for a symbol and insert into database
    Uses reference code from notebook - extracts header fundamentals, peer comparison,
    Profit & Loss, Balance Sheet, Cash Flows, and Ratios.
    
    Args:
        symbol: Symbol to scrape (company name for NSE, ID for BSE)
        exchange: Exchange code (NSE or BSE)
        conn: DuckDB connection to screener database
        base_url: Base URL template with {symbol} placeholder
    
    Returns:
        Number of records inserted
    """
    records_inserted = 0
    extracted_company_name = None
    try:
        if not symbol or not symbol.strip():
            logger.error(f"Invalid symbol provided: '{symbol}' (empty or None)")
            raise ValueError(f"Invalid symbol: symbol cannot be empty")
        
        # Format symbol for URL based on exchange
        # NSE: Format company name (remove spaces, uppercase)
        # BSE: Use ID as-is
        symbol_for_url = format_symbol_for_url(symbol, exchange)
        
        # Build URL - add /consolidated/ if not present (reference code uses /consolidated/)
        if base_url and base_url.strip():
            url = base_url.strip().replace('{symbol}', symbol_for_url)
        else:
            url = f"https://www.screener.in/company/{symbol_for_url}/"
        
        # Ensure consolidated URL (reference code always uses /consolidated/)
        if '/consolidated/' not in url:
            url = url.rstrip('/') + '/consolidated/'
        
        soup = fetch_soup(url)
        snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Extract company name from page (if available) - this will be used in logs
        extracted_company_name = parse_company_name(soup)
        
        # 1) Header fundamentals - MARKET snapshot
        header_data = parse_header_fundamentals(soup)
        for metric_name, metric_value in header_data.items():
            if metric_value:
                numeric_value = clean_numeric_value(metric_value)
                unit = "%" if "%" in metric_name else "₹" if "₹" in str(metric_value) else None
                
                insert_metric(
                    conn, "COMPANY", None, symbol_for_url, exchange,
                    "SNAPSHOT", snapshot_date, "MARKET",
                    metric_name, numeric_value, unit
                )
                records_inserted += 1
        
        # 2) Peer comparison - PEER snapshot
        peer_df = parse_peer_table(soup)
        if peer_df is not None and not peer_df.empty:
            # Extract peer company names from first column (usually Company name)
            # Extract metrics from subsequent columns (CMP Rs., P/E, etc.)
            try:
                # Find the first column which typically contains company names
                first_col = peer_df.columns[0] if len(peer_df.columns) > 0 else None
                if first_col:
                    for idx, row in peer_df.iterrows():
                        peer_name = str(row[first_col]).strip() if pd.notna(row.get(first_col)) else None
                        if not peer_name or peer_name.lower() in ['nan', 'none', '']:
                            continue
                        
                        # Process each metric column (skip the first column which is company name)
                        for col_idx, col_name in enumerate(peer_df.columns):
                            if col_idx == 0:  # Skip company name column
                                continue
                            
                            metric_value = row.get(col_name)
                            if pd.notna(metric_value) and str(metric_value).strip():
                                metric_name = f"{col_name}"  # Use column name as metric name
                                numeric_value = clean_numeric_value(metric_value)
                                
                                if numeric_value is not None:
                                    unit = "%" if "%" in str(col_name) else "₹" if "Rs." in str(col_name) else None
                                    
                                    insert_metric(
                                        conn, "PEER", symbol_for_url, peer_name, exchange,
                                        "SNAPSHOT", snapshot_date, "PEER",
                                        metric_name, numeric_value, unit
                                    )
                                    records_inserted += 1
            except Exception as e:
                logger.debug(f"Error processing peer comparison for {symbol}: {e}")
        
        # 3) Financial statements - ANNUAL period_type
        # Profit & Loss - statement_group must match section name (requirement 6.2)
        pl_df = parse_section_table(soup, "Profit & Loss")
        if pl_df is not None and not pl_df.empty:
            records_inserted += _insert_financial_table(
                conn, pl_df, symbol_for_url, exchange, "Profit & Loss", "Profit & Loss"
            )
        
        # Balance Sheet - statement_group must match section name (requirement 6.2)
        bs_df = parse_section_table(soup, "Balance Sheet")
        if bs_df is not None and not bs_df.empty:
            records_inserted += _insert_financial_table(
                conn, bs_df, symbol_for_url, exchange, "Balance Sheet", "Balance Sheet"
            )
        
        # Cash Flows - statement_group must match section name (requirement 6.2)
        cf_df = parse_section_table(soup, "Cash Flows")
        if cf_df is not None and not cf_df.empty:
            records_inserted += _insert_financial_table(
                conn, cf_df, symbol_for_url, exchange, "Cash Flows", "Cash Flows"
            )
        
        # Ratios - statement_group must match section name (requirement 6.2)
        ratio_df = parse_section_table(soup, "Ratios")
        if ratio_df is not None and not ratio_df.empty:
            records_inserted += _insert_financial_table(
                conn, ratio_df, symbol_for_url, exchange, "Ratios", "Ratios"
            )
        
    except Exception as e:
        # Short error message
        error_short = str(e).split('\n')[0][:100] if str(e) else "Unknown error"
        logger.error(f"[SCRAPING] Error: {error_short}")
        raise
    
    return records_inserted, extracted_company_name

def _insert_financial_table(
    conn: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    symbol: str,
    exchange: str,
    statement_name: str,
    statement_group: str
) -> int:
    """
    Insert financial table data (P&L, Balance Sheet, Cash Flows, Ratios) into database.
    
    Tables have metric names in first column, and financial years as column headers.
    period_key = financial year from column header
    period_type = ANNUAL
    """
    records_inserted = 0
    
    try:
        if df.empty or len(df.columns) < 2:
            return 0
        
        # First column contains metric names
        metric_col = df.columns[0]
        
        # Remaining columns are financial years
        year_cols = [col for col in df.columns[1:]]
        
        for idx, row in df.iterrows():
            metric_name = str(row[metric_col]).strip() if pd.notna(row.get(metric_col)) else None
            if not metric_name or metric_name.lower() in ['nan', 'none', '']:
                continue
            
            # Process each financial year column
            for year_col in year_cols:
                period_key = str(year_col).strip()  # Financial year as period_key
                if not period_key or period_key.lower() in ['nan', 'none', '']:
                    continue
                
                metric_value = row.get(year_col)
                if pd.notna(metric_value) and str(metric_value).strip():
                    numeric_value = clean_numeric_value(metric_value)
                    
                    if numeric_value is not None:
                        # Determine unit based on metric name or value
                        unit = None
                        metric_str = str(metric_name).lower()
                        if 'crore' in metric_str or 'cr' in metric_str:
                            unit = "Cr"
                        elif '%' in str(metric_value) or 'ratio' in metric_str or 'percent' in metric_str:
                            unit = "%"
                        elif '₹' in str(metric_value) or 'rs' in metric_str or 'rupee' in metric_str:
                            unit = "₹"
                        
                        insert_metric(
                            conn, "COMPANY", None, symbol, exchange,
                            "ANNUAL", period_key, statement_group,
                            metric_name, numeric_value, unit
                        )
                        records_inserted += 1
    
    except Exception as e:
        logger.debug(f"Error inserting financial table {statement_name} for {symbol}: {e}")
    
    return records_inserted

def write_detailed_log(
    conn: duckdb.DuckDBPyConnection,
    job_id: str,
    connection_id: Optional[int],
    connection_name: Optional[str],
    symbol: Optional[str],
    exchange: Optional[str],
    action: str,
    message: str,
    company_name: Optional[str] = None,
    symbol_index: Optional[int] = None,
    total_symbols: Optional[int] = None,
    records_count: Optional[int] = None
):
    """
    Write detailed log entry for Screener scraping.
    
    Args:
        conn: DuckDB connection to screener database
        job_id: Job ID for the scraping run
        connection_id: Connection ID
        connection_name: Connection name
        symbol: Symbol being processed (optional, URL symbol)
        exchange: Exchange code (optional)
        action: Action type (START, FETCH, INSERT, STOP, ERROR)
        message: Log message
        company_name: Company name for display (optional)
        symbol_index: Current symbol index (e.g., 1, 2, 3...) for count/total
        total_symbols: Total number of symbols in the job
        records_count: Number of records scraped (for INSERT actions)
    """
    try:
        # Get next ID for log entry
        try:
            max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) FROM screener_detailed_logs").fetchone()
            next_id = (max_id_result[0] if max_id_result else 0) + 1
        except:
            next_id = 1
        
        conn.execute("""
            INSERT INTO screener_detailed_logs 
            (id, job_id, connection_id, connection_name, symbol, exchange, company_name, 
             symbol_index, total_symbols, action, message, records_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            next_id, job_id, connection_id, connection_name, symbol, exchange, company_name,
            symbol_index, total_symbols, action, message, records_count
        ])
    except Exception as e:
        logger.warning(f"Failed to write detailed log: {e}")

def scrape_news(symbol: str, exchange: str, conn: duckdb.DuckDBPyConnection, base_url: Optional[str] = None) -> int:
    """Scrape news/announcements for a symbol"""
    records_inserted = 0
    try:
        # TODO: Implement news scraping
        pass
    except Exception as e:
        logger.error(f"Failed to scrape news for {symbol}: {e}")
        raise
    
    return records_inserted

def scrape_corporate_actions(symbol: str, exchange: str, conn: duckdb.DuckDBPyConnection, base_url: Optional[str] = None) -> int:
    """Scrape corporate actions for a symbol"""
    records_inserted = 0
    try:
        # TODO: Implement corporate actions scraping
        pass
    except Exception as e:
        logger.error(f"Failed to scrape corporate actions for {symbol}: {e}")
        raise
    
    return records_inserted

def scrape_symbol(symbol: str, exchange: str, conn: duckdb.DuckDBPyConnection, connection_type: Optional[str] = None, base_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Scrape all data for a single symbol
    
    Args:
        symbol: Symbol to scrape
            - NSE: Company name (e.g., "Reliance Industries")
            - BSE: Exchange token ID (e.g., "500325")
        exchange: Exchange code (NSE or BSE)
        conn: DuckDB connection to screener database
        connection_type: Type of connection (e.g., "WEBSITE_SCRAPING")
        base_url: Base URL template with {symbol} placeholder
    
    Returns:
        Dictionary with scraping results
    """
    if not symbol or not symbol.strip():
        error_msg = f"Invalid symbol: cannot be empty (received: '{symbol}')"
        logger.error(f"[SCRAPING] {error_msg}")
        return {
            "symbol": symbol or "UNKNOWN",
            "exchange": exchange or "UNKNOWN",
            "success": False,
            "records_inserted": 0,
            "error": error_msg
        }
    
    symbol_clean = str(symbol).strip()
    logger.info(f"[SCRAPING] scrape_symbol called: symbol='{symbol_clean}', exchange='{exchange}'")
    
    result = {
        "symbol": symbol_clean,
        "exchange": exchange,
        "success": False,
        "records_inserted": 0,
        "error": None
    }
    
    try:
        records = 0
        fundamentals_count = 0
        news_count = 0
        actions_count = 0
        
        if connection_type == 'WEBSITE_SCRAPING' or connection_type is None:
            fundamentals_count, extracted_company_name = scrape_fundamentals(symbol_clean, exchange, conn, base_url)
            records += fundamentals_count
            # Store extracted company name in result if available
            if extracted_company_name:
                result["company_name"] = extracted_company_name
            
            news_count = scrape_news(symbol_clean, exchange, conn, base_url)
            records += news_count
            
            actions_count = scrape_corporate_actions(symbol_clean, exchange, conn, base_url)
            records += actions_count
        
        result["success"] = True
        result["records_inserted"] = records
        
        # Detailed logging is done at API level, keep summary here for debugging
        logger.debug(f"[SCRAPING] Scraped Data Summary for {symbol_clean}:")
        logger.debug(f"[SCRAPING]   Fundamentals: {fundamentals_count} records")
        logger.debug(f"[SCRAPING]   News: {news_count} records")
        logger.debug(f"[SCRAPING]   Corporate Actions: {actions_count} records")
        logger.debug(f"[SCRAPING]   Total Records: {records}")
        
    except Exception as e:
        result["error"] = str(e)
        # Error logging is done at API level with proper format
        logger.debug(f"[SCRAPING] Full error for '{symbol_clean}': {e}", exc_info=True)
    
    return result

def get_active_symbols(conn: duckdb.DuckDBPyConnection) -> List[Dict[str, str]]:
    """
    Get active symbols from Symbols database for scraping
    
    IMPORTANT: This function returns symbols from BOTH NSE and BSE exchanges.
    If a company exists in both exchanges, it will be scraped twice (once for each exchange).
    No deduplication is performed - each exchange is processed independently.
    
    URL Logic:
    - NSE: Uses company name (from 'name' column) - e.g., "Reliance Industries" -> "RELIANCEINDUSTRIES"
    - BSE: Uses exchange_token ID - e.g., "500325" -> "500325"
    
    Returns:
        List of dictionaries with 'symbol', 'exchange', and 'display_name' keys
        - symbol: Company name for NSE (for URL), exchange_token ID for BSE (for URL)
        - exchange: Exchange code (NSE or BSE)
        - display_name: Company name for NSE, ID for BSE (for logging)
    """
    symbols_db_path = os.path.join(
        os.path.abspath(settings.DATA_DIR),
        "symbols",
        "symbols.duckdb"
    )
    
    if not os.path.exists(symbols_db_path):
        logger.warning(f"Symbols database not found at {symbols_db_path}")
        return []
    
    try:
        logger.info(f"[SYMBOL_SELECTION] Loading symbols database from: {symbols_db_path}")
        
        # Attach symbols database
        conn.execute(f"ATTACH '{symbols_db_path}' AS symbols_db")
        logger.info(f"[SYMBOL_SELECTION] ✓ Databases loaded")
        
        # Query symbols with all required fields
        # Get both NSE and BSE symbols - no deduplication, scrape both exchanges
        # Only process symbols with instrument_type = 'CASH' or 'EQ' (both represent cash/equity instruments)
        query = conn.execute("""
            SELECT name, exchange, exchange_token, trading_symbol
            FROM symbols_db.symbols
            WHERE status = 'ACTIVE'
            AND (instrument_type = 'CASH' OR instrument_type = 'EQ')
            AND (
                (exchange = 'NSE' AND name IS NOT NULL AND TRIM(name) != '') OR
                (exchange = 'BSE' AND exchange_token IS NOT NULL AND TRIM(exchange_token) != '')
            )
            ORDER BY exchange, UPPER(COALESCE(name, exchange_token))
        """)
        
        rows = query.fetchall()
        conn.execute("DETACH symbols_db")
        
        logger.info(f"[SYMBOL_SELECTION] Fetched {len(rows)} symbols from database")
        
        symbols_list = []
        seen_symbols = set()  # Track to avoid exact duplicates (same symbol + exchange)
        
        for row_idx, row in enumerate(rows):
            name = row[0]  # name column
            exchange = row[1]  # exchange column
            exchange_token = row[2]  # exchange_token column
            trading_symbol = row[3] if len(row) > 3 else None  # trading_symbol column (optional)
            
            exchange_str = str(exchange).strip().upper() if exchange else ""
            
            # Determine symbol based on exchange
            if exchange_str == 'NSE':
                # NSE: Use company name (as-is, no changes)
                if name and str(name).strip():
                    symbol_value = str(name).strip()
                    # Create unique key to avoid exact duplicates
                    unique_key = f"NSE:{symbol_value}"
                    if unique_key not in seen_symbols:
                        seen_symbols.add(unique_key)
                        symbols_list.append({
                            "symbol": symbol_value,  # Company name for URL
                            "exchange": exchange_str,
                            "display_name": symbol_value  # Company name for display
                        })
            elif exchange_str == 'BSE':
                # BSE: Use exchange_token ID
                if exchange_token and str(exchange_token).strip():
                    symbol_value = str(exchange_token).strip()
                    # Create unique key to avoid exact duplicates
                    unique_key = f"BSE:{symbol_value}"
                    if unique_key not in seen_symbols:
                        seen_symbols.add(unique_key)
                        # Try to get company name for display, fallback to ID
                        display_name = str(name).strip() if name and str(name).strip() else symbol_value
                        symbols_list.append({
                            "symbol": symbol_value,  # ID for URL
                            "exchange": exchange_str,
                            "display_name": display_name  # Company name for display (or ID if name not available)
                        })
        
        nse_count = sum(1 for s in symbols_list if s['exchange'] == 'NSE')
        bse_count = sum(1 for s in symbols_list if s['exchange'] == 'BSE')
        
        logger.info(f"[SYMBOL_SELECTION] Successfully prepared {len(symbols_list)} symbols for scraping")
        logger.info(f"[SYMBOL_SELECTION] ✓ NSE symbols: {nse_count} (will be scraped)")
        logger.info(f"[SYMBOL_SELECTION] ✓ BSE symbols: {bse_count} (will be scraped)")
        logger.info(f"[SYMBOL_SELECTION] Total symbols to scrape from BOTH exchanges: {len(symbols_list)}")
        
        return symbols_list
        
    except Exception as e:
        logger.error(f"[SYMBOL_SELECTION] Error getting active symbols: {e}", exc_info=True)
        try:
            conn.execute("DETACH symbols_db")
        except:
            pass
        return []

# Initialize database on module load
try:
    init_screener_database()
except Exception as e:
    logger.warning(f"Could not initialize Screener database on module load: {e}")
