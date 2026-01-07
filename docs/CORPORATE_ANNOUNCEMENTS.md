# Corporate Announcements Feature

## Overview

The Corporate Announcements feature provides real-time ingestion and display of corporate announcements from TrueData via WebSocket, with storage in DuckDB and a REST API fallback mechanism. The system automatically filters duplicates, blank entries, and matches symbols with company names from the symbols database.

**Last Updated**: January 2026

## Architecture

### Components

1. **WebSocket Worker** (`announcements_websocket_worker.py`)
   - Maintains persistent connection to TrueData Corporate Announcements WebSocket
   - Receives real-time announcement messages
   - Parses and validates messages
   - Queues valid announcements for database storage

2. **Database Writer** (`announcements_db_writer.py`)
   - Single-threaded service that reads from message queue
   - Writes announcements to DuckDB in batches
   - Handles duplicate detection and blank entry filtering
   - Ensures data integrity

3. **Announcements Manager** (`announcements_manager.py`)
   - Manages lifecycle of WebSocket workers
   - Controls worker start/stop based on connection status
   - Provides status monitoring

4. **REST API** (`announcements.py`)
   - Serves announcements to frontend
   - Provides search functionality
   - Handles attachment downloads
   - Implements REST API fallback for missing data

### Data Flow

```
TrueData WebSocket → WebSocket Worker → Message Queue → Database Writer → DuckDB
                                                              ↓
                                                         Frontend API
```

## Database Schema

### Table: `corporate_announcements`

```sql
CREATE TABLE corporate_announcements (
    announcement_id VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    symbol_nse VARCHAR,
    symbol_bse VARCHAR,
    exchange VARCHAR,
    headline VARCHAR,
    description TEXT,
    category VARCHAR,
    announcement_datetime TIMESTAMP,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    attachment_id VARCHAR,
    raw_payload TEXT
)
```

### Indexes

- `idx_announcements_datetime` on `announcement_datetime DESC`
- `idx_announcements_received_at` on `received_at DESC`
- `idx_announcements_symbol` on `symbol`

## Configuration

### TrueData Connection

1. **WebSocket URL**: `wss://corp.truedata.in:9092`
   - **Port 9092** is required for Corporate Announcements
   - Port 8086 is for Market Data (NOT announcements)
   - Port 9094 is incorrect and will be overridden

2. **Authentication**: Query parameters
   - Format: `wss://corp.truedata.in:9092?user=<USERNAME>&password=<PASSWORD>`

3. **Connection Setup**:
   - Go to Admin → Connections → TrueData
   - Configure username and password
   - Enable the connection to start WebSocket worker

### Database Location

- **Path**: `{DATA_DIR}/Company Fundamentals/corporate_announcements.duckdb`
- Created automatically on first use

## Frontend Features

### Dashboard Integration

The Corporate Announcements are displayed in the Dashboard under the "Latest Corporate Announcements" tab.

**Features:**
- **Live Updates**: Automatically polls for new announcements every 10 seconds (when on page 1, no search)
- **Search Functionality**: Search by symbol, company name, headline, or description
- **Pagination**: Navigate through announcements with configurable page size (10, 25, 50, 100)
- **Real-time Indicators**: Shows "Live" status and new announcement count
- **Attachment Downloads**: Click download icon to fetch and download PDF attachments
- **Expandable Rows**: Click chevron to expand and view full description

**Search Fields:**
- Symbol (NSE/BSE)
- Company Name (from symbols database)
- Headline
- Description

**UI Components:**
- Search input with Search and Clear buttons
- Loading spinner during data fetch
- Empty state messages
- Pagination controls
- Last update timestamp

## API Endpoints

### Get Announcements

```http
GET /api/v1/announcements?limit=25&offset=0&search=<query>
```

**Parameters:**
- `limit` (default: 100, max: 1000): Number of results per page
- `offset` (default: 0): Pagination offset (for page navigation)
- `search` (optional): Search term - searches in symbol, company name, headline, and description

**Search Behavior:**
- Case-insensitive search
- Partial matching (LIKE query)
- Searches across multiple fields simultaneously
- Returns DISTINCT results to prevent duplicates

