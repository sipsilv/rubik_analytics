# Corporate Announcements Feature

## Overview

The Corporate Announcements feature provides real-time ingestion of corporate announcements from TrueData via WebSocket, with storage in DuckDB and a clean REST API to serve the UI. The system enforces strict deduplication using SHA-256 hashing at the database level.

**Last Updated**: January 2026

## Architecture

### Pipeline

```
TrueData WebSocket → Parse & Normalize → Generate Hash → Persist (DuckDB) → REST API → UI
```

### Key Principles

1. **Database-Level Deduplication**: Unique hash is PRIMARY KEY - duplicates rejected at DB level
2. **Immediate Persistence**: No batching - announcements stored immediately on receipt
3. **Source DateTime**: Always use announcement datetime from source, not fetch time
4. **UI Reads from DB Only**: UI never calls TrueData directly

### Components

1. **AnnouncementsService** (`announcements_service.py`)
   - Singleton service managing all announcement ingestion
   - Initializes database schema on startup
   - Manages WebSocket workers per TrueData connection

2. **WebSocketWorker** (within `announcements_service.py`)
   - Maintains persistent WebSocket connection to TrueData
   - Parses and normalizes incoming messages
   - Generates SHA-256 hash for deduplication
   - Persists announcements immediately

3. **REST API** (`announcements.py`)
   - Serves announcements from database to UI
   - Provides search and pagination
   - Handles attachment downloads

## Unique Key (CRITICAL)

Each announcement is uniquely identified by a SHA-256 hash of:
- **ISIN**
- **Exchange Symbol** (NSE or BSE)
- **Headline**
- **Announcement DateTime**

```python
combined = f"{isin}|{exchange_symbol}|{headline}|{datetime}"
unique_hash = sha256(combined).hexdigest()
```

This hash is the PRIMARY KEY in the database, ensuring:
- No duplicate records ever stored
- Deduplication enforced at database level (not just in-memory)
- Consistent identification across restarts

## Database Schema

### Table: `corporate_announcements`

```sql
CREATE TABLE corporate_announcements (
    unique_hash VARCHAR PRIMARY KEY,      -- SHA-256 hash of unique key components
    announcement_datetime TIMESTAMP,       -- Source datetime (UTC normalized)
    company_info VARCHAR,                  -- "Company Name | NSE: SYMBOL | BSE: SYMBOL | ISIN: CODE"
    headline VARCHAR,                      -- Announcement headline (trimmed, original casing)
    category VARCHAR,                      -- Category (or NULL if missing)
    attachments JSON,                      -- Array: [{file_name, file_url, mime_type}, ...]
    source_link VARCHAR,                   -- Source URL (exactly as received)
    created_at TIMESTAMP,                  -- System timestamp when stored
    raw_payload TEXT                       -- Original JSON for audit/debug
)
```

### Indexes

- `idx_ann_datetime` on `announcement_datetime DESC`
- `idx_ann_created_at` on `created_at DESC`

### company_info Format

Single column containing:
- Full Company Name
- NSE Symbol (prefixed with "NSE:")
- BSE Symbol (prefixed with "BSE:")
- ISIN (prefixed with "ISIN:")

Example: `"Reliance Industries Ltd | NSE: RELIANCE | BSE: 500325 | ISIN: INE002A01018"`

### attachments Format

JSON array of attachment objects:
```json
[
  {
    "file_name": "announcement.pdf",
    "file_url": "https://...",
    "mime_type": "application/pdf"
  }
]
```

Empty array `[]` if no attachments.

## API Endpoints

### Get Announcements

```http
GET /api/v1/announcements?limit=25&offset=0&search=<query>
```

**Parameters:**
- `limit` (default: 25, max: 100): Results per page
- `offset` (default: 0): Pagination offset
- `search` (optional): Search in headline, company_info, category

