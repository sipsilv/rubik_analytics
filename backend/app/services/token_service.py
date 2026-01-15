"""
Token Service for TrueData Token Management
Handles token generation, storage, and refresh for TrueData connections

CRITICAL: TrueData tokens expire daily at ~4:00 AM IST
- expires_in from API is authoritative (seconds until 4 AM IST)
- Never assume fixed duration
- Always refresh 10-15 minutes before expiry
"""
import os
import logging
import duckdb
import requests
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global timer for scheduled token refresh
_token_refresh_timer: Optional[threading.Timer] = None
_token_refresh_lock = threading.Lock()

# Token expiry is at 4:00 AM IST daily
# Refresh happens AFTER expiry, not before

class TokenService:
    """Service for managing TrueData tokens with day-bound expiry"""
    
    def __init__(self):
        # settings.DATA_DIR is already normalized in config.py
        self.data_dir = settings.DATA_DIR
        self.tokens_db_path = os.path.join(self.data_dir, "connection", "truedata", "tokens.duckdb")
        self._init_database()
    
    def _init_database(self):
        """Initialize the tokens database schema - STANDARDIZED SCHEMA (FINAL)"""
        os.makedirs(os.path.dirname(self.tokens_db_path), exist_ok=True)
        
        conn = duckdb.connect(self.tokens_db_path, config={'allow_unsigned_extensions': True})
        try:
            # Check if table exists and get current columns
            table_exists = False
            current_columns = []
            try:
                result = conn.execute("PRAGMA table_info(tokens)").fetchall()
                if result:
                    table_exists = True
                    current_columns = [col[1] for col in result]
                    logger.info(f"Existing tokens table columns: {current_columns}")
            except Exception:
                table_exists = False
            
            # Define the FINAL standardized schema (ONLY these columns)
            required_columns = {
                'id': 'INTEGER PRIMARY KEY',
                'connection_id': 'INTEGER NOT NULL UNIQUE',
                'access_token': 'TEXT NOT NULL',
                'expires_at': 'TIMESTAMP NOT NULL',
                'last_refreshed_at': 'TIMESTAMP NOT NULL',
                'status': 'TEXT NOT NULL DEFAULT \'ACTIVE\''
            }
            
            # Migration: Remove any columns that shouldn't exist
            if table_exists:
                invalid_columns = ['provider', 'last_generated_at', 'refresh_before_minutes']
                columns_to_drop = [col for col in invalid_columns if col in current_columns]
                
                if columns_to_drop or any(col not in required_columns for col in current_columns if col not in ['id', 'connection_id', 'access_token', 'expires_at', 'last_refreshed_at', 'status']):
                    logger.info(f"Migrating tokens table - removing invalid columns: {columns_to_drop}")
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS tokens_new (
                            id INTEGER PRIMARY KEY,
                            connection_id INTEGER NOT NULL UNIQUE,
                            access_token TEXT NOT NULL,
                            expires_at TIMESTAMP NOT NULL,
                            last_refreshed_at TIMESTAMP NOT NULL,
                            status TEXT NOT NULL DEFAULT 'ACTIVE'
                        )
                    """)
                    
                    try:
                        conn.execute("""
                            INSERT INTO tokens_new (id, connection_id, access_token, expires_at, last_refreshed_at, status)
                            SELECT id, connection_id, access_token, expires_at, 
                                   COALESCE(last_refreshed_at, expires_at) as last_refreshed_at,
                                   COALESCE(status, 'ACTIVE') as status
                            FROM tokens
                        """)
                        logger.info("Migrated existing token data to new schema")
                    except Exception as e:
                        logger.warning(f"Could not migrate existing data: {e}")
                    
                    conn.execute("DROP TABLE IF EXISTS tokens")
                    conn.execute("ALTER TABLE tokens_new RENAME TO tokens")
                    logger.info("Tokens table migrated to standardized schema")
            else:
                conn.execute("""
                    CREATE TABLE tokens (
                        id INTEGER PRIMARY KEY,
                        connection_id INTEGER NOT NULL UNIQUE,
                        access_token TEXT NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        last_refreshed_at TIMESTAMP NOT NULL,
                        status TEXT NOT NULL DEFAULT 'ACTIVE'
                    )
                """)
                logger.info("Created tokens table with standardized schema")
            
            conn.commit()
        except Exception as e:
            logger.error(f"Error initializing tokens database: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    
    def generate_token(
        self,
        connection_id: int,
        username: str,
        password: str,
        auth_url: str = "https://auth.truedata.in/token"
    ) -> Dict[str, Any]:
        """
        Generate a new TrueData token for a connection
        
        CRITICAL: expires_in from API is authoritative - it represents seconds until ~4:00 AM IST
        """
        logger.info(f"TokenService.generate_token called for connection_id={connection_id}")
        logger.info(f"  - Auth URL: {auth_url}")
        logger.info(f"  - Username: {username[:3]}*** (length: {len(username)})")
        
        try:
            # Make token request (application/x-www-form-urlencoded)
            logger.info(f"Making POST request to {auth_url}")
            request_data = {
                "username": username,
                "password": password,
                "grant_type": "password"  # Fixed value
            }
            
            response = requests.post(
                auth_url,
                data=request_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=30
            )
            
            logger.info(f"Response status code: {response.status_code}")
            response.raise_for_status()
            
            token_data = response.json()
            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in")
            
            if not access_token:
                logger.error("No access_token in response")
                raise ValueError("No access_token in response")
            
            if expires_in is None:
                logger.warning("No expires_in in response, defaulting to 3600 seconds")
                expires_in = 3600
            
            # CRITICAL: expires_in is authoritative - it's seconds until ~4:00 AM IST
            # Calculate absolute expiry timestamp using IST time (not UTC)
            # Force-clamp to next 4:00 AM IST to avoid drift beyond daily cutoff
            try:
                from zoneinfo import ZoneInfo
                ist_tz = ZoneInfo("Asia/Kolkata")
                now_ist = datetime.now(ist_tz)
                expires_at_ist = now_ist + timedelta(seconds=expires_in)
                
                # Clamp to next 4:00 AM IST (day-bound tokens)
                next_four_am_ist = now_ist.replace(hour=4, minute=0, second=0, microsecond=0)
                if next_four_am_ist <= now_ist:
                    next_four_am_ist += timedelta(days=1)
                if expires_at_ist > next_four_am_ist:
                    logger.info(f"Clamping expiry to next 4:00 AM IST. Calculated: {expires_at_ist.isoformat()}, Target: {next_four_am_ist.isoformat()}")
                    expires_at_ist = next_four_am_ist
                
                # Convert to UTC for storage (database stores UTC)
                expires_at = expires_at_ist.astimezone(timezone.utc)
                last_refreshed_at = datetime.now(timezone.utc)
                
                logger.info(f"Token calculation - Current IST: {now_ist.isoformat()}")
                logger.info(f"Token calculation - Expires IST: {expires_at_ist.isoformat()}")
                logger.info(f"Token calculation - Expires UTC (stored): {expires_at.isoformat()}")
            except ImportError:
                # Fallback for Python < 3.9: manually calculate IST offset
                ist_offset = timedelta(hours=5, minutes=30)
                now_utc = datetime.now(timezone.utc)
                now_ist_approx = now_utc + ist_offset
                expires_at_ist_approx = now_ist_approx + timedelta(seconds=expires_in)
                
                # Clamp to next 4:00 AM IST (approx)
                next_four_am_ist_approx = now_ist_approx.replace(hour=4, minute=0, second=0, microsecond=0)
                if next_four_am_ist_approx <= now_ist_approx:
                    next_four_am_ist_approx += timedelta(days=1)
                if expires_at_ist_approx > next_four_am_ist_approx:
                    logger.info(f"Clamping expiry (fallback) to next 4:00 AM IST. Calculated: {expires_at_ist_approx.isoformat()}, Target: {next_four_am_ist_approx.isoformat()}")
                    expires_at_ist_approx = next_four_am_ist_approx
                
                # Convert back to UTC for storage
                expires_at = expires_at_ist_approx - ist_offset
                last_refreshed_at = now_utc
                
                logger.info(f"Token calculation (fallback) - Current IST (approx): {now_ist_approx.isoformat()}")
                logger.info(f"Token calculation (fallback) - Expires IST (approx): {expires_at_ist_approx.isoformat()}")
                logger.info(f"Token calculation (fallback) - Expires UTC (stored): {expires_at.isoformat()}")
        
            logger.info(f"Token received - expires_in: {expires_in} seconds")
            # Verify the calculated expiry hour is around 4:00 AM IST
            try:
                from zoneinfo import ZoneInfo
                ist_tz = ZoneInfo("Asia/Kolkata")
                expires_at_ist_verify = expires_at.astimezone(ist_tz)
                logger.info(f"Token expires at: {expires_at.isoformat()} UTC")
                logger.info(f"Token expires at: {expires_at_ist_verify.isoformat()} IST")
                logger.info(f"IST hour verification: {expires_at_ist_verify.hour}:{expires_at_ist_verify.minute:02d} (should be ~04:00)")
                if expires_at_ist_verify.hour != 4:
                    logger.warning(f"WARNING: Token expiry hour is {expires_at_ist_verify.hour}:{expires_at_ist_verify.minute:02d} IST, expected ~04:00 IST. expires_in={expires_in}s")
            except Exception as e:
                logger.warning(f"Could not verify IST hour: {e}")
                expires_at_ist_verify = None
            
            # Store token with standardized schema
            conn = duckdb.connect(self.tokens_db_path, config={'allow_unsigned_extensions': True})
            try:
                existing = conn.execute("""
                    SELECT id FROM tokens WHERE connection_id = ?
                """, [connection_id]).fetchone()
                
                if existing:
                    conn.execute("""
                        UPDATE tokens SET
                            access_token = ?,
                            expires_at = ?,
                            last_refreshed_at = ?,
                            status = ?
                        WHERE connection_id = ?
                    """, [
                        access_token,
                        expires_at,
                        last_refreshed_at,
                        "ACTIVE",
                        connection_id
                    ])
                    logger.debug(f"Updated existing token for connection {connection_id}")
                else:
                    max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) FROM tokens").fetchone()
                    next_id = (max_id_result[0] if max_id_result else 0) + 1
                    
                    conn.execute("""
                        INSERT INTO tokens (id, connection_id, access_token, expires_at, last_refreshed_at, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, [
                        next_id,
                        connection_id,
                        access_token,
                        expires_at,
                        last_refreshed_at,
                        "ACTIVE"
                    ])
                    logger.debug(f"Inserted new token with id={next_id} for connection {connection_id}")
                conn.commit()
                logger.info(f"Token stored successfully for connection {connection_id}")
            except Exception as e:
                logger.error(f"Error storing token in database: {e}", exc_info=True)
                raise
            finally:
                conn.close()
            
            # Schedule automatic refresh AT expiry time (4:00 AM IST)
            # Refresh happens AFTER expiry, not before
            self._schedule_token_refresh(expires_at, connection_id, username, password, auth_url)
            
            return {
                "access_token": access_token,
                "expires_at": expires_at.isoformat(),
                "expires_in": expires_in,
                "last_refreshed_at": last_refreshed_at.isoformat()
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating TrueData token: {e}")
            self._set_token_status(connection_id, "ERROR")
            raise Exception(f"Failed to generate token: {str(e)}")
        except Exception as e:
            logger.error(f"Error in token generation: {e}")
            self._set_token_status(connection_id, "ERROR")
            raise
    
    def get_token(self, connection_id: int, auto_refresh: bool = True) -> Optional[str]:
        """
        Get active token for connection
        
        If auto_refresh=True and token is expired/expiring, attempts to refresh automatically
        """
        conn = duckdb.connect(self.tokens_db_path, config={'allow_unsigned_extensions': True})
        try:
            result = conn.execute("""
                SELECT access_token, expires_at, status
                FROM tokens
                WHERE connection_id = ? AND status = 'ACTIVE'
                ORDER BY last_refreshed_at DESC
                LIMIT 1
            """, [connection_id]).fetchone()
            
            if not result:
                return None
            
            access_token, expires_at, status = result
            
            # Parse and check expiry
            if expires_at:
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                elif expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                
                # CRITICAL: Calculate seconds_left using IST time (not UTC)
                try:
                    from zoneinfo import ZoneInfo
                    ist_tz = ZoneInfo("Asia/Kolkata")
                    now_ist = datetime.now(ist_tz)
                    expires_at_ist = expires_at.astimezone(ist_tz)
                    seconds_left = (expires_at_ist - now_ist).total_seconds()
                except ImportError:
                    # Fallback for Python < 3.9
                    now_utc = datetime.now(timezone.utc)
                    seconds_left = (expires_at - now_utc).total_seconds()
                
                # Check if token is expired
                if seconds_left <= 0:
                    # Token expired - mark as expired
                    conn.execute("""
                        UPDATE tokens SET status = 'EXPIRED' WHERE connection_id = ?
                    """, [connection_id])
                    conn.commit()
                    
                    # Auto-refresh if enabled (refresh AFTER expiry)
                    if auto_refresh:
                        logger.info(f"Token expired for connection {connection_id}, attempting auto-refresh")
                        self._auto_refresh_token(connection_id)
                        # Try to get refreshed token
                        return self.get_token(connection_id, auto_refresh=False)
                    
                    return None
            
            return access_token
        finally:
            conn.close()
    
    def get_token_status(self, connection_id: int) -> Dict[str, Any]:
        """
        Get token status for a connection - STANDARDIZED QUERY
        
        Returns:
            - token_status: ACTIVE | EXPIRED | NOT_GENERATED | ERROR
            - expires_at: ISO timestamp (4:00 AM IST)
            - last_refreshed_at: ISO timestamp
            - seconds_left: seconds until expiry at 4:00 AM IST (can be negative if expired)
        """
        conn = duckdb.connect(self.tokens_db_path, config={'allow_unsigned_extensions': True})
        try:
            result = conn.execute("""
                SELECT
                    access_token,
                    expires_at,
                    last_refreshed_at,
                    status
                FROM tokens
                WHERE connection_id = ?
                ORDER BY last_refreshed_at DESC
                LIMIT 1
            """, [connection_id]).fetchone()
            
            if not result:
                # Calculate next 4:00 AM IST for NOT_GENERATED status
                try:
                    from zoneinfo import ZoneInfo
                    ist_tz = ZoneInfo("Asia/Kolkata")
                    now_ist = datetime.now(ist_tz)
                    next_refresh_ist = now_ist.replace(hour=4, minute=0, second=0, microsecond=0)
                    if next_refresh_ist <= now_ist:
                        next_refresh_ist += timedelta(days=1)
                    next_auto_refresh_at = self._ist_to_iso(next_refresh_ist)
                except ImportError:
                    ist_offset = timedelta(hours=5, minutes=30)
                    now_utc = datetime.now(timezone.utc)
                    now_ist_approx = now_utc + ist_offset
                    next_refresh_ist_approx = now_ist_approx.replace(hour=4, minute=0, second=0, microsecond=0)
                    if next_refresh_ist_approx <= now_ist_approx:
                        next_refresh_ist_approx += timedelta(days=1)
                    next_auto_refresh_at = next_refresh_ist_approx.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                
                return {
                    "connection_id": connection_id,
                    "token_status": "NOT_GENERATED",
                    "expires_at": None,
                    "last_refreshed_at": None,
                    "seconds_left": 0,
                    "expires_at_ist": None,
                    "next_auto_refresh_at": next_auto_refresh_at
                }
            
            access_token, expires_at, last_refreshed_at, status = result
            
            if expires_at is None:
                # Calculate next 4:00 AM IST for ERROR status
                try:
                    from zoneinfo import ZoneInfo
                    ist_tz = ZoneInfo("Asia/Kolkata")
                    now_ist = datetime.now(ist_tz)
                    next_refresh_ist = now_ist.replace(hour=4, minute=0, second=0, microsecond=0)
                    if next_refresh_ist <= now_ist:
                        next_refresh_ist += timedelta(days=1)
                    next_auto_refresh_at = self._ist_to_iso(next_refresh_ist)
                except ImportError:
                    ist_offset = timedelta(hours=5, minutes=30)
                    now_utc = datetime.now(timezone.utc)
                    now_ist_approx = now_utc + ist_offset
                    next_refresh_ist_approx = now_ist_approx.replace(hour=4, minute=0, second=0, microsecond=0)
                    if next_refresh_ist_approx <= now_ist_approx:
                        next_refresh_ist_approx += timedelta(days=1)
                    next_auto_refresh_at = next_refresh_ist_approx.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                
                return {
                    "connection_id": connection_id,
                    "token_status": "ERROR",
                    "expires_at": None,
                    "last_refreshed_at": last_refreshed_at.isoformat() if last_refreshed_at else None,
                    "seconds_left": 0,
                    "expires_at_ist": None,
                    "next_auto_refresh_at": next_auto_refresh_at
                }
            
            # Parse timestamps
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            elif expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            # CRITICAL: Calculate seconds_left using IST time (not UTC)
            # This ensures accurate countdown for TrueData's day-bound tokens
            expires_at_ist_dt = None  # ensure defined for later use
            try:
                from zoneinfo import ZoneInfo
                ist_tz = ZoneInfo("Asia/Kolkata")
                now_ist = datetime.now(ist_tz)
                expires_at_ist_dt = expires_at.astimezone(ist_tz)

                # Clamp expiry to next 4:00 AM IST if it's beyond the daily cutoff
                next_four_am_ist = now_ist.replace(hour=4, minute=0, second=0, microsecond=0)
                if next_four_am_ist <= now_ist:
                    next_four_am_ist += timedelta(days=1)
                if expires_at_ist_dt > next_four_am_ist:
                    logger.info(
                        f"[TOKEN STATUS] Clamping stored expiry to next 4:00 AM IST. "
                        f"Stored: {expires_at_ist_dt.isoformat()}, Target: {next_four_am_ist.isoformat()}"
                    )
                    expires_at_ist_dt = next_four_am_ist
                    expires_at = expires_at_ist_dt.astimezone(timezone.utc)
                    # Persist the corrected expiry to avoid repeat drift
                    conn.execute(
                        """
                        UPDATE tokens
                        SET expires_at = ?
                        WHERE connection_id = ?
                        """,
                        [expires_at, connection_id],
                    )
                    conn.commit()

                # Calculate seconds_left in IST timezone
                seconds_left = int((expires_at_ist_dt - now_ist).total_seconds())
            except ImportError:
                # Fallback for Python < 3.9: use UTC but log warning
                now_utc = datetime.now(timezone.utc)
                seconds_left = int((expires_at - now_utc).total_seconds())
                logger.warning("Using UTC for seconds_left calculation (Python < 3.9). Consider upgrading for accurate IST calculations.")
            
            # Derive token_status based on seconds_left and stored status
            # Status determination is authoritative - backend owns this logic
            # Only ACTIVE or EXPIRED - refresh happens AFTER expiry, not before
            if status == "ERROR":
                token_status = "ERROR"
            elif seconds_left <= 0:
                token_status = "EXPIRED"
            else:
                token_status = "ACTIVE"
            
            # Convert to IST for display (authoritative format)
            expires_at_ist_str = self._utc_to_ist(expires_at)
            
            # Calculate next auto refresh time (always at 4:00 AM IST)
            # If token is expired, calculate next 4:00 AM IST from now
            # If token is active, use the current expires_at (which is already 4:00 AM IST)
            try:
                from zoneinfo import ZoneInfo
                ist_tz = ZoneInfo("Asia/Kolkata")
                now_ist = datetime.now(ist_tz)
                
                # Next auto refresh is always the next 4:00 AM IST (day-bound)
                next_refresh_ist = now_ist.replace(hour=4, minute=0, second=0, microsecond=0)
                if next_refresh_ist <= now_ist:
                    next_refresh_ist += timedelta(days=1)
                
                next_auto_refresh_at = self._ist_to_iso(next_refresh_ist)
            except ImportError:
                # Fallback for Python < 3.9
                ist_offset = timedelta(hours=5, minutes=30)
                now_utc = datetime.now(timezone.utc)
                now_ist_approx = now_utc + ist_offset
                
                if seconds_left <= 0:
                    # Token expired, calculate next 4:00 AM IST
                    next_refresh_ist_approx = now_ist_approx.replace(hour=4, minute=0, second=0, microsecond=0)
                    if next_refresh_ist_approx <= now_ist_approx:
                        next_refresh_ist_approx += timedelta(days=1)
                    next_refresh_utc = next_refresh_ist_approx - ist_offset
                else:
                    # Use expires_at (already UTC)
                    next_refresh_utc = expires_at
                
                next_auto_refresh_at = self._utc_to_ist(next_refresh_utc)
            
            # Return authoritative response - expires_at in IST format
            # seconds_left can be negative (indicates expired) - frontend handles display
            return {
                "connection_id": connection_id,
                "token_status": token_status,  # ACTIVE | EXPIRED | NOT_GENERATED | ERROR
                "expires_at": expires_at_ist_str,  # IST format (ISO 8601 with +05:30)
                "expires_at_utc": expires_at.isoformat(),  # UTC for reference
                "expires_at_ist": expires_at_ist_str,  # IST (same as expires_at)
                "last_refreshed_at": last_refreshed_at.isoformat() if last_refreshed_at else None,
                "seconds_left": seconds_left,  # Can be negative if expired - frontend uses this ONLY
                "next_auto_refresh_at": next_auto_refresh_at  # Next 4:00 AM IST when token will auto-refresh
            }
        except Exception as e:
            error_msg = str(e)
            if "column" in error_msg.lower() or "binder" in error_msg.lower():
                logger.error(f"SQL schema error getting token status for connection {connection_id}: {e}", exc_info=True)
                raise Exception(f"Database schema error: {error_msg}. This indicates a schema mismatch.")
            logger.error(f"Error getting token status for connection {connection_id}: {e}", exc_info=True)
            # Calculate next 4:00 AM IST for error case
            try:
                from zoneinfo import ZoneInfo
                ist_tz = ZoneInfo("Asia/Kolkata")
                now_ist = datetime.now(ist_tz)
                next_refresh_ist = now_ist.replace(hour=4, minute=0, second=0, microsecond=0)
                if next_refresh_ist <= now_ist:
                    next_refresh_ist += timedelta(days=1)
                next_auto_refresh_at = next_refresh_ist.isoformat()
            except ImportError:
                ist_offset = timedelta(hours=5, minutes=30)
                now_utc = datetime.now(timezone.utc)
                now_ist_approx = now_utc + ist_offset
                next_refresh_ist_approx = now_ist_approx.replace(hour=4, minute=0, second=0, microsecond=0)
                if next_refresh_ist_approx <= now_ist_approx:
                    next_refresh_ist_approx += timedelta(days=1)
                next_auto_refresh_at = next_refresh_ist_approx.strftime("%Y-%m-%dT%H:%M:%S+05:30")
            except Exception:
                next_auto_refresh_at = None
            
            return {
                "connection_id": connection_id,
                "token_status": "ERROR",
                "expires_at": None,
                "expires_at_ist": None,
                "last_refreshed_at": None,
                "seconds_left": 0,
                "error": str(e),
                "next_auto_refresh_at": next_auto_refresh_at
            }
        finally:
            conn.close()
    
    def refresh_token_if_needed(
        self,
        connection_id: int,
        username: str,
        password: str,
        auth_url: str = "https://auth.truedata.in/token"
    ) -> bool:
        """
        Refresh token if it's expired or within refresh buffer
        
        This is called by the periodic scheduler
        """
        token_status = self.get_token_status(connection_id)
        
        if token_status["token_status"] == "NOT_GENERATED":
            # No token exists, generate one
            try:
                self.generate_token(connection_id, username, password, auth_url)
                return True
            except Exception as e:
                logger.error(f"Error generating new token: {e}")
                return False
        
        # Refresh if expired (refresh happens AFTER expiry, not before)
        if token_status["token_status"] == "EXPIRED":
            # Check if we recently refreshed (within last 2 minutes) to prevent repeated refreshes
            conn = duckdb.connect(self.tokens_db_path, config={'allow_unsigned_extensions': True})
            try:
                result = conn.execute("""
                    SELECT last_refreshed_at FROM tokens WHERE connection_id = ?
                    ORDER BY last_refreshed_at DESC LIMIT 1
                """, [connection_id]).fetchone()
                
                if result and result[0]:
                    last_refreshed = result[0]
                    if isinstance(last_refreshed, str):
                        last_refreshed = datetime.fromisoformat(last_refreshed.replace('Z', '+00:00'))
                    elif last_refreshed.tzinfo is None:
                        last_refreshed = last_refreshed.replace(tzinfo=timezone.utc)
                    
                    time_since_refresh = (datetime.now(timezone.utc) - last_refreshed).total_seconds()
                    if time_since_refresh < 120:  # 2 minutes cooldown
                        logger.debug(f"Token refresh skipped - last refreshed {int(time_since_refresh)} seconds ago")
                        return False
            except Exception as e:
                logger.warning(f"Error checking last_refreshed_at: {e}")
            finally:
                conn.close()
            
            # Refresh token
            try:
                self.generate_token(connection_id, username, password, auth_url)
                logger.info("Token refreshed successfully")
                return True
            except Exception as e:
                logger.error(f"Error refreshing token: {e}")
                return False
        
        # Token is still active, no refresh needed
        return False
    
    def _auto_refresh_token(self, connection_id: int):
        """Auto-refresh token using stored credentials"""
        try:
            from app.core.database import get_db
            from app.models.connection import Connection
            from app.core.security import decrypt_data
            import json
            
            db_gen = get_db()
            db = next(db_gen)
            try:
                truedata_conn = db.query(Connection).filter(
                    Connection.id == connection_id,
                    Connection.is_enabled == True
                ).first()
                
                if not truedata_conn or not truedata_conn.credentials:
                    logger.warning(f"Cannot auto-refresh token for connection {connection_id}: connection not enabled or no credentials")
                    return
                
                config = {}
                try:
                    decrypted_json = decrypt_data(truedata_conn.credentials)
                    config = json.loads(decrypted_json)
                except Exception as e:
                    logger.warning(f"Failed to decrypt TrueData credentials: {e}")
                    return
                
                username = config.get("username")
                password = config.get("password")
                auth_url = config.get("auth_url", "https://auth.truedata.in/token")
                
                if username and password:
                    self.generate_token(connection_id, username, password, auth_url)
                    logger.info(f"Auto-refreshed token for connection {connection_id}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error in auto-refresh: {e}", exc_info=True)
    
    def delete_token(self, connection_id: int) -> bool:
        """Delete token for connection"""
        conn = duckdb.connect(self.tokens_db_path, config={'allow_unsigned_extensions': True})
        try:
            conn.execute("DELETE FROM tokens WHERE connection_id = ?", [connection_id])
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting token: {e}")
            return False
        finally:
            conn.close()
    
    def _set_token_status(self, connection_id: int, status: str) -> bool:
        """Set token status (ACTIVE, EXPIRING, EXPIRED, ERROR)"""
        conn = duckdb.connect(self.tokens_db_path, config={'allow_unsigned_extensions': True})
        try:
            conn.execute("""
                UPDATE tokens SET status = ?
                WHERE connection_id = ?
            """, [status, connection_id])
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting token status: {e}", exc_info=True)
            return False
        finally:
            conn.close()
    
    def _schedule_token_refresh(
        self,
        refresh_time: datetime,
        connection_id: int,
        username: str,
        password: str,
        auth_url: str
    ):
        """
        Schedule a token refresh at refresh_time (expires_at = 4:00 AM IST)
        
        CRITICAL: refresh_time is the exact expiry time (4:00 AM IST)
        Refresh happens AFTER expiry, not before
        """
        global _token_refresh_timer, _token_refresh_lock
        
        with _token_refresh_lock:
            # Cancel existing timer if any
            if _token_refresh_timer:
                _token_refresh_timer.cancel()
            
            # Parse refresh_time if needed
            if isinstance(refresh_time, str):
                refresh_time = datetime.fromisoformat(refresh_time.replace('Z', '+00:00'))
            elif refresh_time.tzinfo is None:
                refresh_time = refresh_time.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            time_until_refresh = (refresh_time - now).total_seconds()
            
            if time_until_refresh <= 0:
                # Refresh time already passed, refresh immediately
                logger.info("Refresh time already passed, refreshing immediately")
                self._refresh_token_at_scheduled_time(connection_id, username, password, auth_url)
                return
            
            # Schedule refresh
            logger.info(f"Scheduling token refresh in {time_until_refresh:.0f} seconds (at {refresh_time.isoformat()} UTC / {self._utc_to_ist(refresh_time)} IST)")
            _token_refresh_timer = threading.Timer(
                time_until_refresh,
                self._refresh_token_at_scheduled_time,
                args=(connection_id, username, password, auth_url)
            )
            _token_refresh_timer.daemon = True
            _token_refresh_timer.start()
    
    def _refresh_token_at_scheduled_time(
        self,
        connection_id: int,
        username: str,
        password: str,
        auth_url: str
    ):
        """Refresh token at scheduled time (called by timer)"""
        logger.info(f"Token refresh triggered for connection {connection_id}")
        
        try:
            # Check if connection is still enabled
            from app.core.database import get_db
            from app.models.connection import Connection
            
            db_gen = get_db()
            db = next(db_gen)
            try:
                truedata_conn = db.query(Connection).filter(
                    Connection.id == connection_id,
                    Connection.is_enabled == True
                ).first()
                
                if not truedata_conn:
                    logger.info("TrueData connection not enabled, skipping auto-refresh")
                    return
                
                # Generate new token (this will schedule the next refresh)
                token_result = self.generate_token(connection_id, username, password, auth_url)
                logger.info(f"Token refreshed automatically. New token expires at {token_result['expires_at']} UTC / {self._utc_to_ist(datetime.fromisoformat(token_result['expires_at']))} IST")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in scheduled token refresh: {e}", exc_info=True)
    
    def _utc_to_ist(self, utc_time: datetime) -> str:
        """
        Convert UTC datetime to IST (Indian Standard Time) ISO 8601 format
        
        Returns: ISO 8601 string with IST timezone (e.g., "2026-01-03T04:00:00+05:30")
        """
        try:
            from zoneinfo import ZoneInfo
            ist = utc_time.astimezone(ZoneInfo("Asia/Kolkata"))
            # Return ISO 8601 format with IST timezone
            return ist.isoformat()
        except ImportError:
            # Fallback for Python < 3.9
            ist_offset = timedelta(hours=5, minutes=30)
            ist = utc_time + ist_offset
            # Return ISO-like format with IST offset
            return ist.strftime("%Y-%m-%dT%H:%M:%S+05:30")
        except Exception as e:
            logger.warning(f"Error converting to IST: {e}")
            return utc_time.isoformat()
    
    def _ist_to_iso(self, ist_time: datetime) -> str:
        """
        Convert IST datetime to ISO 8601 format string
        
        Returns: ISO 8601 string with IST timezone (e.g., "2026-01-03T04:00:00+05:30")
        """
        return ist_time.isoformat()
    
    def check_and_refresh_all_tokens(self):
        """
        Check all tokens and refresh those that are expired
        
        This is called by the periodic scheduler - it only checks timestamps,
        doesn't hit TrueData API unless refresh is needed
        Refresh happens AFTER expiry, not before
        """
        conn = duckdb.connect(self.tokens_db_path, config={'allow_unsigned_extensions': True})
        try:
            # Get all active tokens
            results = conn.execute("""
                SELECT connection_id, expires_at, status
                FROM tokens
                WHERE status = 'ACTIVE'
            """).fetchall()
            
            for connection_id, expires_at, status in results:
                try:
                    # Parse expiry
                    if isinstance(expires_at, str):
                        expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    elif expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    
                    # CRITICAL: Calculate seconds_left using IST time (not UTC)
                    try:
                        from zoneinfo import ZoneInfo
                        ist_tz = ZoneInfo("Asia/Kolkata")
                        now_ist = datetime.now(ist_tz)
                        expires_at_ist = expires_at.astimezone(ist_tz)
                        seconds_left = (expires_at_ist - now_ist).total_seconds()
                    except ImportError:
                        # Fallback for Python < 3.9
                        now_utc = datetime.now(timezone.utc)
                        seconds_left = (expires_at - now_utc).total_seconds()
                    
                    # Check if expired (refresh happens AFTER expiry)
                    if seconds_left <= 0:
                        logger.info(f"Token for connection {connection_id} expired ({int(seconds_left)}s), refreshing")
                        # Trigger auto-refresh (will get credentials from DB)
                        self._auto_refresh_token(connection_id)
                except Exception as e:
                    logger.error(f"Error checking token for connection {connection_id}: {e}")
        finally:
            conn.close()

# Global token service instance
_token_service: Optional[TokenService] = None

def get_token_service() -> TokenService:
    """Get the global token service instance"""
    global _token_service
    if _token_service is None:
        _token_service = TokenService()
    return _token_service

def get_truedata_token_for_connection(connection_id: int) -> Optional[str]:
    """
    Get TrueData token for use by other connections.
    Auto-refreshes if expired/expiring.
    """
    try:
        token_service = get_token_service()
        token = token_service.get_token(connection_id, auto_refresh=True)
        return token
    except Exception as e:
        logger.error(f"Error getting TrueData token for connection {connection_id}: {e}")
        return None

def get_truedata_auth_headers(connection_id: int) -> Dict[str, str]:
    """
    Get authorization headers for TrueData API calls.
    Auto-refreshes token if expired/expiring.
    """
    token = get_truedata_token_for_connection(connection_id)
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}