**Response:**
```json
{
  "announcements": [
    {
      "announcement_id": "12345",
      "symbol": "RELIANCE",
      "symbol_nse": "RELIANCE",
      "symbol_bse": null,
      "exchange": "NSE",
      "headline": "Board Meeting",
      "description": "Board meeting scheduled...",
      "category": "Board Meeting",
      "announcement_datetime": "2026-01-05T12:00:00",
      "received_at": "2026-01-05T12:00:00Z",
      "attachment_id": "att123",
      "company_name": "Reliance Industries Ltd"
    }
  ],
  "total": 100,
  "limit": 25,
  "offset": 0
}
```

### Get Announcement Status

```http
GET /api/v1/announcements/status
```

**Response:**
```json
{
  "workers": [
    {
      "connection_id": 3,
      "connection_name": "TrueData Production",
      "is_enabled": true,
      "worker_running": true,
      "worker_exists": true,
      "queue_size": 5,
      "connection_status": "CONNECTED",
      "connection_health": "UP"
    }
  ],
  "total_announcements": 1250,
  "latest_announcement": {
    "announcement_id": "12345",
    "headline": "Board Meeting",
    "received_at": "2026-01-05T12:00:00Z"
  },
  "db_writer_running": true,
  "message_queue_size": 2
}
```

### Download Attachment

```http
GET /api/v1/announcements/{announcement_id}/attachment/{attachment_id}
```

**Response:** Binary file stream

## Data Validation

### Blank Entry Filtering

The system automatically filters out:
- Messages with no `announcement_id`
- Messages with no `headline` AND no `description`
- Messages where `headline` is just "-", "", "null", or "None"

### Duplicate Detection

- **Database Level**: `UNIQUE(announcement_id)` constraint prevents duplicates
- **Application Level**: Check performed before insert for efficiency
- **API Level**: `SELECT DISTINCT` ensures no duplicates in query results
- **Insert Strategy**: Uses `INSERT OR IGNORE` to handle race conditions
- If duplicate found, the message is skipped (no insertion)
- Duplicate count is logged for monitoring

## Symbol Extraction

The parser tries multiple methods to extract symbols:

1. **Direct Fields**: `symbol`, `symbol_nse`, `symbol_bse`, `Symbol`, `SYMBOL`, etc.
2. **Nested Structures**: Checks `nse.symbol`, `bse.symbol` if present
3. **Exchange Inference**: Uses `exchange` field to determine NSE vs BSE
4. **Headline Extraction**: Regex pattern matching for symbol codes in headlines

### Symbol Matching and Company Name Resolution

**Automatic Symbol Matching:**
- When an announcement arrives without symbols, the system attempts to match it with the symbols database
- Matching is done by searching for company names in the announcement headline/description
- Only matches equity instruments (EQ) to avoid matching options/futures
- Updates the announcement with matched symbols before insertion

**Company Name Resolution:**
- Company names are resolved by joining with the symbols database
- Joins on `symbol_nse` or `symbol_bse` matching `trading_symbol`
- Requires symbols database to be attached
- Falls back to NULL if no match found
- Uses `COALESCE` to show best available company name (NSE first, then BSE)

## REST API Fallback

If a `symbol` parameter is provided and no data exists in DuckDB:
1. Calls TrueData REST API (`getannouncementsforcompanies2`)
2. Fetches last 7 days of announcements
3. Stores results in DuckDB
4. Returns fetched data

**Note**: This is a one-time fetch. If "No data exists" response is received, empty state is stored and not retried automatically.

## Troubleshooting

### WebSocket Not Connecting

1. **Check Port**: Must use port 9092 (not 8086 or 9094)
2. **Check Credentials**: Verify username/password in connection settings
3. **Check Logs**: Look for connection errors in backend logs
4. **Restart Worker**: Toggle connection OFF then ON

### Messages Not Parsing

1. **Check Logs**: Look for "Sample WebSocket message structure" logs
2. **Verify Format**: Messages should be valid JSON
3. **Check Validation**: Ensure messages have headline or description

### Symbols Not Appearing

