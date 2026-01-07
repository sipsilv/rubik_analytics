"""
TrueData API Service
Handles all TrueData API calls with correct authentication methods

CRITICAL: TrueData uses TWO different authentication methods:
1. TOKEN (Bearer) - for Corporate & Fundamental APIs
2. QUERY_CREDENTIALS - for Symbol Master API
"""
import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from app.services.token_service import get_token_service
from app.core.security import decrypt_data
import json

logger = logging.getLogger(__name__)



class TrueDataAPIService:
    """Service for calling TrueData APIs with correct authentication"""
    
    # API Base URLs
    AUTH_URL = "https://auth.truedata.in/token"
    SYMBOL_API_URL = "https://api.truedata.in/getAllSymbols"
    CORPORATE_API_BASE = "https://corporate.truedata.in/"
    
    def __init__(self, connection_id: int, db_session=None):
        """
        Initialize TrueData API service for a connection
        
        Args:
            connection_id: Connection ID from connections table
            db_session: SQLAlchemy session (optional, will create if needed)
        """
        self.connection_id = connection_id
        self.db_session = db_session
        self._credentials = None
        self._token_service = get_token_service()
    
    def _get_credentials(self) -> Dict[str, str]:
        """Get and decrypt connection credentials"""
        # Don't cache credentials - always fetch fresh from DB
        # This ensures we get updated credentials after reconfiguration
        self._credentials = None
        
        # Use provided session or create temporary one
        should_close = False
        if not self.db_session:
            from app.core.database import get_db
            from app.models.connection import Connection
            db_gen = get_db()
            self.db_session = next(db_gen)
            should_close = True
        
        try:
            from app.models.connection import Connection
            conn = self.db_session.query(Connection).filter(
                Connection.id == self.connection_id
            ).first()
            
            if not conn or not conn.credentials:
                raise ValueError("Connection not found or credentials not configured")
            
            try:
                decrypted_json = decrypt_data(conn.credentials)
                credentials = json.loads(decrypted_json)
                # Store in cache for this instance
                self._credentials = credentials
                return credentials
            except Exception as decrypt_error:
                error_msg = str(decrypt_error)
                if "InvalidToken" in error_msg or "InvalidSignature" in error_msg or "decrypt" in error_msg.lower():
                    raise ValueError(
                        f"Cannot decrypt credentials for connection {self.connection_id}. "
                        f"The encryption key may have changed. Please reconfigure the connection."
                    )
                raise ValueError(f"Error decrypting credentials: {error_msg}")
        except ValueError:
            raise  # Re-raise ValueError as-is
        except Exception as e:
            logger.error(f"Error getting credentials for connection {self.connection_id}: {e}")
            raise ValueError(f"Error getting credentials: {str(e)}")
        finally:
            if should_close and self.db_session:
                self.db_session.close()
                self.db_session = None
    
    def _get_token(self) -> str:
        """Get active token for connection (for Corporate APIs)"""
        token = self._token_service.get_token(connection_id=self.connection_id)
        if not token:
            # Try to refresh if expired
            credentials = self._get_credentials()
            username = credentials.get("username")
            password = credentials.get("password")
            auth_url = credentials.get("auth_url", self.AUTH_URL)
            
            if username and password:
                refreshed = self._token_service.refresh_token_if_needed(
                    connection_id=self.connection_id,
                    username=username,
                    password=password,
                    auth_url=auth_url
                )
                if refreshed:
                    token = self._token_service.get_token(connection_id=self.connection_id)
        
        if not token:
            raise ValueError("No active token available. Please generate a token first.")
        
        return token
    
    # ============================================================
    # 1. TOKEN AUTHENTICATION (Corporate & Fundamental APIs)
    # ============================================================
    
    def call_corporate_api(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Call TrueData Corporate API with Bearer token authentication
        
        Args:
            endpoint: API endpoint (e.g., "getCorpAction", "getMarketCap")
            method: HTTP method (GET, POST)
            params: Query parameters
            data: Request body (for POST)
            timeout: Request timeout in seconds
        
        Returns:
            API response as dictionary
        
        Examples:
            - getCorpAction
            - getCorpActionRange
            - getSymbolClassification
            - getCompanyLogo
            - getMarketCap
            - getCorporateInfo
        """
        token = self._get_token()
        url = f"{self.CORPORATE_API_BASE}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            if method.upper() == "GET":
                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=timeout
                )
            elif method.upper() == "POST":
                response = requests.post(
                    url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                # Token expired, try to refresh
                logger.warning(f"Token expired for connection {self.connection_id}, attempting refresh")
                credentials = self._get_credentials()
                username = credentials.get("username")
                password = credentials.get("password")
                auth_url = credentials.get("auth_url", self.AUTH_URL)
                
                if username and password:
                    self._token_service.generate_token(
                        connection_id=self.connection_id,
                        username=username,
                        password=password,
                        auth_url=auth_url
                    )
                    # Retry with new token
                    token = self._get_token()
                    headers["Authorization"] = f"Bearer {token}"
                    
                    if method.upper() == "GET":
                        response = requests.get(url, headers=headers, params=params, timeout=timeout)
                    else:
                        response = requests.post(url, headers=headers, params=params, json=data, timeout=timeout)
                    response.raise_for_status()
                    return response.json()
            
            logger.error(f"HTTP error calling Corporate API {endpoint}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling Corporate API {endpoint}: {e}")
            raise
    
    # ============================================================
    # 2. QUERY CREDENTIALS AUTHENTICATION (Symbol Master API)
    # ============================================================
    
    def get_all_symbols(
        self,
        segment: str = "eq",
        response_format: str = "json",
        timeout: int = 60
    ) -> Any:
        """
        Get all symbols from TrueData Symbol Master API
        
        This API uses QUERY PARAMETER authentication (NOT Bearer token)
        
        Args:
            segment: Market segment - "eq" (NSE) or "bseeq" (BSE)
            response_format: Response format - "json" or "csv"
            timeout: Request timeout in seconds
        
        Returns:
            JSON response as dict/list, or CSV as string
        
        Examples:
            - NSE: segment="eq"
            - BSE: segment="bseeq"
        """
        credentials = self._get_credentials()
        username = credentials.get("username")
        password = credentials.get("password")
        
        if not username or not password:
            raise ValueError("Username and password required for Symbol Master API")
        
        # Build URL with query parameters (NO Authorization header)
        params = {
            "segment": segment,
            "user": username,
            "password": password
        }
        
        if response_format.lower() == "csv":
            params["response"] = "csv"
        
        try:
            response = requests.get(
                self.SYMBOL_API_URL,
                params=params,
                timeout=timeout
            )
            response.raise_for_status()
            
            if response_format.lower() == "csv":
                return response.text
            else:
                return response.json()
                
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error calling Symbol Master API: {e}")
            if e.response is not None:
                logger.error(f"Response: {e.response.text[:500]}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling Symbol Master API: {e}")
            raise
    
    def get_nse_symbols(self, response_format: str = "json") -> Any:
        """Get NSE symbols (convenience method)"""
        return self.get_all_symbols(segment="eq", response_format=response_format)
    
    def get_bse_symbols(self, response_format: str = "json") -> Any:
        """Get BSE symbols (convenience method)"""
        return self.get_all_symbols(segment="bseeq", response_format=response_format)
    
    # ============================================================
    # CONVENIENCE METHODS FOR COMMON CORPORATE APIs
    # ============================================================
    
    def get_corp_action(self, symbol: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Get corporate actions"""
        params = kwargs.copy()
        if symbol:
            params["symbol"] = symbol
        return self.call_corporate_api("getCorpAction", params=params)
    
    def get_corp_action_range(
        self,
        from_date: str,
        to_date: str,
        symbol: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get corporate actions for date range"""
        params = {
            "from": from_date,
            "to": to_date,
            **kwargs
        }
        if symbol:
            params["symbol"] = symbol
        return self.call_corporate_api("getCorpActionRange", params=params)
    
    def get_symbol_classification(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """Get symbol classification"""
        params = {"symbol": symbol, **kwargs}
        return self.call_corporate_api("getSymbolClassification", params=params)
    
    def get_company_logo(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """Get company logo"""
        params = {"symbol": symbol, **kwargs}
        return self.call_corporate_api("getCompanyLogo", params=params)
    
    def get_market_cap(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """Get market capitalization"""
        params = {"symbol": symbol, **kwargs}
        return self.call_corporate_api("getMarketCap", params=params)
    
    def get_corporate_info(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """Get corporate information"""
        params = {"symbol": symbol, **kwargs}
        return self.call_corporate_api("getCorporateInfo", params=params)


def get_truedata_api_service(connection_id: int, db_session=None) -> TrueDataAPIService:
    """
    Get TrueData API service instance for a connection
    
    Args:
        connection_id: Connection ID from connections table
        db_session: Optional SQLAlchemy session
    
    Returns:
        TrueDataAPIService instance
    """
    return TrueDataAPIService(connection_id, db_session)

