# Symbols Management System Documentation

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Database Schema](#database-schema)
4. [Symbol Data Model](#symbol-data-model)
5. [Upload Workflow](#upload-workflow)
6. [Series Lookup System](#series-lookup-system)
7. [API Endpoints](#api-endpoints)
8. [UI Components](#ui-components)
9. [Transformation Scripts](#transformation-scripts)
10. [Scheduled Uploads](#scheduled-uploads)
11. [Best Practices](#best-practices)

---

## Overview

The Symbols Management System is a comprehensive solution for managing financial instrument data (stocks, derivatives, bonds, etc.) across multiple exchanges (NSE, BSE). It provides:

- **Manual and Automated Uploads**: Support for CSV, Excel, JSON, and Parquet files
- **Data Transformation**: Python-based transformation scripts for data normalization
- **Series Descriptions**: Automatic lookup and display of series code descriptions
- **Scheduled Imports**: Automated scheduled uploads from URLs or APIs
- **Real-time Processing**: Background job processing with progress tracking
- **Status Management**: Active/Inactive status tracking for symbols

---

## Architecture

### Technology Stack
- **Backend**: FastAPI (Python)
- **Database**: DuckDB (embedded analytical database)
- **Frontend**: Next.js (React)
- **File Processing**: Pandas (DataFrame operations)

### Database Location
- **Path**: `data/symbols/symbols.duckdb`
- **Format**: DuckDB (analytical SQL database)

### Key Components

```
┌─────────────────┐
│   UI (Next.js)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI Backend│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DuckDB Database│
│  - symbols      │
│  - series_lookup│
│  - upload_logs  │
│  - schedulers   │
└─────────────────┘
```

---

## Database Schema

### `symbols` Table

The main table storing all symbol/instrument data.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | INTEGER | Primary key, auto-increment | PRIMARY KEY |
| `exchange` | VARCHAR | Exchange code (NSE, BSE) | NOT NULL |
| `trading_symbol` | VARCHAR | Trading symbol (e.g., RELIANCE-EQ) | NOT NULL |
| `exchange_token` | VARCHAR | Exchange-specific token/ID | NULLABLE |
| `name` | VARCHAR | Company/instrument name | NULLABLE |
| `instrument_type` | VARCHAR | Type (EQ, FUT, OPT, INDEX, etc.) | NULLABLE |
| `segment` | VARCHAR | Market segment (CASH, FNO, etc.) | NULLABLE |
| `series` | VARCHAR | Series code (EQ, BE, F, etc.) | NULLABLE |
| `isin` | VARCHAR | ISIN identifier | NULLABLE |
| `expiry_date` | DATE | Expiry date (for derivatives) | NULLABLE |
| `strike_price` | DOUBLE | Strike price (for options) | NULLABLE |
| `lot_size` | INTEGER | Lot size | NULLABLE |
| `status` | VARCHAR | ACTIVE or INACTIVE | DEFAULT 'ACTIVE' |
| `source` | VARCHAR | Upload source (MANUAL, AUTO, etc.) | DEFAULT 'MANUAL' |
| `created_at` | TIMESTAMP | Creation timestamp | NULLABLE |
| `updated_at` | TIMESTAMP | Last update timestamp | NULLABLE |
| `last_updated_at` | TIMESTAMP | Last update timestamp (for tracking) | NULLABLE |

**Unique Constraint**: `(exchange, trading_symbol)` - Ensures no duplicate symbols per exchange.

**Indexes**:
- `idx_symbols_exchange` on `exchange`
- `idx_symbols_trading_symbol` on `trading_symbol`
- `idx_symbols_status` on `status`

### `series_lookup` Table

Lookup table for series code descriptions.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `series_code` | VARCHAR | Series code (EQ, BE, F, etc.) | PRIMARY KEY |
| `description` | VARCHAR | Human-readable description | NOT NULL |

**Index**: `idx_series_lookup_code` on `series_code`

**Data Source**: Populated from `data/symbols/Series.csv`

### `series_lookup_metadata` Table

Tracks when series lookup data was last loaded.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `id` | INTEGER | Primary key (always 1) | PRIMARY KEY, CHECK (id = 1) |
| `csv_last_modified` | TIMESTAMP | CSV file modification time | NULLABLE |
| `last_loaded_at` | TIMESTAMP | When data was last loaded | DEFAULT CURRENT_TIMESTAMP |

### `upload_logs` Table

Tracks all upload operations.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `job_id` | VARCHAR | Unique job identifier (UUID) |
| `file_name` | VARCHAR | Source filename |
| `upload_type` | VARCHAR | MANUAL or AUTO |
| `triggered_by` | VARCHAR | User/system identifier |
| `started_at` | TIMESTAMP | Job start time |
| `ended_at` | TIMESTAMP | Job end time |
| `duration_seconds` | INTEGER | Processing duration |
| `total_rows` | INTEGER | Total rows processed |
| `inserted_rows` | INTEGER | New rows inserted |
| `updated_rows` | INTEGER | Existing rows updated |
| `failed_rows` | INTEGER | Failed rows |
| `status` | VARCHAR | Status (PENDING, RUNNING, SUCCESS, FAILED, etc.) |
| `progress_percentage` | INTEGER | Progress (0-100) |
| `error_summary` | VARCHAR | Error details |
| `created_at` | TIMESTAMP | Log creation time |

**Index**: `idx_upload_logs_job_id` on `job_id`

### `schedulers` Table

Stores scheduled upload configurations.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `name` | VARCHAR | Scheduler name |
| `description` | VARCHAR | Description |
| `mode` | VARCHAR | RUN_ONCE, INTERVAL, or CRON |
| `interval_value` | INTEGER | Interval value |
| `interval_unit` | VARCHAR | minutes, hours, days |
| `cron_expression` | VARCHAR | Cron expression (for CRON mode) |
| `script_id` | INTEGER | Transformation script ID |
| `is_active` | BOOLEAN | Active status |
| `sources` | TEXT | JSON array of source configurations |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Update time |
| `last_run_at` | TIMESTAMP | Last run time |
| `next_run_at` | TIMESTAMP | Next scheduled run |
| `created_by` | INTEGER | User ID who created |

### `transformation_scripts` Table

Stores Python transformation scripts.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `name` | VARCHAR | Script name (unique) |
| `description` | VARCHAR | Description |
| `content` | TEXT | Python script code |
| `version` | INTEGER | Version number |
| `created_by` | INTEGER | User ID |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Update time |
| `last_used_at` | TIMESTAMP | Last usage time |

---

## Symbol Data Model

### Symbol Fields

#### Required Fields
- **`exchange`**: Exchange code (e.g., "NSE", "BSE")
- **`trading_symbol`**: Trading symbol (e.g., "RELIANCE-EQ", "500325")

#### Optional Fields
- **`exchange_token`**: Exchange-specific identifier
- **`name`**: Company/instrument name
- **`instrument_type`**: EQ (Equity), FUT (Futures), OPT (Options), INDEX
- **`segment`**: CASH, FNO (Futures & Options), etc.
- **`series`**: Series code (EQ, BE, F, etc.)
- **`isin`**: ISIN code (e.g., "INE467B01029")
- **`expiry_date`**: For derivatives
- **`strike_price`**: For options
- **`lot_size`**: Trading lot size

#### System Fields
- **`status`**: ACTIVE or INACTIVE
- **`source`**: MANUAL, AUTO, SCHEDULED
- **`created_at`**: Creation timestamp
- **`updated_at`**: Last update timestamp
- **`last_updated_at`**: Last modification timestamp

### Example Symbol

```json
{
  "id": 12345,
  "exchange": "NSE",
  "trading_symbol": "RELIANCE-EQ",
  "exchange_token": "2885",
  "name": "RELIANCE INDUSTRIES LTD",
  "instrument_type": "EQ",
  "segment": "CASH",
  "series": "EQ",
  "series_description": "Normal Equity",
  "isin": "INE467B01029",
  "expiry_date": null,
  "strike_price": null,
  "lot_size": 1,
  "status": "ACTIVE",
  "source": "MANUAL",
  "created_at": "2026-01-01T10:00:00Z",
  "updated_at": "2026-01-02T12:30:00Z",
  "last_updated_at": "2026-01-02T12:30:00Z"
}
```

---

## Upload Workflow

### Manual Upload Process

1. **File Selection**: User selects CSV/Excel/JSON/Parquet file
2. **File Parsing**: System parses file based on extension
3. **Preview Generation**: System creates preview with first 10 rows
4. **User Confirmation**: User reviews preview and optionally applies transformation script
5. **Background Processing**: System processes upload in background
6. **Status Tracking**: Real-time status updates via polling
7. **Completion**: Success/failure notification with summary

### Automatic Upload Process

1. **Source Configuration**: User provides URL or API endpoint
2. **Authentication Setup**: Optional headers/auth tokens
3. **Download**: System downloads file from source
4. **File Detection**: Auto-detect file type (CSV, Excel, etc.)
5. **Transformation**: Apply transformation script if configured
6. **Processing**: Same as manual upload from step 5

### Processing Logic

#### Insert/Update Strategy

The system uses **UPSERT** logic:
- If `(exchange, trading_symbol)` exists → **UPDATE** existing record
- If new → **INSERT** new record

This ensures:
- No duplicates per exchange
- Data stays current
- Historical tracking via timestamps

#### Bulk Processing

- Processes data in chunks (1000 rows at a time)
- Updates progress in real-time
- Handles errors gracefully (continues on errors)
- Tracks inserted vs updated counts

### Supported File Formats

| Format | Extension | Parser |
|--------|-----------|--------|
| CSV | `.csv` | Pandas `read_csv()` |
| Excel | `.xlsx`, `.xls` | Pandas `read_excel()` |
| JSON | `.json` | Pandas `read_json()` |
| Parquet | `.parquet` | Pandas `read_parquet()` |

### Required Columns

Minimum required columns:
- `exchange` (or `Exchange`)
- `trading_symbol` (or `Trading Symbol`)

All other columns are optional and mapped if present.

---

## Series Lookup System

### Overview

The series lookup system provides human-readable descriptions for series codes (e.g., "EQ" → "Normal Equity").

### CSV File Structure

**Location**: `data/symbols/Series.csv`

**Format**:
```csv
Series Code,Description,Trading Rules,Primary Usage
EQ,Normal Equity,Intraday + Delivery,Main equity trading
BE,Trade-to-Trade Book Entry,Delivery only; no intraday,Stocks under surveillance
F,Fixed-Income/Debt,Debt market rules apply,Corporate bonds and debentures
N0-N9/NA-NZ,Non-Convertible Debentures,Delivery only; rolling settlement,Corporate debt instruments
```

### Range Expansion

The system automatically expands range patterns:
- `N0-N9` → Expands to N0, N1, N2, ..., N9
- `NA-NZ` → Expands to NA, NB, NC, ..., NZ
- `N0-N9/NA-NZ` → Expands both ranges

### Loading Mechanism

1. **On Startup**: System checks if CSV is newer than last load
2. **Auto-Reload**: If CSV modified, automatically reloads data
3. **Manual Reload**: UI button triggers reload without restart

### API Integration

When fetching symbols, the API performs a LEFT JOIN:
```sql
SELECT s.*, sl.description as series_description
FROM symbols s
LEFT JOIN series_lookup sl ON s.series = sl.series_code
```

This ensures:
- Symbols always include series_description if available
- No performance impact (indexed lookup)
- Real-time updates after reload

### Reload API

**Endpoint**: `POST /admin/symbols/series-lookup/reload?force=false`

**Parameters**:
- `force` (boolean): Force reload even if CSV unchanged

**Response**:
```json
{
  "success": true,
  "message": "Successfully loaded 45 series entries",
  "reloaded": true,
  "entries_count": 45
}
```

---

## API Endpoints

### Symbols Management

#### Get Symbols (Paginated)
```
GET /admin/symbols
```

**Query Parameters**:
- `page` (int): Page number (default: 1)
- `page_size` (int): Items per page (default: 25)
- `search` (string): Search term (searches multiple fields)
- `exchange` (string): Filter by exchange
- `status` (string): Filter by status (ACTIVE/INACTIVE)
- `expiry` (string): Filter by expiry (today/skipped)
- `sort_by` (string): Sort field (last_updated/name/symbol)

**Response**:
```json
{
  "items": [/* SymbolResponse[] */],
  "total": 1000,
  "page": 1,
  "page_size": 25,
  "total_pages": 40
}
```

#### Get Symbol Statistics
```
GET /admin/symbols/stats
```

**Response**:
```json
{
  "total": 1000,
  "skipped_symbols": 50,
  "last_updated": "2026-01-02T12:00:00Z",
  "last_update_duration": 120,
  "last_status": "Completed",
  "last_run_datetime": "2026-01-02T12:00:00Z",
  "last_upload_type": "MANUAL",
  "last_triggered_by": "user@example.com",
  "last_updated_rows": 950,
  "last_inserted_rows": 50
}
```

#### Bulk Update Status
```
PATCH /admin/symbols/status/bulk
```

**Body**:
```json
{
  "ids": [1, 2, 3],
  "status": "INACTIVE"
}
```

#### Bulk Delete
```
DELETE /admin/symbols/bulk
```

**Body**:
```json
{
  "ids": [1, 2, 3],
  "hard_delete": false
}
```

#### Delete All Symbols
```
DELETE /admin/symbols/delete_all
```

### Upload Endpoints

#### Manual Upload (Preview)
```
POST /admin/symbols/upload/manual
```

**Form Data**:
- `file`: File (CSV/Excel/JSON/Parquet)
- `script_id`: (optional) Transformation script ID

**Response**:
```json
{
  "preview_id": "uuid-here",
  "headers": ["exchange", "trading_symbol", "name"],
  "rows": [/* first 10 rows */],
  "total_rows": 1000
}
```

#### Confirm Upload
```
POST /admin/symbols/upload/confirm/{preview_id}
```

**Response**:
```json
{
  "job_id": "uuid-here",
  "message": "Upload started"
}
```

#### Auto Upload
```
POST /admin/symbols/upload/auto
```

**Body**:
```json
{
  "url": "https://example.com/symbols.csv",
  "headers": {"Authorization": "Bearer token"},
  "auth_type": "BEARER",
  "auth_value": "token",
  "file_type": "AUTO",
  "script_id": 1
}
```

#### Get Upload Status
```
GET /admin/symbols/upload/status/{job_id}
```

**Response**:
```json
{
  "status": "RUNNING",
  "processed": 500,
  "total": 1000,
  "inserted": 450,
  "updated": 50,
  "failed": 0,
  "percentage": 50
}
```

#### Get Upload Logs
```
GET /admin/symbols/upload/logs?limit=50&page=1
```

#### Cancel Upload
```
POST /admin/symbols/upload/{job_id}/cancel
```

### Series Lookup Endpoints

#### Reload Series Lookup
```
POST /admin/symbols/series-lookup/reload?force=false
```

### Transformation Scripts

#### List Scripts
```
GET /admin/symbols/scripts
```

#### Get Script
```
GET /admin/symbols/scripts/{id}
```

#### Create Script
```
POST /admin/symbols/scripts
```

**Body**:
```json
{
  "name": "My Transformation",
  "description": "Cleans up data",
  "content": "df['name'] = df['name'].str.upper()\nfinal_df = df"
}
```

#### Update Script
```
PUT /admin/symbols/scripts/{id}
```

#### Delete Script
```
DELETE /admin/symbols/scripts/{id}
```

### Schedulers

#### List Schedulers
```
GET /admin/symbols/schedulers
```

#### Get Scheduler
```
GET /admin/symbols/schedulers/{id}
```

#### Create Scheduler
```
POST /admin/symbols/schedulers
```

**Body**:
```json
{
  "name": "Daily NSE Import",
  "description": "Import NSE symbols daily",
  "mode": "INTERVAL",
  "interval_value": 24,
  "interval_unit": "hours",
  "script_id": 1,
  "is_active": true,
  "sources": [{
    "url": "https://example.com/symbols.csv",
    "headers": {},
    "file_type": "AUTO"
  }]
}
```

#### Update Scheduler
```
PUT /admin/symbols/schedulers/{id}
```

#### Delete Scheduler
```
DELETE /admin/symbols/schedulers/{id}
```

#### Trigger Scheduler
```
POST /admin/symbols/schedulers/{id}/trigger
```

---

## UI Components

### Symbols Page (`/admin/symbols`)

#### Features
- **Symbol Table**: Displays all symbols with pagination
- **Search**: Multi-field search (symbol, name, ISIN, etc.)
- **Filters**: Exchange, Status, Expiry filters
- **Bulk Actions**: Select multiple symbols for bulk operations
- **Upload Modal**: Manual file upload with preview
- **Status Tracking**: Real-time upload status
- **Series Descriptions**: Two-line display (code + description)

#### Key UI Elements

**Header Actions**:
- **Refresh Button**: Reload current page data
- **Reload Series Button**: Reload series lookup from CSV
- **Status Button**: View upload job status
- **Upload Symbols Button**: Open upload modal
- **Delete All Button**: Delete all symbols (dangerous)

**Symbol Table Columns**:
1. Checkbox (for selection)
2. Details (Exchange + Exchange Token)
3. Symbol (Trading Symbol)
4. Name (Company Name)
5. Type (Instrument Type)
6. Segment
7. **Series** (Code + Description in two lines)
8. ISIN
9. Expiry
10. Strike
11. Lot
12. Source
13. Status (ACTIVE/INACTIVE badge)
14. Last Updated

**Series Column Display**:
```
┌─────────────┐
│ EQ          │  ← Bold, larger font
│ Normal      │  ← Smaller, muted
│ Equity      │
└─────────────┘
```

### Upload Modal

#### Steps
1. **File Selection**: Choose file or configure URL
2. **Preview**: Review first 10 rows
3. **Script Selection**: Optional transformation script
4. **Confirmation**: Review and confirm
5. **Processing**: Background job with progress

### Status Modal

Shows detailed upload history:
- Job status (Running, Completed, Failed, etc.)
- Progress percentage
- Inserted/Updated/Failed counts
- Error details
- Timestamps

---

## Transformation Scripts

### Overview

Python scripts that transform uploaded data before insertion.

### Script Structure

Scripts receive a pandas DataFrame (`df`) and must return a DataFrame (`final_df`):

```python
# Example: Convert names to uppercase
df['name'] = df['name'].str.upper()

# Rename columns if needed
df = df.rename(columns={
    'Symbol': 'trading_symbol',
    'Exchange': 'exchange'
})

# Add computed columns
df['source'] = 'AUTO'

# Create final_df (required)
final_df = df
```

### Available Variables

- **`df`**: Input pandas DataFrame (can be modified)
- **`pd`**: Pandas module
- **`__builtins__`**: Standard Python builtins

### Script Execution

1. Script runs in isolated environment
2. Original DataFrame is copied (safe to modify)
3. Must create `final_df` variable
4. Returns transformed DataFrame
5. Errors are caught and reported

### Best Practices

- Always create `final_df` at the end
- Handle missing columns gracefully
- Validate data types
- Add comments for complex logic
- Test with sample data first

---

## Scheduled Uploads

### Scheduler Modes

#### 1. Run Once
Execute immediately and disable.

#### 2. Interval
Repeat at fixed intervals:
- `interval_value`: Number (e.g., 24)
- `interval_unit`: minutes, hours, days

Example: Every 24 hours

#### 3. Cron
Use cron expression for complex schedules:
- `cron_expression`: Standard cron format

Example: `0 2 * * *` (Daily at 2 AM)

### Source Configuration

Each scheduler can have multiple sources:

```json
{
  "url": "https://example.com/symbols.csv",
  "headers": {
    "Authorization": "Bearer token",
    "Accept": "application/json"
  },
  "auth_type": "BEARER",
  "auth_value": "token",
  "file_type": "AUTO"
}
```

### Execution Flow

1. Scheduler triggers at scheduled time
2. Downloads from configured sources
3. Applies transformation script if set
4. Processes upload (same as manual)
5. Logs results in upload_logs
6. Updates scheduler's last_run_at
7. Calculates next_run_at

### Status Tracking

Schedulers show:
- Last run status (SUCCESS/FAILED)
- Last run timestamp
- Next run timestamp
- Active/Inactive status

---

## Best Practices

### Data Upload

1. **Standardize Column Names**: Use consistent column naming
2. **Validate Data**: Ensure required fields (exchange, trading_symbol)
3. **Use Transformation Scripts**: Normalize data automatically
4. **Test First**: Upload small test file before bulk upload
5. **Monitor Progress**: Watch status during large uploads

### Series Descriptions

1. **Keep CSV Updated**: Update `Series.csv` with new series codes
2. **Reload After Changes**: Use "Reload Series" button after CSV updates
3. **Range Patterns**: Use range notation (N0-N9) for multiple codes

### Transformation Scripts

1. **Document Logic**: Add comments explaining transformations
2. **Handle Edge Cases**: Account for missing/null values
3. **Test Thoroughly**: Test with various data formats
4. **Version Control**: Keep track of script versions
5. **Reusable**: Make scripts generic for different sources

### Scheduled Uploads

1. **Error Handling**: Configure error notifications
2. **Monitoring**: Regularly check scheduler status
3. **Source Reliability**: Ensure sources are stable
4. **Rate Limiting**: Respect API rate limits
5. **Backup**: Keep backups of critical data

### Performance

1. **Bulk Operations**: Use bulk actions for multiple symbols
2. **Pagination**: Use appropriate page sizes
3. **Indexes**: Database indexes are auto-created
4. **Caching**: Preview data is cached temporarily

### Security

1. **Authentication**: All endpoints require admin authentication
2. **Validation**: Input validation on all endpoints
3. **File Limits**: File size limits enforced
4. **Script Isolation**: Transformation scripts run in isolated environment

---

## Troubleshooting

### Common Issues

#### Upload Fails
- **Check file format**: Ensure file is valid CSV/Excel/JSON
- **Check required columns**: Must have exchange and trading_symbol
- **Check file size**: Large files may timeout
- **Review errors**: Check upload logs for specific errors

#### Series Descriptions Not Showing
- **Check CSV file**: Ensure `Series.csv` exists
- **Reload data**: Click "Reload Series" button
- **Check series codes**: Ensure symbols have valid series codes
- **Review logs**: Check backend logs for loading errors

#### Scheduler Not Running
- **Check active status**: Ensure scheduler is active
- **Check cron expression**: Validate cron syntax
- **Check sources**: Ensure URLs are accessible
- **Review logs**: Check scheduler execution logs

#### Performance Issues
- **Reduce page size**: Use smaller page_size parameter
- **Optimize queries**: Add filters to reduce result set
- **Check database**: Verify database file isn't corrupted
- **Monitor resources**: Check server CPU/memory usage

---

## File Locations

### Backend
- **API**: `backend/app/api/v1/symbols.py`
- **Schemas**: `backend/app/schemas/symbol.py`
- **Database Init**: `backend/app/api/v1/symbols.py` (init_symbols_database)

### Frontend
- **Symbols Page**: `frontend/app/(main)/admin/symbols/page.tsx`
- **Upload Modal**: `frontend/components/UploadSymbolModal.tsx`
- **Status Modal**: `frontend/components/UploadStatusModal.tsx`
- **API Client**: `frontend/lib/api.ts`

### Data
- **Database**: `data/symbols/symbols.duckdb`
- **Series CSV**: `data/symbols/Series.csv`

---

## Version History

### Current Version
- Series lookup system with automatic reload
- Scheduled uploads with multiple sources
- Transformation scripts
- Real-time status tracking
- Bulk operations

---

## Support

For issues or questions:
1. Check this documentation
2. Review backend logs: `backend/logs/`
3. Check upload logs in UI
4. Review database schema integrity

---

**Last Updated**: January 2026