1. **Check Database**: Verify symbols are stored in `symbol_nse` or `symbol_bse` columns
2. **Check Symbols DB**: Ensure symbols database is attached and has matching records
3. **Check Parser**: Review logs for symbol extraction attempts
4. **Manual Extraction**: Parser may extract from headlines if not in message

### Duplicates Appearing

1. **Run Cleanup Script**: `python scripts/maintenance/clean_announcements.py`
2. **Check announcement_id**: Ensure unique IDs are being generated
3. **Verify Deduplication**: Check logs for duplicate detection

### Blank Entries

1. **Run Cleanup Script**: `python scripts/maintenance/clean_announcements.py`
2. **Check Validation**: New entries should be filtered automatically
3. **Review Parser**: Ensure validation logic is working

## Maintenance Scripts

### Clean Announcements

```bash
cd backend
python scripts/maintenance/clean_announcements.py
```

**Actions:**
- Removes blank entries (no headline/description or invalid headlines)
- Removes duplicate entries (keeps earliest `received_at`)
- Shows before/after statistics
- Safe to run multiple times

**Example Output:**
```
Total announcements before cleanup: 2408
Found 0 blank entries
Found 0 announcement_ids with duplicates (0 extra copies)

[OK] No cleanup needed - database is clean!
```

### Associate Symbols to Announcements

```bash
cd backend
python scripts/maintenance/associate_symbols_to_announcements.py
```

**Actions:**
- Backfills missing symbols for existing announcements
- Matches by company name in headline/description/raw_payload
- Updates announcements with matched symbols
- Shows progress and statistics

**Use Case:**
- Run after adding new symbols to the symbols database
- Fix announcements that arrived before symbol matching was implemented
- Update announcements that couldn't be matched initially

## Monitoring

### Log Messages to Watch

1. **Connection**: `[ANNOUNCEMENTS] ✅ Connected to Corporate Announcements WebSocket`
2. **Messages**: `Received announcement: <id> - <headline>`
3. **Errors**: `Failed to parse announcement message`
4. **Warnings**: `Skipping announcement with no headline or description`

### Status Endpoint

Use `/api/v1/announcements/status` to monitor:
- Worker running status
- Queue sizes
- Total announcements
- Latest announcement timestamp

## Best Practices

1. **Regular Cleanup**: Run cleanup script periodically to remove blanks/duplicates
2. **Monitor Queue**: Watch queue size - if growing, database writer may be slow
3. **Check Logs**: Review parsing errors to identify message format issues
4. **Symbol Database**: Keep symbols database updated for company name resolution
5. **Connection Health**: Monitor connection status and auto-reconnect behavior

## User Interface

### Dashboard Page

**Location**: Dashboard → "Latest Corporate Announcements" tab

**Features:**
1. **Search Bar**
   - Search by symbol, company name, headline, or description
   - Enter key to search
   - Clear button to reset search
   - Real-time search with proper loading states

2. **Announcements Table**
   - Date & Time: Shows announcement date/time and received time
   - Company: Company name from symbols database (or "-" if not found)
   - Symbol: Trading symbol (NSE/BSE format)
   - Headline: Announcement headline
   - Category: Announcement category
   - Actions: Expand/collapse description, download attachment

3. **Pagination**
   - Page size selector (10, 25, 50, 100)
   - Page navigation with ellipsis
   - Shows current range and total count

4. **Live Updates**
   - Automatic polling every 10 seconds (when on page 1, no search)
   - Shows "Live" indicator with pulsing dot
   - Displays count of new announcements
   - Last update timestamp

5. **Loading States**
   - Spinner during data fetch
   - Disabled buttons during loading
   - Clear error messages

## Limitations

1. **Symbol Extraction**: May not always extract symbols if not in message format
2. **Company Names**: Requires symbols database with matching trading_symbols
3. **REST Fallback**: Only triggers when symbol parameter provided and no data exists
4. **WebSocket**: Requires persistent connection - reconnects automatically on failure
5. **Search**: Case-insensitive partial matching - exact matches may be needed for some symbols

## Related Documentation

- [TrueData Connection Guide](./TRUEDATA_CONNECTION.md)
- [Troubleshooting Guide](./TROUBLESHOOTING.md)
- [API Documentation](./API.md)