**Response:**
```json
{
  "announcements": [
    {
      "unique_hash": "abc123...",
      "announcement_datetime": "2026-01-07T14:30:00",
      "company_info": "Reliance Industries Ltd | NSE: RELIANCE",
      "company_name": "Reliance Industries Ltd",
      "symbol_nse": "RELIANCE",
      "symbol_bse": null,
      "isin": "INE002A01018",
      "headline": "Board Meeting Notice",
      "category": "Board Meeting",
      "attachments": [{"file_name": "notice.pdf", "file_url": "...", "mime_type": "application/pdf"}],
      "source_link": "https://...",
      "created_at": "2026-01-07T14:30:05"
    }
  ],
  "total": 1250,
  "limit": 25,
  "offset": 0
}
```

### Get Status

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
      "received": 150,
      "inserted": 145,
      "duplicates": 5,
      "errors": 0,
      "last_received_at": "2026-01-07T14:30:00Z"
    }
  ],
  "total_announcements": 1250,
  "latest_announcement": {
    "unique_hash": "abc123...",
    "headline": "Board Meeting Notice",
    "announcement_datetime": "2026-01-07T14:30:00"
  }
}
```

### Download Attachment

```http
GET /api/v1/announcements/{unique_hash}/attachment/{attachment_index}
```

Backend fetches and streams file - never exposes TrueData URL to UI.

## UI Columns

| # | Column | Content |
|---|--------|---------|
| 1 | Date & Time | `announcement_datetime` formatted |
| 2 | Company | Full Company Name (main) + NSE \| BSE \| ISIN (subtext) |
| 3 | Headline | Announcement headline |
| 4 | Category | Category or "-" |
| 5 | Attachments | Clickable download links for each attachment |
| 6 | Source Link | Clickable external link |

## Data Flow

1. **WebSocket Message Received**
   - Raw payload logged for audit
   - Received count incremented

2. **Parse & Normalize**
   - Extract fields from array or dict format
   - Normalize datetime to UTC
   - Build company_info string
   - Parse attachments array
   - Preserve original casing and URLs

3. **Generate Unique Hash**
   - Combine: ISIN + Exchange Symbol + Headline + DateTime
   - SHA-256 hash → 64-char hex string

4. **Persist to Database**
   - INSERT with unique_hash as PRIMARY KEY
   - If duplicate (constraint violation): log and skip
   - Else: inserted count incremented

5. **Serve to UI**
   - UI calls REST API
   - API queries database
   - Results ordered by announcement_datetime DESC

## Configuration

### TrueData Connection

- **WebSocket URL**: `wss://corp.truedata.in:9092`
- **Port 9092** required for Corporate Announcements
- **Authentication**: Query parameters (`?user=<USERNAME>&password=<PASSWORD>`)

### Database Location

`{DATA_DIR}/Company Fundamentals/corporate_announcements.duckdb`

## Logging

Every fetch cycle logs:
- Received count
- Inserted count
- Duplicate count
- Error count

Skipped records logged ONLY if they violate UNIQUE constraint.

## Troubleshooting

### Duplicates in UI

Should not happen - unique_hash PRIMARY KEY enforces deduplication.
If seen, verify database schema is correct (new schema with unique_hash).

### Missing Announcements

Check:
1. WebSocket worker running (`/api/v1/announcements/status`)
2. Logs for errors
3. Received vs Inserted counts

### Attachment Download Fails

Check:
1. Attachment URL in database
2. Network connectivity to source
3. Backend logs for fetch errors

### Schema Migration

If upgrading from old schema:
1. Old table renamed to `corporate_announcements_old`
2. New table created with new schema
3. Old data NOT automatically migrated (new data starts fresh)

## Strict Constraints

- NO caching layers
- NO in-memory deduplication only (must be DB-level)
- NO data enrichment beyond TrueData payload
- NO skipping records due to missing optional fields
- Store empty array if attachments missing
- Store NULL if category missing
