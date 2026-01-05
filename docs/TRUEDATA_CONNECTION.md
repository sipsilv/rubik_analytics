# TrueData Connection Guide

This guide covers everything you need to know about setting up and using TrueData connections in Rubik Analytics.

## Table of Contents

1. [Overview](#overview)
2. [Setup & Configuration](#setup--configuration)
3. [Authentication Methods](#authentication-methods)
4. [Token Management](#token-management)
5. [API Endpoints](#api-endpoints)
6. [WebSocket Connections](#websocket-connections)
7. [Troubleshooting](#troubleshooting)

---

## Overview

TrueData is a market data provider that offers real-time and historical market data, corporate information, and announcements. Rubik Analytics integrates with TrueData through a connection system that supports multiple authentication methods.

### Key Features

- **Token-based Authentication** - For Corporate & Fundamental APIs
- **Query Parameter Authentication** - For Symbol Master API
- **WebSocket Support** - For Corporate Announcements
- **Automatic Token Refresh** - Tokens expire daily at 4:00 AM IST
- **Secure Credential Storage** - All credentials are encrypted

### TrueData APIs Available

1. **Corporate API** - Corporate actions, market cap, company info
2. **Symbol Master API** - Get all symbols (NSE/BSE)
3. **Corporate Announcements** - Real-time announcements via WebSocket

---

## Setup & Configuration

### Prerequisites

- TrueData account with valid username and password
- Admin access to Rubik Analytics
- Connection properly configured in the system

### Creating a TrueData Connection

1. **Navigate to Connections**
   - Go to Admin → Connections → TrueData

2. **Click "Add Connection" or "Configure"**
   - If no connection exists, click "Add Connection"
   - If connection exists, click "Configure" to update credentials

3. **Fill in Connection Details**
   ```
   Name: TrueData Production (or any descriptive name)
   Connection Type: Market Data
   Provider: TrueData
   Environment: PROD (or SANDBOX)
   ```

4. **Enter Credentials**
   ```
   Username: Your TrueData username
   Password: Your TrueData password
   Auth URL: https://auth.truedata.in/token (default)
   WebSocket Port: 8086 (for Market Data) or 9092 (for Corporate Announcements)
   ```

5. **Save Connection**
   - Click "Save" to store the connection
   - Credentials are automatically encrypted

6. **Enable Connection**
   - Toggle the "Enabled" switch to activate the connection

7. **Generate Token**
   - Click "Generate Token" to create your first authentication token
   - Token will be automatically refreshed daily at 4:00 AM IST

### Default Configuration

The system uses these defaults (configurable via environment variables):

```env
TRUEDATA_DEFAULT_AUTH_URL=https://auth.truedata.in/token
TRUEDATA_DEFAULT_WEBSOCKET_PORT=8086
```

These can be overridden in the connection configuration dialog.

---

## Authentication Methods

TrueData uses **three different authentication methods** depending on the API endpoint:

### 1. Token Authentication (Bearer Token)

**Used for:** Corporate API, Fundamental API

**Method:** Bearer token in Authorization header

**Example:**
```http
GET https://corporate.truedata.in/getCorpAction
Authorization: Bearer <access_token>
```

**Token Generation:**
- Tokens are generated using username/password
- Tokens expire daily at **4:00 AM IST**
- Tokens are automatically refreshed when expired

### 2. Query Parameter Authentication

**Used for:** Symbol Master API

**Method:** Username and password as query parameters

**Example:**
```http
GET https://api.truedata.in/getAllSymbols?segment=eq&user=<username>&password=<password>
```

**Note:** This API does NOT use Bearer tokens - credentials are passed directly in the URL.

### 3. WebSocket Authentication

**Used for:** Corporate Announcements WebSocket

**Method:** Username and password in WebSocket URL query parameters

**Example:**
```
wss://corp.truedata.in:9092?user=<username>&password=<password>
```

**Important Ports:**
- **Port 9092** - Corporate Announcements WebSocket (ALWAYS use this for announcements)
- **Port 8086** - Market Data WebSocket (NOT for announcements)

---

## Token Management

### Token Lifecycle

1. **Generation**
   - Tokens are generated using username/password via `/token` endpoint
   - Response includes `access_token` and `expires_in` (seconds until 4:00 AM IST)

2. **Storage**
   - Tokens are stored in DuckDB: `data/connection/truedata/tokens.duckdb`
   - Encrypted credentials stored in SQLite: `data/auth/sqlite/auth.db`

3. **Expiry**
   - Tokens expire daily at **4:00 AM IST** (not a fixed duration)
   - `expires_in` from API is authoritative - represents seconds until next 4:00 AM IST
   - System automatically refreshes tokens after expiry

4. **Auto-Refresh**
   - Tokens are automatically refreshed at expiry time (4:00 AM IST)
   - Refresh happens **AFTER** expiry, not before
   - Scheduled refresh uses threading.Timer

### Token Status

Tokens can have the following statuses:

- **ACTIVE** - Token is valid and not expired
- **EXPIRED** - Token has passed expiry time (4:00 AM IST)
- **NOT_GENERATED** - No token exists for this connection
- **ERROR** - Token generation or storage failed

### Manual Token Operations

#### Generate Token

```http
POST /api/v1/admin/connections/{id}/token/generate
```

**Requirements:**
- Connection must be enabled
- Username and password must be configured
- Connection provider must be "TrueData"

**Response:**
```json
{
  "message": "Token generated successfully",
  "status": "ACTIVE",
  "expires_at": "2026-01-04T04:00:00+05:30"
}
```

#### Refresh Token

```http
POST /api/v1/admin/connections/{id}/token/refresh
```

**Note:** Refresh always generates a new token (force refresh).

#### Get Token Status

```http
GET /api/v1/admin/connections/{id}/token/status
```

**Response:**
```json
{
  "connection_id": 2,
  "token_status": "ACTIVE",
  "expires_at": "2026-01-04T04:00:00+05:30",
  "expires_at_ist": "2026-01-04T04:00:00+05:30",
  "last_refreshed_at": "2026-01-03T10:30:00+00:00",
  "seconds_left": 64800,
  "next_auto_refresh_at": "2026-01-04T04:00:00+05:30"
}
```

**Fields:**
- `token_status`: ACTIVE | EXPIRED | NOT_GENERATED | ERROR
- `expires_at`: ISO timestamp in IST (4:00 AM IST)
- `seconds_left`: Seconds until expiry (can be negative if expired)
- `next_auto_refresh_at`: Next scheduled refresh time (always 4:00 AM IST)

#### Get Token Value

```http
GET /api/v1/admin/connections/truedata/token?connection_id={id}
```

**Response:** Plain text token (for use by other services)

---

## API Endpoints

### Corporate API

**Base URL:** `https://corporate.truedata.in/`

**Authentication:** Bearer token

**Available Endpoints:**

1. **getCorpAction**
   ```http
   GET /getCorpAction?symbol=RELIANCE
   ```

2. **getCorpActionRange**
   ```http
   GET /getCorpActionRange?from=2026-01-01&to=2026-01-31&symbol=RELIANCE
   ```

3. **getSymbolClassification**
   ```http
   GET /getSymbolClassification?symbol=RELIANCE
   ```

4. **getCompanyLogo**
   ```http
   GET /getCompanyLogo?symbol=RELIANCE
   ```

5. **getMarketCap**
   ```http
   GET /getMarketCap?symbol=RELIANCE
   ```

6. **getCorporateInfo**
   ```http
   GET /getCorporateInfo?symbol=RELIANCE
   ```

**Usage in Code:**
```python
from app.services.truedata_api_service import get_truedata_api_service

api_service = get_truedata_api_service(connection_id=2, db_session=db)
result = api_service.call_corporate_api("getCorpAction", params={"symbol": "RELIANCE"})
```

### Symbol Master API

**Base URL:** `https://api.truedata.in/getAllSymbols`

**Authentication:** Query parameters (username/password)

**Parameters:**
- `segment`: "eq" (NSE) or "bseeq" (BSE)
- `user`: TrueData username
- `password`: TrueData password
- `response`: "json" or "csv" (optional)

**Example:**
```http
GET /getAllSymbols?segment=eq&user=<username>&password=<password>&response=json
```

**Usage in Code:**
```python
api_service = get_truedata_api_service(connection_id=2, db_session=db)
symbols = api_service.get_all_symbols(segment="eq", response_format="json")
# Or convenience methods:
nse_symbols = api_service.get_nse_symbols()
bse_symbols = api_service.get_bse_symbols()
```

**API Endpoint in Rubik:**
```http
GET /api/v1/admin/connections/{id}/truedata/symbols?segment=eq&format=json
```

### Corporate Announcements API

**Base URL:** `https://corporate.truedata.in/`

**Authentication:** Bearer token

**Available Endpoints:**
- Any endpoint under `/corporate/` can be called

**Usage:**
```http
GET /api/v1/admin/connections/{id}/truedata/corporate/{endpoint}?symbol=RELIANCE
```

**Example:**
```http
GET /api/v1/admin/connections/2/truedata/corporate/getCorpAction?symbol=RELIANCE
```

---

## WebSocket Connections

### Corporate Announcements WebSocket

**URL Format:**
```
wss://corp.truedata.in:9092?user=<username>&password=<password>
```

**Important:**
- **Port 9092** is for Corporate Announcements ONLY
- **Port 8086** is for Market Data WebSocket (different service)
- Always use port 9092 for corporate announcements

**Getting WebSocket URL:**
```python
api_service = get_truedata_api_service(connection_id=2, db_session=db)
ws_url = api_service.get_websocket_url()
# Returns: wss://corp.truedata.in:9092?user=xxx&password=yyy
```

**Connection Example:**
```python
import websockets
import asyncio

async def connect_announcements():
    api_service = get_truedata_api_service(connection_id=2)
    ws_url = api_service.get_websocket_url()
    
    async with websockets.connect(ws_url) as websocket:
        while True:
            message = await websocket.recv()
            # Process announcement
            print(f"Announcement: {message}")

asyncio.run(connect_announcements())
```

---

## Troubleshooting

### Common Issues

#### 1. "Invalid encryption key configuration"

**Symptoms:**
- Error when trying to view/update connection
- "Decryption failed" messages in logs

**Solution:**
1. Check that `ENCRYPTION_KEY` environment variable is set correctly
2. Key must be a valid Fernet key (32 bytes, base64url-encoded, 44 characters)
3. Generate new key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
4. Update in `docker-compose.dev.yml` or `.env` file
5. Recreate containers: `docker compose -f docker-compose.dev.yml up -d --force-recreate`

#### 2. "Token generation failed"

**Symptoms:**
- Cannot generate token
- HTTP 401 or 400 errors

**Solutions:**

1. **Check Credentials**
   - Verify username and password are correct
   - Ensure no extra spaces or special characters
   - Try logging into TrueData web portal to verify credentials

2. **Check Auth URL**
   - Default: `https://auth.truedata.in/token`
   - Verify URL is accessible
   - Check for network/firewall issues

3. **Check Connection Status**
   - Connection must be enabled
   - Connection status should be "CONNECTED" or "DISCONNECTED" (not "ERROR")

4. **Check Logs**
   ```bash
   docker compose -f docker-compose.dev.yml logs -f backend | grep -i truedata
   ```

#### 3. "Token expired" but refresh not working

**Symptoms:**
- Token shows as expired
- Auto-refresh not triggering

**Solutions:**

1. **Manual Refresh**
   - Click "Refresh Token" button in UI
   - Or call: `POST /api/v1/admin/connections/{id}/token/refresh`

2. **Check Scheduler**
   - Verify token refresh scheduler is running
   - Check logs for scheduler errors

3. **Check Timezone**
   - System uses IST (Indian Standard Time) for token expiry
   - Ensure server timezone is correct
   - Tokens expire at 4:00 AM IST daily

#### 4. "Connection credentials not found"

**Symptoms:**
- Cannot decrypt credentials
- "Credentials not configured" error

**Solutions:**

1. **Re-enter Credentials**
   - Go to Configure dialog
   - Enter username and password again
   - Save connection

2. **Check Encryption Key**
   - Ensure `ENCRYPTION_KEY` is valid
   - If key changed, old encrypted data cannot be decrypted
   - You'll need to re-enter credentials

#### 5. WebSocket Connection Fails

**Symptoms:**
- Cannot connect to Corporate Announcements WebSocket
- Connection timeout errors

**Solutions:**

1. **Check Port**
   - Use port **9092** for Corporate Announcements
   - Port 8086 is for Market Data (different service)

2. **Check Credentials**
   - Verify username/password in connection configuration
   - Credentials are passed in URL query parameters

3. **Check Network**
   - Ensure `corp.truedata.in:9092` is accessible
   - Check firewall rules
   - Verify SSL/TLS certificates

#### 6. "Symbol API returns empty/error"

**Symptoms:**
- Symbol Master API returns no data
- HTTP errors from Symbol API

**Solutions:**

1. **Check Authentication Method**
   - Symbol API uses query parameters, NOT Bearer token
   - Verify credentials are passed correctly

2. **Check Segment Parameter**
   - Use "eq" for NSE
   - Use "bseeq" for BSE
   - Case-sensitive

3. **Check Response Format**
   - Default is JSON
   - Can request CSV with `response=csv` parameter

### Debugging

#### Enable Debug Logging

Check backend logs for detailed information:

```bash
# Docker
docker compose -f docker-compose.dev.yml logs -f backend | grep -i truedata

# Local
# Logs are in: data/logs/app/
```

#### Test Connection Manually

```python
# Test token generation
import requests

response = requests.post(
    "https://auth.truedata.in/token",
    data={
        "username": "your_username",
        "password": "your_password",
        "grant_type": "password"
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)
print(response.json())
```

#### Check Token Status via API

```bash
curl -X GET "http://localhost:8000/api/v1/admin/connections/2/token/status" \
  -H "Authorization: Bearer <your_jwt_token>"
```

### Getting Help

If issues persist:

1. **Check Logs**
   - Backend logs: `data/logs/app/`
   - Docker logs: `docker compose logs backend`

2. **Verify Configuration**
   - Connection is enabled
   - Credentials are correct
   - Encryption key is valid

3. **Test API Directly**
   - Use curl/Postman to test TrueData APIs directly
   - Verify credentials work outside Rubik Analytics

4. **Contact Support**
   - TrueData support: Check TrueData documentation
   - Rubik Analytics: Check project issues/forum

---

## Best Practices

### Security

1. **Never commit credentials**
   - Credentials are encrypted in database
   - Use environment variables for sensitive config
   - Rotate encryption keys periodically

2. **Use strong encryption keys**
   - Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - Store in environment variables, not code

3. **Monitor token expiry**
   - Check token status regularly
   - Set up alerts for token expiry

### Performance

1. **Cache token status**
   - Token status doesn't change frequently
   - Cache for 30-60 seconds in frontend

2. **Batch API calls**
   - Group multiple API calls when possible
   - Use connection pooling

3. **Handle rate limits**
   - TrueData may have rate limits
   - Implement retry logic with exponential backoff

### Maintenance

1. **Regular token refresh**
   - Tokens auto-refresh at 4:00 AM IST
   - Monitor refresh success in logs

2. **Update credentials**
   - Update if password changes
   - Test connection after updates

3. **Monitor connection health**
   - Check connection status regularly
   - Set up health checks/alerts

---

## API Reference Summary

### Connection Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/connections` | GET | List all connections |
| `/api/v1/admin/connections` | POST | Create new connection |
| `/api/v1/admin/connections/{id}` | GET | Get connection details |
| `/api/v1/admin/connections/{id}` | PUT | Update connection |
| `/api/v1/admin/connections/{id}` | DELETE | Delete connection |
| `/api/v1/admin/connections/{id}/test` | POST | Test connection |

### Token Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/connections/{id}/token/generate` | POST | Generate new token |
| `/api/v1/admin/connections/{id}/token/refresh` | POST | Refresh token |
| `/api/v1/admin/connections/{id}/token/status` | GET | Get token status |
| `/api/v1/admin/connections/truedata/token` | GET | Get token value |

### TrueData API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/connections/{id}/truedata/symbols` | GET | Get all symbols |
| `/api/v1/admin/connections/{id}/truedata/corporate/{endpoint}` | GET | Call Corporate API |

---

## Additional Resources

- **TrueData Documentation**: Check TrueData official documentation
- **Rubik Analytics Architecture**: See `docs/ARCHITECTURE.md`
- **Troubleshooting Guide**: See `docs/TROUBLESHOOTING.md`
- **Project Structure**: See `docs/PROJECT-STRUCTURE.md`

---

**Last Updated:** 2026-01-03  
**Version:** 1.0

