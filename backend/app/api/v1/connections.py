from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import logging
import requests
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.permissions import get_current_user, get_admin_user
from app.core.security import encrypt_data, decrypt_data
from app.core.config import settings
from app.models.user import User
from app.models.connection import Connection, ConnectionStatus, ConnectionHealth
from app.schemas.connection import ConnectionCreate, ConnectionUpdate, ConnectionResponse
from app.core.audit import log_audit_event

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[ConnectionResponse])
async def get_connections(
    category: Optional[str] = None,
    include_manager: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """List all connections from database and connection manager"""
    from app.core.database import get_connection_manager
    from app.core.config import settings
    from app.schemas.connection import ConnectionResponse
    from datetime import datetime, timezone
    
    # Get connections from database (no filtering by status - show all)
    query = db.query(Connection)
    if category:
        query = query.filter(Connection.connection_type == category)
    db_connections = list(query.all())
    
    # Log for debugging
    logger.info(f"Found {len(db_connections)} connections in database (category={category})")
    for conn in db_connections:
        logger.debug(f"  - ID: {conn.id}, Name: {conn.name}, Provider: {conn.provider}, Status: {conn.status}, Type: {conn.connection_type}")
    
    # Convert database connections to ConnectionResponse
    result = []
    for conn in db_connections:
        # Handle None values before validation to avoid Pydantic errors
        try:
            # Extract URL and port from credentials for TrueData connections
            url = None
            port = None
            safe_details = {}
            
            provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
            
            # Decrypt credentials for all connections to populate 'details'
            if conn.credentials:
                try:
                    decrypted_json = decrypt_data(conn.credentials)
                    config = json.loads(decrypted_json)
                    
                    # For TrueData, specific URL/Port extraction
                    if provider_normalized == "TRUEDATA":
                        url = config.get("auth_url", settings.TRUEDATA_DEFAULT_AUTH_URL)
                        port = config.get("websocket_port", settings.TRUEDATA_DEFAULT_WEBSOCKET_PORT)
                    
                    # Mask sensitive fields
                    sensitive_keys = ['password', 'api_secret', 'access_token', 'api_hash', 'bot_token', 'secret_key', 'api_key_secret', 'api_key']
                    safe_details = {
                        k: ('********' if k in sensitive_keys or 'secret' in k.lower() or 'password' in k.lower() or 'hash' in k.lower() or 'token' in k.lower() else v) 
                        for k, v in config.items()
                    }
                    # Exception: Ensure api_id is visible (it's often public-ish or needed for identifying)
                    if 'api_id' in safe_details:
                         safe_details['api_id'] = config.get('api_id')
                         
                except Exception as e:
                    logger.debug(f"Could not extract/decrypt credentials for connection {conn.id}: {e}")
                    # Use defaults if extraction fails
                    if provider_normalized == "TRUEDATA":
                        url = settings.TRUEDATA_DEFAULT_AUTH_URL
                        port = settings.TRUEDATA_DEFAULT_WEBSOCKET_PORT

            # Prepare data with defaults for None values
            conn_dict = {
                'id': conn.id,
                'name': conn.name or "Unknown",
                'connection_type': conn.connection_type or "UNKNOWN",
                'provider': conn.provider or "UNKNOWN",
                'description': conn.description,
                'environment': conn.environment if conn.environment is not None else "PROD",
                'status': conn.status if conn.status is not None else "DISCONNECTED",
                'health': conn.health if conn.health is not None else "HEALTHY",
                'is_enabled': conn.is_enabled if conn.is_enabled is not None else False,
                'last_checked_at': conn.last_checked_at,
                'last_success_at': conn.last_success_at,
                'created_at': conn.created_at if conn.created_at is not None else datetime.now(timezone.utc),
                'updated_at': conn.updated_at,
                'url': url,
                'port': port,
                'details': safe_details
            }
            
            # Use model_validate with dict to ensure proper validation
            response = ConnectionResponse.model_validate(conn_dict)
            result.append(response)
        except Exception as e:
            # Log but don't fail - return partial data
            logger.error(f"Error serializing connection {conn.id} ({conn.name}): {e}", exc_info=True)
            # Try to create a minimal response with explicit defaults
            try:
                # Extract URL and port from credentials for TrueData connections
                url = None
                port = None
                provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
                if provider_normalized == "TRUEDATA" and conn.credentials:
                    try:
                        decrypted_json = decrypt_data(conn.credentials)
                        config = json.loads(decrypted_json)
                        url = config.get("auth_url", settings.TRUEDATA_DEFAULT_AUTH_URL)
                        port = config.get("websocket_port", settings.TRUEDATA_DEFAULT_WEBSOCKET_PORT)
                    except Exception:
                        url = settings.TRUEDATA_DEFAULT_AUTH_URL
                        port = settings.TRUEDATA_DEFAULT_WEBSOCKET_PORT
                
                result.append(ConnectionResponse(
                    id=conn.id,
                    name=conn.name or "Unknown",
                    connection_type=conn.connection_type or "UNKNOWN",
                    provider=conn.provider or "UNKNOWN",
                    description=conn.description,
                    environment=conn.environment if conn.environment is not None else "PROD",
                    status=conn.status if conn.status is not None else "DISCONNECTED",
                    health=conn.health if conn.health is not None else "HEALTHY",
                    is_enabled=conn.is_enabled if conn.is_enabled is not None else False,
                    last_checked_at=conn.last_checked_at,
                    last_success_at=conn.last_success_at,
                    created_at=conn.created_at if conn.created_at is not None else datetime.now(timezone.utc),
                    updated_at=conn.updated_at,
                    url=url,
                    port=port
                ))
            except Exception as e2:
                logger.error(f"Failed to create minimal response for connection {conn.id}: {e2}")
                # Skip this connection
                continue
    
    # Also include manager connections if requested
    if include_manager:
        manager = get_connection_manager(settings.DATA_DIR)
        manager_connections = manager.get_all_connections()
        
        # Filter by category if provided
        if category:
            # Map category to connection manager category
            category_map = {"auth": "auth", "analytics": "analytics"}
            manager_category = category_map.get(category.upper() if category else None)
            if manager_category:
                manager_connections = [c for c in manager_connections if c.get("category") == manager_category]
            else:
                manager_connections = []  # No match, don't include any
        # If category is None, include all manager connections
        
        # Convert manager connections to ConnectionResponse format
        for conn_config in manager_connections:
            # Test connection status
            conn_status = "DISCONNECTED"
            conn_health = "DOWN"
            try:
                if conn_config.get("category"):
                    client = manager.get_client(conn_config["category"])
                    if client and hasattr(client, 'test_connection'):
                        if client.test_connection():
                            conn_status = "CONNECTED"
                            conn_health = "HEALTHY"
                        else:
                            conn_status = "ERROR"
                            conn_health = "DOWN"
            except Exception:
                conn_status = "ERROR"
                conn_health = "DOWN"
            
            # Create ConnectionResponse object
            # Use a negative ID to distinguish from DB connections
            manager_conn_id = -(hash(conn_config.get("id", "")) % 1000000)
            created_at_str = conn_config.get("created_at", datetime.now(timezone.utc).isoformat())
            try:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            except:
                created_at = datetime.now(timezone.utc)
            
            manager_conn_response = ConnectionResponse(
                id=manager_conn_id,
                name=conn_config.get("name", "Unknown"),
                connection_type="INTERNAL",
                provider=conn_config.get("type", "Unknown").upper().replace("_", " "),
                description=f"Database: {conn_config.get('config', {}).get('path', 'N/A')}",
                environment="PROD",
                status=conn_status,
                health=conn_health,
                is_enabled=conn_config.get("is_active", True),
                last_checked_at=datetime.now(timezone.utc) if conn_status != "DISCONNECTED" else None,
                last_success_at=datetime.now(timezone.utc) if conn_status == "CONNECTED" else None,
                created_at=created_at,
                updated_at=None
            )
            result.append(manager_conn_response)
            
    
    # AI connections are now in SQLite and returned naturally from the query above
    return result

@router.post("/", response_model=ConnectionResponse)
async def create_connection(
    connection_data: ConnectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Create a new connection with encrypted credentials"""
    # Check uniqueness (case-insensitive, trim whitespace)
    normalized_name = connection_data.name.strip()
    # Get all connections and check case-insensitively (SQLite doesn't have reliable trim in func)
    all_connections = db.query(Connection).all()
    existing = None
    for conn in all_connections:
        if conn.name.strip().lower() == normalized_name.lower():
            existing = conn
            break
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Connection name '{normalized_name}' already exists (found existing: '{existing.name}', ID: {existing.id})"
        )

    # Handle TrueData connection specially
    is_truedata = connection_data.provider.upper() == "TRUEDATA"
    connection_status = ConnectionStatus.DISCONNECTED
    connection_health = ConnectionHealth.HEALTHY
    error_message = None
    
    # Validate TrueData credentials BEFORE creating connection
    if is_truedata and connection_data.details:
        try:
            # Extract TrueData credentials from details
            username = connection_data.details.get("username")
            password = connection_data.details.get("password")
            auth_url = connection_data.details.get("auth_url", settings.TRUEDATA_DEFAULT_AUTH_URL)
            
            if not username or not password:
                raise HTTPException(
                    status_code=400, 
                    detail="Username and password are required for TrueData connections"
                )
            
            # Validate credentials by attempting token generation (without storing)
            # We'll use a temporary connection_id of 0 for validation
            import requests
            try:
                response = requests.post(
                    auth_url,
                    data={
                        "username": username.strip(),
                        "password": password.strip(),
                        "grant_type": "password"
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    timeout=30
                )
                response.raise_for_status()
                token_data = response.json()
                if not token_data.get("access_token"):
                    raise ValueError("No access_token in response")
                
                # Credentials are valid
                connection_status = ConnectionStatus.CONNECTED
                connection_health = ConnectionHealth.HEALTHY
                logger.info(f"TrueData credentials validated successfully for connection: {connection_data.name}")
                
            except requests.exceptions.HTTPError as e:
                error_detail = e.response.json() if e.response else str(e)
                error_message = f"TrueData authentication failed (HTTP {e.response.status_code if hasattr(e, 'response') else 'Unknown'}): {error_detail}"
                connection_status = ConnectionStatus.ERROR
                connection_health = ConnectionHealth.DOWN
                logger.error(f"TrueData token validation failed: {error_message}")
            except requests.exceptions.RequestException as e:
                error_message = f"Network error validating TrueData credentials: {str(e)}"
                connection_status = ConnectionStatus.ERROR
                connection_health = ConnectionHealth.DOWN
                logger.error(f"TrueData credential validation network error: {error_message}")
            except Exception as token_error:
                error_message = f"TrueData authentication failed: {str(token_error)}"
                connection_status = ConnectionStatus.ERROR
                connection_health = ConnectionHealth.DOWN
                logger.error(f"TrueData token validation failed: {token_error}")
                
        except HTTPException:
            raise
            logger.error(f"Error processing TrueData connection: {e}", exc_info=True)
            connection_status = ConnectionStatus.ERROR
            connection_health = ConnectionHealth.DOWN
            error_message = f"Error setting up TrueData connection: {str(e)}"
    # Validate Telegram Bot credentials (if Connection Type is TELEGRAM_BOT)
    # Validate Telegram Bot credentials (if Connection Type is TELEGRAM_BOT)
    elif connection_data.connection_type == "TELEGRAM_BOT" and connection_data.details:
        bot_token = connection_data.details.get("bot_token")
        if bot_token:
            try:
                import aiohttp
                # Strip "bot" prefix if user accidentally included it
                clean_token = bot_token.strip()
                if clean_token.lower().startswith("bot") and len(clean_token) > 3 and clean_token[3].isdigit():
                    clean_token = clean_token[3:]
                    logger.info("Stripped 'bot' prefix from token")

                # Update the details with the clean token so it's saved correctly
                connection_data.details["bot_token"] = clean_token

                async with aiohttp.ClientSession() as session:
                    async with session.get(f"https://api.telegram.org/bot{clean_token}/getMe", timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("ok"):
                                connection_status = ConnectionStatus.CONNECTED
                                connection_health = ConnectionHealth.HEALTHY
                                logger.info(f"Telegram Bot validated: {data.get('result', {}).get('first_name')}")
                            else:
                                raise HTTPException(
                                    status_code=400,
                                    detail=f"Telegram API Error: {data.get('description')}"
                                )
                        elif resp.status == 401:
                             raise HTTPException(
                                 status_code=400,
                                 detail="Invalid Bot Token. Telegram rejected authorization (401). Please double-check your token from @BotFather."
                             )
                        elif resp.status == 404:
                             raise HTTPException(
                                 status_code=400,
                                 detail="Invalid Bot Token Format (404). Please ensure you didn't paste extra text or the 'bot' prefix twice."
                             )
                        else:
                            raise HTTPException(
                                status_code=400,
                                detail=f"Telegram API HTTP Error: {resp.status}"
                            )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Telegram Validation Failed: {str(e)}"
                )

    # Validate Telegram User credentials
    elif connection_data.connection_type in ["TELEGRAMUSER", "TELEGRAM_USER"] and connection_data.details:
        api_id = connection_data.details.get("api_id")
        api_hash = connection_data.details.get("api_hash")
        if not (api_id and api_hash):
             raise HTTPException(
                 status_code=400,
                 detail="Missing API ID or Hash for Telegram User"
             )
        connection_status = ConnectionStatus.CONNECTED
        connection_health = ConnectionHealth.HEALTHY


    # Validate AI Connection - Skip adapter validation, handled by ai_connection_manager
    elif connection_data.connection_type == "AI_ML":
        # Set initial status - will be validated when connection is tested
        connection_status = ConnectionStatus.DISCONNECTED
        connection_health = ConnectionHealth.HEALTHY
        logger.info(f"AI Connection will be created: {connection_data.provider}")


    # Encrypt details if present
    encrypted_creds = None
    if connection_data.details:
        try:
            logger.info(f"Creating connection - details keys: {list(connection_data.details.keys())}")
            # Mask sensitive keys
            masked_details = {
                k: ('***' if k in ['password', 'api_secret', 'api_key', 'access_token'] else v) 
                for k, v in connection_data.details.items()
            }
            logger.info(f"Details content (masked): {masked_details}")
            json_str = json.dumps(connection_data.details)
            encrypted_creds = encrypt_data(json_str)
            logger.info(f"Credentials encrypted successfully, length: {len(encrypted_creds)}")
        except Exception as e:
            logger.error(f"Encryption failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Encryption failed: {str(e)}")
    else:
        logger.warning(f"No details provided for connection creation: {connection_data.name}")

    # Raising error here if it was set earlier (e.g. TrueData) and flow reached here
    if error_message:
        raise HTTPException(
            status_code=400,
            detail=error_message
        )

    # All connections including AI_ML are now stored in SQLite
    # AI-specific fields (model_name, base_url, timeout, etc.) are stored in the encrypted credentials JSON
    
    new_conn = Connection(
        name=connection_data.name,
        connection_type=connection_data.connection_type,
        provider=connection_data.provider,
        description=connection_data.description,
        environment=connection_data.environment,
        is_enabled=connection_data.is_enabled,
        credentials=encrypted_creds,
        status=connection_status.value,
        health=connection_health.value,
        last_checked_at=datetime.now(timezone.utc) if connection_status == ConnectionStatus.CONNECTED else None,
        last_success_at=datetime.now(timezone.utc) if connection_status == ConnectionStatus.CONNECTED else None,
        error_logs=None # No error logs if we are creating successfully
    )
    
    db.add(new_conn)
    db.commit()
    db.refresh(new_conn)
    
    # NOW generate and store token if connection was created successfully
    if is_truedata and connection_status == ConnectionStatus.CONNECTED and new_conn.id:
        try:
            from app.services.token_service import get_token_service
            token_service = get_token_service()
            
            username = connection_data.details.get("username")
            password = connection_data.details.get("password")
            auth_url = connection_data.details.get("auth_url", settings.TRUEDATA_DEFAULT_AUTH_URL)
            
            if username and password:
                try:
                    token_result = token_service.generate_token(
                        connection_id=new_conn.id,
                        username=username.strip(),
                        password=password.strip(),
                        auth_url=auth_url
                    )
                    logger.info(f"Token generated and stored for connection {new_conn.id}")
                except Exception as token_error:
                    logger.warning(f"Token generation failed after connection creation: {token_error}")
                    # Don't fail the connection creation, just log the warning
        except Exception as e:
            logger.warning(f"Error generating token after connection creation: {e}")
    
    log_audit_event(
        db, 
        current_user.id, 
        "CREATE_CONNECTION", 
        "connections", 
        str(new_conn.id), 
        None, 
        {"name": new_conn.name, "type": new_conn.connection_type, "status": connection_status.value}
    )
    
    # Create response with details
    from app.schemas.connection import ConnectionResponse
    
    # Use masked details we created earlier
    response_details = masked_details if connection_data.details else {}
    
    # Extract URL/Port if TrueData
    url = None
    port = None
    if is_truedata:
        url = connection_data.details.get("auth_url", settings.TRUEDATA_DEFAULT_AUTH_URL)
        port = connection_data.details.get("websocket_port", settings.TRUEDATA_DEFAULT_WEBSOCKET_PORT)

    return ConnectionResponse(
        id=new_conn.id,
        name=new_conn.name,
        connection_type=new_conn.connection_type,
        provider=new_conn.provider,
        description=new_conn.description,
        environment=new_conn.environment,
        status=new_conn.status,
        health=new_conn.health,
        is_enabled=new_conn.is_enabled,
        last_checked_at=new_conn.last_checked_at,
        last_success_at=new_conn.last_success_at,
        created_at=new_conn.created_at,
        updated_at=new_conn.updated_at,
        url=url,
        port=port,
        details=response_details
    )

@router.get("/{id}", response_model=ConnectionResponse)
async def get_connection(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    # Handle AI Connections (Negative IDs)
    if id < 0:
        try:
            from app.services.ai_connection_manager import get_ai_connection
            ai = get_ai_connection(abs(id))
            if not ai:
                raise HTTPException(status_code=404, detail="AI Connection not found")
            
            details_dict = {
                "base_url": ai['base_url'],
                "model_name": ai['model_name'],
                "timeout_seconds": ai['timeout_seconds'],
                "ai_prompt_template": ai['ai_prompt_template'],
                "is_active": ai['is_active'],
                "api_key": ai['api_key'] # Return encrypted or let frontend handle blank if masked
            }
            
            return ConnectionResponse(
                id=ai['connection_id'] * -1, 
                name=ai['connection_name'],
                connection_type='AI_ML',
                provider=ai['provider_type'],
                description=f"Model: {ai['model_name']}",
                environment="PROD",
                status=ai['status'],
                health="HEALTHY" if ai['status'] == 'CONNECTED' else "DOWN",
                is_enabled=ai['is_enabled'],
                last_checked_at=ai['last_checked_at'],
                last_success_at=None,
                created_at=ai['created_at'],
                updated_at=ai['updated_at'],
                details=details_dict
            )
        except Exception as e:
            logger.error(f"Error fetching AI connection {id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Extract URL and port from credentials for TrueData connections
    url = None
    port = None
    provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
    if provider_normalized == "TRUEDATA" and conn.credentials:
        try:
            decrypted_json = decrypt_data(conn.credentials)
            config = json.loads(decrypted_json)
            url = config.get("auth_url", settings.TRUEDATA_DEFAULT_AUTH_URL)
            port = config.get("websocket_port", settings.TRUEDATA_DEFAULT_WEBSOCKET_PORT)
        except Exception as e:
            logger.debug(f"Could not extract URL/port from credentials for connection {conn.id}: {e}")
            url = settings.TRUEDATA_DEFAULT_AUTH_URL
            port = settings.TRUEDATA_DEFAULT_WEBSOCKET_PORT
    
    # Create response with URL and port
    conn_dict = {
        'id': conn.id,
        'name': conn.name,
        'connection_type': conn.connection_type,
        'provider': conn.provider,
        'description': conn.description,
        'environment': conn.environment if conn.environment is not None else "PROD",
        'status': conn.status if conn.status is not None else "DISCONNECTED",
        'health': conn.health if conn.health is not None else "HEALTHY",
        'is_enabled': conn.is_enabled if conn.is_enabled is not None else False,
        'last_checked_at': conn.last_checked_at,
        'last_success_at': conn.last_success_at,
        'created_at': conn.created_at if conn.created_at is not None else datetime.now(timezone.utc),
        'updated_at': conn.updated_at,
        'url': url,
        'port': port
    }
    
    return ConnectionResponse.model_validate(conn_dict)

@router.get("/{id}/status")
async def get_connection_status(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get connection status including token status for TrueData connections"""
    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    response = {
        "status": conn.status,
        "health": conn.health,
        "is_enabled": conn.is_enabled,
        "last_checked_at": conn.last_checked_at.isoformat() if conn.last_checked_at else None,
        "last_success_at": conn.last_success_at.isoformat() if conn.last_success_at else None,
    }
    
    # Add token status for TrueData connections (normalize provider name)
    provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
    if provider_normalized == "TRUEDATA":
        try:
            from app.services.token_service import get_token_service
            token_service = get_token_service()
            
            token_status = token_service.get_token_status(connection_id=id)
            
            if token_status:
                response["token_status"] = token_status.get("token_status", "UNKNOWN")
                response["expires_at"] = token_status.get("expires_at")
                response["seconds_left"] = token_status.get("seconds_left", 0)
            else:
                response["token_status"] = "NOT_GENERATED"
                response["expires_at"] = None
                response["seconds_left"] = None
                
        except Exception as e:
            logger.error(f"Error getting token status: {e}")
            response["token_status"] = "ERROR"
            response["expires_at"] = None
            response["seconds_left"] = None
    
    return response

    return response

@router.post("/{id}/test")
async def test_connection(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Test a specific connection logic"""
    # All connections including AI_ML are now in SQLite
    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Decrypt credentials
    details = {}
    if conn.credentials:
        try:
            details = json.loads(decrypt_data(conn.credentials))
        except Exception as e:
            raise HTTPException(status_code=500, detail="Could not decrypt credentials")

    success = False
    message = "Unknown Connection Type"

    if conn.connection_type == "AI_ML":
        # Simple connectivity test for AI connections
        if details.get("base_url"):
            try:
                import requests
                response = requests.get(details["base_url"], timeout=5)
                if response.status_code < 500:
                    success = True
                    message = f"Successfully connected to {conn.provider} at {details['base_url']}"
                else:
                    success = False
                    message = f"Server error from {details['base_url']}: {response.status_code}"
            except requests.exceptions.Timeout:
                success = False
                message = "Connection timeout - server not responding"
            except requests.exceptions.ConnectionError:
                success = False
                message = "Connection failed - unable to reach server"
            except Exception as e:
                success = False
                message = f"Connection error: {str(e)}"
        else:
            success = True
            message = f"AI connection configured for {conn.provider} with model {details.get('model_name', 'unknown')}"
            
    elif conn.connection_type == "TELEGRAM_BOT":
        # Reuse logic from create/update if possible, or simple check
        try:
            import requests # or aiohttp
            token = details.get('bot_token')
            if not token:
                success = False
                message = "Missing Bot Token"
            else:
                resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
                if resp.status_code == 200:
                    success = True
                    message = "Telegram Bot Connected"
                else:
                    success = False
                    message = f"Telegram Error: {resp.text}"
        except Exception as e:
            success = False
            message = str(e)
            
    # Update Status
    if success:
        conn.status = "CONNECTED"
        conn.health = "HEALTHY"
        conn.last_checked_at = datetime.now(timezone.utc)
        conn.last_success_at = datetime.now(timezone.utc)
        conn.error_logs = None
    else:
        conn.status = "ERROR"
        conn.health = "DOWN"
        conn.last_checked_at = datetime.now(timezone.utc)
        conn.error_logs = json.dumps({"error": message})
        
    db.commit()
    
    return {
        "success": success,
        "message": message,
        "status": conn.status
    }

@router.put("/{id}", response_model=ConnectionResponse)
async def update_connection(
    id: int,
    update_data: ConnectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    # Handle AI Connections (Negative IDs)
    if id < 0:
        try:
            from app.services.ai_connection_manager import update_ai_connection, get_ai_connection
            
            # Map update_data to AI fields
            db_id = abs(id)
            updates = {}
            
            if update_data.details:
                if 'prompt' in update_data.details:
                    updates['prompt_template'] = update_data.details['prompt']
                # Frontend might send 'ai_prompt_template'
                if 'ai_prompt_template' in update_data.details:
                    updates['prompt_template'] = update_data.details['ai_prompt_template']
                    
                if 'model_name' in update_data.details:
                    updates['model_name'] = update_data.details['model_name']
                    
                if 'timeout' in update_data.details:
                    updates['timeout'] = int(update_data.details['timeout'])
                if 'timeout_seconds' in update_data.details:
                    updates['timeout'] = int(update_data.details['timeout_seconds'])
                    
                if 'is_active' in update_data.details:
                    updates['is_active'] = bool(update_data.details['is_active'])
                    
                if 'base_url' in update_data.details:
                    updates['base_url'] = update_data.details['base_url']

                if 'api_key' in update_data.details:
                    updates['api_key'] = update_data.details['api_key']

            # Call update
            update_ai_connection(db_id, **updates)
            
            # Re-fetch to return full response
            # Since we just implemented get logic above, we can assume a helper or just re-fetch using manager
            ai = get_ai_connection(db_id)
            if not ai:
                 raise HTTPException(status_code=404, detail="AI Connection not found after update")
                 
            details_dict = {
                "base_url": ai['base_url'],
                "model_name": ai['model_name'],
                "timeout_seconds": ai['timeout_seconds'],
                "ai_prompt_template": ai['ai_prompt_template'],
                "is_active": ai['is_active']
            }
            
            return ConnectionResponse(
                id=ai['connection_id'] * -1, 
                name=ai['connection_name'],
                connection_type='AI_ML',
                provider=ai['provider_type'],
                description=f"Model: {ai['model_name']}",
                environment="PROD",
                status=ai['status'],
                health="HEALTHY" if ai['status'] == 'CONNECTED' else "DOWN",
                is_enabled=ai['is_enabled'],
                last_checked_at=ai['last_checked_at'],
                last_success_at=None,
                created_at=ai['created_at'],
                updated_at=ai['updated_at'],
                details=details_dict
            )
            
        except Exception as e:
            logger.error(f"Error updating AI connection {id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    logger.info(f"Received update request for connection ID {id} with data: {update_data}")
    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        logger.error(f"Connection ID {id} not found.")
        raise HTTPException(status_code=404, detail="Connection not found")
        
    old_state = {"name": conn.name, "enabled": conn.is_enabled}
    # Normalize provider name for TrueData check
    provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
    is_truedata = provider_normalized == "TRUEDATA"
    connection_status = conn.status
    connection_health = conn.health
    error_message = None

    if update_data.name:
        conn.name = update_data.name
    if update_data.provider: # Allow updating provider
        conn.provider = update_data.provider
    if update_data.description:
        conn.description = update_data.description
    if update_data.environment:
        conn.environment = update_data.environment
    if update_data.is_enabled is not None:
        conn.is_enabled = update_data.is_enabled
        
    # Update credentials if provided
    if update_data.details:
        try:
            merged_details = None
            
            # GENERIC MERGE: Get existing credentials first for ALL providers
            existing_config = {}
            if conn.credentials:
                try:
                    decrypted_existing = decrypt_data(conn.credentials)
                    existing_config = json.loads(decrypted_existing)
                    logger.info(f"Loaded existing credentials for connection {id}, keys: {list(existing_config.keys())}")
                except ValueError as e:
                    # Invalid encryption key configuration
                    logger.error(f"Invalid encryption key configuration: {e}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Invalid encryption key configuration. Cannot decrypt existing credentials. Please check ENCRYPTION_KEY environment variable."
                    )
                except Exception as e:
                    logger.warning(f"Could not decrypt existing credentials: {e}")
                    # If we can't decrypt and user is only updating URL/port (not providing username/password),
                    # we need to fail gracefully if it is critical, but for now we proceed.
            
            # Merge: use new values if provided, otherwise keep existing
            merged_details = existing_config.copy() if existing_config else {}
            logger.info(f"Starting merge - existing keys: {list(existing_config.keys())}, new keys: {list(update_data.details.keys())}")
            
            for key, value in update_data.details.items():
                # Only update if value is not None/undefined/empty string
                # Also check for string "undefined" which might come from JSON
                value_str = str(value).strip() if value is not None else ""
                if value is not None and value != "" and value_str != "" and str(value).lower() != "undefined":
                    merged_details[key] = value
                else:
                    # Keep existing value if it exists
                    if key not in merged_details:
                        logger.warning(f"Key {key} not in existing config and new value is empty - this field will be missing!")
            
            # Ensure required fields are present for TrueData specifically
            if is_truedata:
                if "username" not in merged_details or not merged_details.get("username"):
                    logger.error(f"CRITICAL: Username is missing after merge for connection {id}")
                    raise HTTPException(
                        status_code=400,
                        detail="Username is required. Please enter your TrueData username in the Configure dialog and save the connection."
                    )
                if "password" not in merged_details or not merged_details.get("password"):
                    logger.error(f"CRITICAL: Password is missing after merge for connection {id}")
                    raise HTTPException(
                        status_code=400,
                        detail="Password is required. Please enter your TrueData password in the Configure dialog and save the connection."
                    )
            
                logger.info(f"Merged credentials keys: {list(merged_details.keys())}")
                logger.info(f"Merged credentials (masked): { {k: ('***' if k in ['password', 'api_secret'] else v) for k, v in merged_details.items()} }")
                
                from app.services.token_service import get_token_service
                token_service = get_token_service()
                
                # Extract TrueData credentials from merged details
                username = merged_details.get("username")
                password = merged_details.get("password")
                auth_url = merged_details.get("auth_url", settings.TRUEDATA_DEFAULT_AUTH_URL)
                
                # Only regenerate token if username/password are provided and not empty
                if username and password and username.strip() and password.strip():
                    try:
                        token_result = token_service.generate_token(
                            connection_id=id,
                            username=username.strip(),
                            password=password.strip(),
                            auth_url=auth_url
                        )
                        
                        # Token generated successfully
                        connection_status = ConnectionStatus.CONNECTED
                        connection_health = ConnectionHealth.HEALTHY
                        conn.last_checked_at = datetime.now(timezone.utc)
                        conn.last_success_at = datetime.now(timezone.utc)
                        conn.error_logs = None
                        logger.info(f"Token regenerated successfully during connection update")
            

                        
                    except requests.exceptions.HTTPError as e:
                        # Token generation failed with HTTP error
                        connection_status = ConnectionStatus.ERROR
                        connection_health = ConnectionHealth.DOWN
                        error_detail = ""
                        if hasattr(e, 'response') and e.response is not None:
                            try:
                                error_detail = e.response.json()
                            except:
                                error_detail = e.response.text[:200] if e.response.text else str(e)
                        error_message = f"TrueData authentication failed (HTTP {e.response.status_code if hasattr(e, 'response') and e.response else 'Unknown'}): {error_detail}"
                        logger.error(f"TrueData token generation failed during update: {error_message}")
                        conn.error_logs = json.dumps({"error": error_message})
                        # Don't raise here - allow connection to be saved with error status
                    except Exception as token_error:
                        # Token generation failed
                        connection_status = ConnectionStatus.ERROR
                        connection_health = ConnectionHealth.DOWN
                        error_message = f"TrueData authentication failed: {str(token_error)}"
                        logger.error(f"TrueData token generation failed during update: {token_error}")
                        conn.error_logs = json.dumps({"error": error_message})
                        # Don't raise here - allow connection to be saved with error status
            
            # Encrypt and store credentials (use merged_details if available, else new details)
            final_details = merged_details if merged_details else update_data.details
            logger.info(f"Final credentials to save - keys: {list(final_details.keys())}")
            logger.info(f"Final credentials (masked): { {k: ('***' if k in ['password', 'api_secret'] else v) for k, v in final_details.items()} }")
            
            # Validate that required fields are present for TrueData
            if is_truedata:
                if "username" not in final_details or not final_details.get("username"):
                    raise HTTPException(
                        status_code=400,
                        detail="Username is required. Please enter your TrueData username in the Configure dialog and save the connection."
                    )
                if "password" not in final_details or not final_details.get("password"):
                    raise HTTPException(
                        status_code=400,
                        detail="Password is required. Please enter your TrueData password in the Configure dialog and save the connection."
                    )
            
            # Update status for Telegram User
            elif provider_normalized in ["TELEGRAMUSER", "TELEGRAM_USER"]:
                 api_id = final_details.get("api_id")
                 api_hash = final_details.get("api_hash")
                 if api_id and api_hash:
                      conn.status = ConnectionStatus.CONNECTED.value
                      conn.health = ConnectionHealth.HEALTHY.value
                      conn.last_checked_at = datetime.now(timezone.utc)
                      # conn.last_success_at = datetime.now(timezone.utc) # Only set success if we actually tested. But CONNECTED implies success here.
                      conn.error_logs = None
                 else:
                      conn.status = ConnectionStatus.ERROR.value
                      conn.health = ConnectionHealth.DOWN.value
            
            try:
                json_str = json.dumps(final_details)
                conn.credentials = encrypt_data(json_str)
                logger.info(f"Credentials encrypted and stored for connection {id}")
            except ValueError as e:
                # Invalid encryption key configuration
                logger.error(f"Encryption failed due to invalid encryption key: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Invalid encryption key configuration. Cannot encrypt credentials. Please check ENCRYPTION_KEY environment variable."
                )
            except Exception as e:
                logger.error(f"Encryption failed: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Encryption failed: {str(e)}")
            
            # Update status if it changed
            if is_truedata:
                # Ensure we convert enum to string if it's an enum, otherwise use as-is
                conn.status = connection_status.value if hasattr(connection_status, 'value') else str(connection_status)
                conn.health = connection_health.value if hasattr(connection_health, 'value') else str(connection_health)
            
            elif provider_normalized in ["TELEGRAMUSER", "TELEGRAM_USER"]:
                 api_id = final_details.get("api_id")
                 api_hash = final_details.get("api_hash")
                 session_string = final_details.get("session_string")

                 if api_id and api_hash and session_string:
                      conn.status = ConnectionStatus.CONNECTED.value
                      conn.health = ConnectionHealth.HEALTHY.value
                      conn.last_checked_at = datetime.now(timezone.utc)
                      conn.last_success_at = datetime.now(timezone.utc)
                      conn.error_logs = None
                 elif api_id and api_hash:
                      # Configured but not logged in
                      conn.status = ConnectionStatus.DISCONNECTED.value
                      conn.health = ConnectionHealth.DOWN.value
                      conn.last_checked_at = datetime.now(timezone.utc)
                      conn.error_logs = json.dumps({"message": "Login Required: Please verify OTP"})
                 else:
                      conn.status = ConnectionStatus.ERROR.value
                      conn.health = ConnectionHealth.DOWN.value
            
            elif conn.connection_type == "AI_ML":
                 try:
                     from app.services.ai_adapter import get_adapter
                     adapter = get_adapter(conn.provider, final_details)
                     success, message = adapter.test_connection()
                     
                     if success:
                         conn.status = ConnectionStatus.CONNECTED.value
                         conn.health = ConnectionHealth.HEALTHY.value
                         conn.last_checked_at = datetime.now(timezone.utc)
                         conn.last_success_at = datetime.now(timezone.utc)
                         conn.error_logs = None
                         logger.info(f"AI Connection re-validated: {message}")
                     else:
                         conn.status = ConnectionStatus.ERROR.value
                         conn.health = ConnectionHealth.DOWN.value
                         conn.error_logs = json.dumps({"error": message})
                         logger.warning(f"AI Connection re-validation failed: {message}")
                         
                 except Exception as e:
                     conn.status = ConnectionStatus.ERROR.value
                     conn.health = ConnectionHealth.DOWN.value
                     conn.error_logs = json.dumps({"error": str(e)})
                     logger.error(f"AI Connection Update Error: {e}")

            elif conn.connection_type == "TELEGRAM_BOT":
                 bot_token = final_details.get("bot_token")
                 logger.info(f"Validating Telegram Bot Token: {bot_token[:5]}... (Length: {len(bot_token) if bot_token else 0})")
                 
                 if bot_token:
                    try:
                        import aiohttp
                        # Strip "bot" prefix if user accidentally included it
                        clean_token = bot_token.strip()
                        if clean_token.lower().startswith("bot") and clean_token[3].isdigit():
                            clean_token = clean_token[3:]
                            logger.info("Stripped 'bot' prefix from token")
                        
                        # Update final_details with clean token if changed
                        if clean_token != bot_token:
                            final_details["bot_token"] = clean_token
                            # Re-encrypt
                            json_str = json.dumps(final_details)
                            conn.credentials = encrypt_data(json_str)

                        async with aiohttp.ClientSession() as session:
                             async with session.get(f"https://api.telegram.org/bot{clean_token}/getMe", timeout=10) as resp:
                                logger.info(f"Telegram API Response Code: {resp.status}")
                                
                                if resp.status == 200:
                                    data = await resp.json()
                                    if data.get("ok"):
                                        conn.status = ConnectionStatus.CONNECTED.value
                                        conn.health = ConnectionHealth.HEALTHY.value
                                        conn.last_checked_at = datetime.now(timezone.utc)
                                        conn.last_success_at = datetime.now(timezone.utc)
                                        conn.error_logs = None
                                        logger.info(f"Telegram Bot re-validated: {data.get('result', {}).get('first_name')}")
                                    else:
                                        error_desc = data.get('description', 'Unknown Error')
                                        error_message = f"Telegram API Check Failed: {error_desc}"
                                        logger.error(error_message)
                                        conn.status = ConnectionStatus.ERROR.value
                                        conn.health = ConnectionHealth.DOWN.value
                                        conn.error_logs = json.dumps({"error": error_message})
                                elif resp.status == 401:
                                     error_message = "Invalid Bot Token (Unauthorized)"
                                     logger.error(error_message)
                                     conn.status = ConnectionStatus.ERROR.value
                                     conn.health = ConnectionHealth.DOWN.value
                                     conn.error_logs = json.dumps({"error": error_message})
                                else:
                                    error_message = f"Telegram API HTTP Error: {resp.status} - {await resp.text()}"
                                    logger.error(error_message)
                                    conn.status = ConnectionStatus.ERROR.value
                                    conn.health = ConnectionHealth.DOWN.value
                                    conn.error_logs = json.dumps({"error": error_message})
                    except Exception as e:
                        error_message = f"Telegram Validation Exception: {str(e)}"
                        logger.exception(error_message)
                        conn.status = ConnectionStatus.ERROR.value
                        conn.health = ConnectionHealth.DOWN.value
                        conn.error_logs = json.dumps({"error": error_message})

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating connection credentials: {e}")
            raise HTTPException(status_code=500, detail=f"Encryption failed: {str(e)}")
    
    conn.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conn)
    
    
    log_audit_event(
        db, 
        current_user.id, 
        "UPDATE_CONNECTION", 
        "connections", 
        str(conn.id), 
        old_state, 
        {"name": conn.name, "enabled": conn.is_enabled, "status": conn.status}
    )
    
    
    # If there was an error with token generation, raise it after saving
    if error_message:
        raise HTTPException(
            status_code=400,
            detail=error_message
        )
    
    return conn

@router.delete("/{id}")
async def delete_connection(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    # Only SUPER ADMIN can delete
    if current_user.role.lower() != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can delete connections")

    # Handle AI Connections (Negative IDs)
    if id < 0:
        try:
            from app.services.ai_connection_manager import delete_ai_connection
            # Use manager to delete
            success = delete_ai_connection(abs(id))
            if not success:
                 raise HTTPException(status_code=404, detail="AI Connection not found")
            
            # Log audit
            log_audit_event(
                db, 
                current_user.id, 
                "DELETE_CONNECTION", 
                "connections", 
                str(id), 
                {"type": "AI_ML"}, 
                None
            )
            return {"message": "AI Connection deleted"}
        except Exception as e:
            logger.error(f"Error deleting AI connection {id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        
    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # If this is a TrueData connection, delete the token (normalize provider name)
    provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
    if provider_normalized == "TRUEDATA":
        try:
            from app.services.token_service import get_token_service
            token_service = get_token_service()
            token_service.delete_token(connection_id=id)
        except Exception as e:
            logger.warning(f"Failed to delete TrueData token: {e}")
    
    # TODO: Disable all dependent connections that reference this provider
    # This would require a field in Connection model to track token_provider references
        
    db.delete(conn)
    db.commit()
    
    log_audit_event(
        db, 
        current_user.id, 
        "DELETE_CONNECTION", 
        "connections", 
        str(id), 
        {"name": conn.name}, 
        None
    )
    
    return {"message": "Connection deleted"}

@router.post("/{id}/toggle")
async def toggle_connection(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    # All connections including AI_ML are now in SQLite
    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    conn.is_enabled = not conn.is_enabled
    db.commit()
    
    status = "enabled" if conn.is_enabled else "disabled"
    log_audit_event(
        db, current_user.id, f"{status.upper()}_CONNECTION", "connections", str(id)
    )
    
    return {"status": status, "is_enabled": conn.is_enabled}

@router.post("/{id}/test")
async def test_connection(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    # Handle ConnectionManager connections (negative IDs)
    if id < 0:
        from app.core.database import get_connection_manager
        from app.core.config import settings
        
        manager = get_connection_manager(settings.DATA_DIR)
        connections = manager.get_all_connections()
        
        target_conn_id = None
        for conn_config in connections:
            # Replicate the ID generation logic from get_connections
            conn_id_int = -(hash(conn_config.get("id", "")) % 1000000)
            if conn_id_int == id:
                target_conn_id = conn_config.get("id")
                break
        
        if target_conn_id:
            try:
                result = manager.test_connection(target_conn_id)
                if result:
                    return {"status": "success", "message": f"Connection test successful for {target_conn_id}"}
                else:
                    return {"status": "error", "message": f"Connection test failed for {target_conn_id}"}
            except Exception as e:
                return {"status": "error", "message": f"Connection test error: {str(e)}"}
        else:
            raise HTTPException(status_code=404, detail="System connection not found (ID mismatch)")

    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    # Real Test Logic
    try:
        # Decrypt credentials if available
        config = {}
        if conn.credentials:
            try:
                decrypted_json = decrypt_data(conn.credentials)
                config = json.loads(decrypted_json)
            except Exception as e:
                print(f"Error decrypting credentials: {e}")
                raise Exception("Failed to decrypt connection credentials")
        
        # Determine connection mechanism based on provider
        # Normalize provider name for comparison
        provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
        provider = conn.provider.lower()
        is_connected = False
        message = ""
        
        # Handle TrueData token-based connections
        # Handle TrueData token-based connections
        if provider_normalized == "TRUEDATA":
            try:
                from app.services.token_service import get_token_service
                token_service = get_token_service()
                
                # Try to generate/refresh token
                username = config.get("username")
                password = config.get("password")
                auth_url = config.get("auth_url", settings.TRUEDATA_DEFAULT_AUTH_URL)
                
                if username and password:
                    token_result = token_service.generate_token(
                        connection_id=id,
                        username=username,
                        password=password,
                        auth_url=auth_url
                    )
                    
                    if token_result:
                        is_connected = True
                        message = "TrueData authentication successful"
                    else:
                        message = "TrueData token generation failed"
                else:
                    message = "Missing TrueData credentials (username/password)"
            
            except Exception as e:
                is_connected = False
                message = f"TrueData Test Failed: {str(e)}"
            
            # DB Update for TrueData
            if is_connected:
                conn.status = "CONNECTED"
                conn.health = "HEALTHY"
                conn.last_checked_at = datetime.now(timezone.utc)
                conn.last_success_at = datetime.now(timezone.utc)
                conn.error_logs = None
            else:
                conn.status = "ERROR"
                conn.health = "DOWN"
                conn.last_checked_at = datetime.now(timezone.utc)
                conn.error_logs = json.dumps({"error": message})
            
            db.commit()
            return {"status": "success" if is_connected else "error", "message": message}

        # Add Telegram Bot Test Logic
        # Check connection_type OR provider name for robustness
        elif (conn.connection_type == "TELEGRAM_BOT") or (provider_normalized == "TELEGRAMBOT") or (provider_normalized == "TELEGRAM"):
            if config.get("bot_token"):
                try:
                    import aiohttp
                    token = config.get("bot_token")
                    
                    # Strip "bot" prefix if present
                    clean_token = token.strip()
                    if clean_token.lower().startswith("bot") and len(clean_token) > 3 and clean_token[3].isdigit():
                        clean_token = clean_token[3:]
                    
                    # Call getMe to verify token using aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"https://api.telegram.org/bot{clean_token}/getMe", timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get("ok"):
                                    bot_info = data.get("result", {})
                                    is_connected = True
                                    message = f"Connected as @{bot_info.get('username')} ({bot_info.get('first_name')})"
                                else:
                                    message = f"Telegram API Error: {data.get('description')}"
                            elif resp.status == 401:
                                message = "Invalid Bot Token (Unauthorized). Please check your token."
                            elif resp.status == 404:
                                message = "Invalid Bot Token Format (404). Check for extra characters or 'bot' prefix."
                            else:
                                message = f"Telegram API HTTP Error: {resp.status} - {await resp.text()}"

                except Exception as e:
                    message = f"Telegram Connection Failed: {str(e)}"
            else:
                 message = "Bot Token is missing in configuration."
            
            # DB Update for Telegram
            if is_connected:
                conn.status = "CONNECTED"
                conn.health = "HEALTHY"
                conn.last_checked_at = datetime.now(timezone.utc)
                conn.last_success_at = datetime.now(timezone.utc)
                conn.error_logs = None
            else:
                conn.status = "ERROR"
                conn.health = "DOWN"
                conn.last_checked_at = datetime.now(timezone.utc)
                conn.error_logs = json.dumps({"error": message})
            
            db.commit()
            return {"status": "success" if is_connected else "error", "message": message}


        # Add Telegram User Test Logic
        elif provider_normalized in ["TELEGRAMUSER", "TELEGRAM_USER"]:
            try:
                # Check for session string or minimal credentials
                session_string = config.get("session_string")
                api_id = config.get("api_id")
                api_hash = config.get("api_hash")
                phone = config.get("phone")

                if session_string:
                    # If we have a session string, we assume it's valid for now 
                    # (Full verification requires async Telethon `connect()` which might be slow or problematic here)
                    # Ideally, we'd try to connect, but for quick UI feedback:
                    is_connected = True
                    message = "Telegram session present"
                    
                    # Optional: specific check if telethon is available
                    try:
                        from telethon.sync import TelegramClient
                        from telethon.sessions import StringSession
                        
                        client = TelegramClient(StringSession(session_string), api_id, api_hash)
                        client.connect()
                        if client.is_user_authorized():
                            me = client.get_me()
                            message = f"Connected as User: {me.first_name} (@{me.username})"
                            is_connected = True
                        else:
                            is_connected = False
                            message = "Session valid but not authorized (re-login needed)"
                        client.disconnect()
                    except ImportError:
                        message = "Telegram session present (Telethon not installed for deep check)"
                    except Exception as e:
                         # Fallback if connection fails but string exists - might be network or old session
                         # We'll mark as error to prompt user to check
                         is_connected = False
                         message = f"Telegram User Connection Error: {str(e)}"
                
                elif api_id and api_hash:
                     # Credentials present but NO session string
                     # Mark as CONNECTED but with a warning, OR DISCONNECTED/ERROR depending on user preference.
                     # User request: "if doest ask [OTP] then say connected" - implies they want to know if it's NOT connected.
                     # Strict check:
                     is_connected = False
                     message = "Disconnected: Login Required (OTP verification needed)"
                else:
                     is_connected = False
                     message = "Missing API ID or Hash"

            except Exception as e:
                message = f"Telegram User Verification Failed: {str(e)}"

            # DB Update for Telegram User
            if is_connected:
                conn.status = "CONNECTED"
                conn.health = "HEALTHY"
                conn.last_checked_at = datetime.now(timezone.utc)
                conn.last_success_at = datetime.now(timezone.utc)
                conn.error_logs = None
            else:
                conn.status = "ERROR"
                conn.health = "DOWN"
                conn.last_checked_at = datetime.now(timezone.utc)
                conn.error_logs = json.dumps({"error": message})
            
            db.commit()
            return {"status": "success" if is_connected else "error", "message": message}
        
        elif provider in ["sqlite", "duckdb", "duckdb_sqlalchemy"]:
            path = config.get("path") or config.get("database") or config.get("filename")
            if not path:
                # Try to use name as path if it looks like a file
                if conn.name.endswith(".db") or conn.name.endswith(".duckdb"):
                     path = conn.name
                else:
                     raise Exception("Database path not specified in connection details")
            
            # Handle relative paths (relative to backend root or data dir)
            import os
            from app.core.config import settings
            
            # If path is just a filename, look in data dir
            if not os.path.isabs(path):
                # Try data dir first (preferred)
                data_path = os.path.join(settings.DATA_DIR, path)
                if os.path.exists(data_path):
                    path = data_path
                else:
                    # Try current working directory
                    cwd_path = os.path.abspath(path)
                    # If file doesn't exist, we might be creating it, but for test we generally expect existence
                    # unless it's a new DB. Let's assume for test validity we want to check if we CAN connect/create.
                    path = cwd_path

            # Verify connection
            if provider == "sqlite":
                import sqlite3
                try:
                    # Connect and run simple query
                    connection = sqlite3.connect(path)
                    cursor = connection.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    connection.close()
                    is_connected = True
                    message = f"Successfully connected to SQLite database at {os.path.basename(path)}"
                except Exception as e:
                    raise Exception(f"SQLite connection failed: {str(e)}")
                    
            elif provider in ["duckdb", "duckdb_sqlalchemy"]:
                import duckdb
                try:
                    # Connect and run simple query
                    connection = duckdb.connect(path, config={'allow_unsigned_extensions': True})
                    connection.execute("SELECT 1")
                    connection.close()
                    is_connected = True
                    message = f"Successfully connected to DuckDB database at {os.path.basename(path)}"
                except Exception as e:
                    raise Exception(f"DuckDB connection failed: {str(e)}")
        
        elif provider == "postgresql":
            # Handle Postgres
            host = config.get("host", "localhost")
            port = config.get("port", 5432)
            user = config.get("username") or config.get("user")
            password = config.get("password")
            database = config.get("database") or config.get("dbname")
            
            if not all([host, user, database]):
                raise Exception("Missing required PostgreSQL parameters (host, user, database)")
                
            from sqlalchemy import create_engine, text
            url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
            try:
                engine = create_engine(url)
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                is_connected = True
                message = f"Successfully connected to PostgreSQL database {database} on {host}"
            except Exception as e:
                raise Exception(f"PostgreSQL connection failed: {str(e)}")
                
        else:
            # Fallback mock for unknown providers (but log it)
            # Or better, fail for unknown providers to avoid false positives
            raise Exception(f"Provider '{provider}' not supported for automatic testing yet")
            
        # Update status on success
        conn.status = ConnectionStatus.CONNECTED
        conn.health = ConnectionHealth.HEALTHY
        conn.last_checked_at = datetime.utcnow()
        conn.last_success_at = datetime.utcnow()
        conn.error_logs = None
        db.commit()
        return {"status": "success", "message": message}
        
    except Exception as e:
        # Update status on failure
        error_msg = str(e)
        conn.status = ConnectionStatus.ERROR
        conn.health = ConnectionHealth.DOWN
        conn.last_checked_at = datetime.utcnow()
        conn.error_logs = f"Connection test failed at {datetime.utcnow()}: {error_msg}"
        db.commit()
        return {"status": "error", "message": error_msg}

@router.post("/{id}/token/generate")
async def generate_token(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Generate or refresh TrueData token for a connection"""
    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Check if this is a TrueData connection (normalize provider name)
    provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
    if provider_normalized != "TRUEDATA":
        logger.error(f"Token generation attempted for non-TrueData connection {id}: provider={conn.provider}")
        raise HTTPException(status_code=400, detail=f"Token generation only available for TrueData connections. Current provider: {conn.provider}")
    
    # Check if connection is enabled
    if not conn.is_enabled:
        logger.error(f"Token generation attempted for disabled connection {id}")
        raise HTTPException(status_code=400, detail="Connection must be enabled to generate token")
    
    # Decrypt credentials
    config = {}
    if not conn.credentials:
        logger.error(f"No credentials found for connection {id}")
        raise HTTPException(status_code=400, detail="Connection credentials not found. Please configure the connection with username and password.")
    
    try:
        decrypted_json = decrypt_data(conn.credentials)
        config = json.loads(decrypted_json)
        logger.info(f"Successfully decrypted credentials for connection {id}")
        logger.info(f"Decrypted config keys: {list(config.keys())}")
        logger.info(f"Config content (masked): { {k: ('***' if k in ['password', 'api_secret'] else (str(v)[:20] + '...' if v and len(str(v)) > 20 else v)) for k, v in config.items()} }")
    except Exception as e:
        logger.error(f"Failed to decrypt credentials for connection {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to decrypt credentials: {str(e)}")
    
    username = config.get("username")
    password = config.get("password")
    auth_url = config.get("auth_url", settings.TRUEDATA_DEFAULT_AUTH_URL)
    
    # Handle case where username/password might be stored as empty strings or None
    if username:
        username = str(username).strip() if username else None
    if password:
        password = str(password).strip() if password else None
    
    logger.info(f"Extracted credentials - username: {('present (length: ' + str(len(username)) + ')' if username else 'MISSING')}, password: {('present (length: ' + str(len(password)) + ')' if password else 'MISSING')}, auth_url: {auth_url}")
    
    if not username or not username.strip():
        logger.error(f"Username missing or empty for connection {id}")
        logger.error(f"Config keys available: {list(config.keys())}")
        logger.error(f"Config values (masked): { {k: ('***' if k in ['password', 'api_secret'] else (repr(v) if v else 'None')) for k, v in config.items()} }")
        logger.error(f"Raw username value: {repr(config.get('username'))}")
        logger.error(f"Raw password value: {repr('***' if config.get('password') else None)}")
        raise HTTPException(status_code=400, detail="Username is required for token generation. Please configure the connection with a valid username. Go to Configure and enter your TrueData username and password.")
    
    if not password or not password.strip():
        logger.error(f"Password missing or empty for connection {id}")
        raise HTTPException(status_code=400, detail="Password is required for token generation. Please configure the connection with a valid password.")
    
    logger.info(f"Attempting to generate token for connection {id}")
    logger.info(f"  - Auth URL: {auth_url}")
    logger.info(f"  - Username: {username[:3]}*** (length: {len(username)})")
    logger.info(f"  - Password: {'*' * len(password)} (length: {len(password)})")
    logger.info(f"  - Connection enabled: {conn.is_enabled}")
    
    try:
        from app.services.token_service import get_token_service
        token_service = get_token_service()
        
        logger.info(f"Calling token_service.generate_token for connection {id}")
        token_data = token_service.generate_token(
            connection_id=id,
            username=username.strip(),
            password=password.strip(),
            auth_url=auth_url
        )
        logger.info(f"Token service returned: expires_at={token_data.get('expires_at')}, expires_in={token_data.get('expires_in')}")
        
        # Update connection status
        conn.status = ConnectionStatus.CONNECTED
        conn.health = ConnectionHealth.HEALTHY
        conn.last_checked_at = datetime.utcnow()
        conn.last_success_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Token generated successfully for connection {id}")
        
        log_audit_event(
            db, current_user.id, "GENERATE_TOKEN", "connections", str(id),
            None, {"provider": "TRUEDATA"}
        )
        
        return {
            "message": "Token generated successfully",
            "status": "ACTIVE",
            "expires_at": token_data["expires_at"]
        }
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP error from TrueData API: {e.response.status_code if hasattr(e, 'response') else 'Unknown'}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {e.response.text[:200]}"
        logger.error(f"Token generation HTTP error for connection {id}: {error_msg}", exc_info=True)
        conn.status = ConnectionStatus.ERROR
        conn.health = ConnectionHealth.DOWN
        conn.last_checked_at = datetime.utcnow()
        conn.error_logs = f"Token generation failed at {datetime.utcnow()}: {error_msg}"
        db.commit()
        raise HTTPException(status_code=400, detail=f"Token generation failed: {error_msg}")
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error connecting to TrueData API: {str(e)}"
        logger.error(f"Token generation network error for connection {id}: {error_msg}", exc_info=True)
        conn.status = ConnectionStatus.ERROR
        conn.health = ConnectionHealth.DOWN
        conn.last_checked_at = datetime.utcnow()
        conn.error_logs = f"Token generation failed at {datetime.utcnow()}: {error_msg}"
        db.commit()
        raise HTTPException(status_code=400, detail=f"Token generation failed: {error_msg}")
    except ValueError as e:
        error_msg = f"Invalid response from TrueData API: {str(e)}"
        logger.error(f"Token generation validation error for connection {id}: {error_msg}", exc_info=True)
        conn.status = ConnectionStatus.ERROR
        conn.health = ConnectionHealth.DOWN
        conn.last_checked_at = datetime.utcnow()
        conn.error_logs = f"Token generation failed at {datetime.utcnow()}: {error_msg}"
        db.commit()
        raise HTTPException(status_code=400, detail=f"Token generation failed: {error_msg}")
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Token generation failed for connection {id}: {error_msg}", exc_info=True)
        conn.status = ConnectionStatus.ERROR
        conn.health = ConnectionHealth.DOWN
        conn.last_checked_at = datetime.utcnow()
        conn.error_logs = f"Token generation failed at {datetime.utcnow()}: {error_msg}"
        db.commit()
        raise HTTPException(status_code=400, detail=f"Token generation failed: {error_msg}")

@router.get("/{id}/debug")
async def debug_connection(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Debug endpoint to check connection credentials (for troubleshooting)"""
    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    debug_info = {
        "connection_id": id,
        "name": conn.name,
        "provider": conn.provider,
        "is_enabled": conn.is_enabled,
        "has_credentials": conn.credentials is not None,
        "credentials_length": len(conn.credentials) if conn.credentials else 0
    }
    
    # Try to decrypt and show structure (masked)
    if conn.credentials:
        try:
            decrypted_json = decrypt_data(conn.credentials)
            config = json.loads(decrypted_json)
            debug_info["decrypted_keys"] = list(config.keys())
            debug_info["config_structure"] = {
                k: ("***MASKED***" if k in ["password", "api_secret"] else 
                    ("present" if v else "empty/None") if k in ["username", "api_key"] else 
                    str(v)[:50] if v else None)
                for k, v in config.items()
            }
            debug_info["username_present"] = bool(config.get("username"))
            debug_info["password_present"] = bool(config.get("password"))
            debug_info["username_length"] = len(str(config.get("username", ""))) if config.get("username") else 0
        except Exception as e:
            debug_info["decrypt_error"] = str(e)
    
    return debug_info

@router.get("/{id}/token/status")
async def get_token_status(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get token status for a TrueData connection - STANDARDIZED"""
    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Check if this is a TrueData connection (normalize provider name)
    provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
    if provider_normalized != "TRUEDATA":
        raise HTTPException(status_code=400, detail="Token status only available for TrueData connections")
    
    try:
        from app.services.token_service import get_token_service
        token_service = get_token_service()
        
        try:
            token_status = token_service.get_token_status(connection_id=id)
            
            # Return authoritative response - backend owns all expiry logic
            return {
                "connection_id": token_status["connection_id"],
                "token_status": token_status["token_status"],  # ACTIVE | EXPIRED | NOT_GENERATED | ERROR
                "expires_at": token_status["expires_at"],  # IST format (authoritative)
                "expires_at_utc": token_status.get("expires_at_utc"),  # UTC for reference
                "expires_at_ist": token_status.get("expires_at_ist"),  # IST (same as expires_at)
                "last_refreshed_at": token_status["last_refreshed_at"],
                "seconds_left": token_status["seconds_left"],  # Authoritative - frontend uses this ONLY
                "next_auto_refresh_at": token_status.get("next_auto_refresh_at")  # Next 4:00 AM IST when token will auto-refresh
            }
        except Exception as token_error:
            error_msg = str(token_error)
            # SQL schema errors should return 500, not 400
            if "schema" in error_msg.lower() or "column" in error_msg.lower() or "binder" in error_msg.lower():
                logger.error(f"SQL schema error getting token status for connection {id}: {token_error}", exc_info=True)
                logger.error(f"SQL query and bindings: connection_id={id}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Database schema error: {error_msg}. Please check the tokens table schema."
                )
            logger.error(f"Error getting token status for connection {id}: {token_error}", exc_info=True)
            logger.error(f"SQL query and bindings: connection_id={id}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get token status: {error_msg}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get token status for connection {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get token status: {str(e)}")

@router.post("/{id}/token/refresh")
async def refresh_token(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Refresh TrueData token - always generates a new token (force refresh)
    
    This endpoint always generates a new token regardless of current token status.
    Used for manual refresh operations.
    """
    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Check if this is a TrueData connection (normalize provider name)
    provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
    if provider_normalized != "TRUEDATA":
        raise HTTPException(status_code=400, detail="Token refresh only available for TrueData connections")
    
    if not conn.is_enabled:
        raise HTTPException(status_code=400, detail="Connection must be enabled to refresh token")
    
    # Decrypt credentials
    config = {}
    if not conn.credentials:
        raise HTTPException(status_code=400, detail="Connection credentials not found. Please configure the connection with username and password.")
    
    try:
        decrypted_json = decrypt_data(conn.credentials)
        config = json.loads(decrypted_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decrypt credentials: {str(e)}")
    
    username = config.get("username")
    password = config.get("password")
    auth_url = config.get("auth_url", settings.TRUEDATA_DEFAULT_AUTH_URL)
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required for token refresh")
    
    try:
        from app.services.token_service import get_token_service
        token_service = get_token_service()
        
        # ALWAYS generate a new token (force refresh)
        # This is a manual refresh operation, so we always create a new token
        token_data = token_service.generate_token(
            connection_id=id,
            username=username.strip(),
            password=password.strip(),
            auth_url=auth_url
        )
        
        # Update connection status
        conn.status = ConnectionStatus.CONNECTED
        conn.health = ConnectionHealth.HEALTHY
        conn.last_checked_at = datetime.utcnow()
        conn.last_success_at = datetime.utcnow()
        db.commit()
        
        # Get updated token status (includes IST-formatted expires_at)
        token_status = token_service.get_token_status(connection_id=id)
        
        log_audit_event(
            db, current_user.id, "REFRESH_TOKEN", "connections", str(id),
            None, {"provider": "TRUEDATA"}
        )
        
        return {
            "status": "success",
            "refreshed": True,
            "message": "Token refreshed successfully",
            "token_status": token_status,
            "expires_at": token_status["expires_at"]  # IST format (authoritative)
        }
    except Exception as e:
        logger.error(f"Token refresh failed for connection {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")

@router.get("/truedata/token")
async def get_truedata_token(
    connection_id: Optional[int] = Query(None, description="Connection ID for TrueData connection"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Get TrueData token for use by other connections (token only, no metadata)"""
    try:
        # If connection_id not provided, find first enabled TrueData connection
        if not connection_id:
            truedata_conn = db.query(Connection).filter(
                Connection.provider.ilike('TRUEDATA'),
                Connection.is_enabled == True
            ).first()
            if not truedata_conn:
                raise HTTPException(status_code=404, detail="No enabled TrueData connection found")
            connection_id = truedata_conn.id
        
        from app.services.token_service import get_token_service
        token_service = get_token_service()
        
        token = token_service.get_token(connection_id=connection_id)
        
        if not token:
            raise HTTPException(status_code=404, detail="No active TrueData token found")
        
        return {
            "access_token": token,
            "token_type": "Bearer"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get token: {str(e)}")

@router.get("/{id}/truedata/symbols")
async def get_truedata_symbols(
    id: int,
    segment: str = Query("eq", description="Market segment: 'eq' (NSE) or 'bseeq' (BSE)"),
    format: str = Query("json", description="Response format: 'json' or 'csv'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Get all symbols from TrueData Symbol Master API
    
    This API uses QUERY PARAMETER authentication (NOT Bearer token).
    Username and password are passed as query parameters.
    """
    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Check if this is a TrueData connection
    provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
    if provider_normalized != "TRUEDATA":
        raise HTTPException(status_code=400, detail="Symbol API only available for TrueData connections")
    
    if not conn.is_enabled:
        raise HTTPException(status_code=400, detail="Connection must be enabled")
    
    try:
        from app.services.truedata_api_service import get_truedata_api_service
        api_service = get_truedata_api_service(id, db)
        
        result = api_service.get_all_symbols(
            segment=segment,
            response_format=format
        )
        
        if format.lower() == "csv":
            from fastapi.responses import Response
            return Response(
                content=result,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=truedata_symbols_{segment}.csv"}
            )
        else:
            return {
                "status": "success",
                "segment": segment,
                "format": format,
                "data": result
            }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except requests.exceptions.HTTPError as e:
        error_msg = f"TrueData API error: {e.response.status_code if hasattr(e, 'response') else 'Unknown'}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {e.response.text[:200]}"
        logger.error(f"Error fetching symbols for connection {id}: {error_msg}", exc_info=True)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"Error fetching symbols for connection {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch symbols: {str(e)}")

@router.get("/{id}/truedata/corporate/{endpoint}")
async def call_truedata_corporate_api(
    id: int,
    endpoint: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
    **query_params
):
    """
    Call TrueData Corporate API with Bearer token authentication
    
    Endpoints:
    - getCorpAction
    - getCorpActionRange
    - getSymbolClassification
    - getCompanyLogo
    - getMarketCap
    - getCorporateInfo
    """
    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Check if this is a TrueData connection
    provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
    if provider_normalized != "TRUEDATA":
        raise HTTPException(status_code=400, detail="Corporate API only available for TrueData connections")
    
    if not conn.is_enabled:
        raise HTTPException(status_code=400, detail="Connection must be enabled")
    
    try:
        from app.services.truedata_api_service import get_truedata_api_service
        api_service = get_truedata_api_service(id, db)
        
        result = api_service.call_corporate_api(
            endpoint=endpoint,
            method="GET",
            params=query_params
        )
        
        return {
            "status": "success",
            "endpoint": endpoint,
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except requests.exceptions.HTTPError as e:
        error_msg = f"TrueData API error: {e.response.status_code if hasattr(e, 'response') else 'Unknown'}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {e.response.text[:200]}"
        logger.error(f"Error calling Corporate API {endpoint} for connection {id}: {error_msg}", exc_info=True)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"Error calling Corporate API {endpoint} for connection {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to call API: {str(e)}")

@router.post("/{id}/toggle", response_model=ConnectionResponse)
async def toggle_connection(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Toggle connection enabled/disabled status
    """
    conn = db.query(Connection).filter(Connection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Toggle status
    conn.is_enabled = not conn.is_enabled
    
    # Log audit event
    action = "ENABLE_CONNECTION" if conn.is_enabled else "DISABLE_CONNECTION"
    log_audit_event(
        db, 
        current_user.id, 
        action, 
        "connections", 
        str(conn.id), 
        None, 
        {"name": conn.name, "new_status": conn.is_enabled}
    )
    
    db.commit()
    
    # Auto-verify if enabled (only for DB connections)
    if conn.is_enabled:
        try:
            # Re-test connection to ensure validity
            # We call the existing test_connection endpoint logic
            await test_connection(id, db, current_user)
        except Exception as e:
            logger.error(f"Auto-verification failed for connection {id}: {e}")
            # We don't fail the toggle, but the status will be updated by test_connection
            
    db.refresh(conn)
    
    return create_connection_response(conn)


def create_connection_response(conn: Connection) -> ConnectionResponse:
    """Helper to create ConnectionResponse from Connection model"""
    # Extract URL and port from credentials for TrueData connections
    url = None
    port = None
    provider_normalized = conn.provider.upper().replace(" ", "").replace("_", "").replace("-", "") if conn.provider else ""
    
    if provider_normalized == "TRUEDATA" and conn.credentials:
        try:
            decrypted_json = decrypt_data(conn.credentials)
            config = json.loads(decrypted_json)
            url = config.get("auth_url", settings.TRUEDATA_DEFAULT_AUTH_URL)
            port = config.get("websocket_port", settings.TRUEDATA_DEFAULT_WEBSOCKET_PORT)
        except Exception as e:
            # logger.debug(f"Could not extract URL/port: {e}")
            url = settings.TRUEDATA_DEFAULT_AUTH_URL
            port = settings.TRUEDATA_DEFAULT_WEBSOCKET_PORT
            
    conn_dict = {
        'id': conn.id,
        'name': conn.name,
        'connection_type': conn.connection_type,
        'provider': conn.provider,
        'description': conn.description,
        'environment': conn.environment if conn.environment is not None else "PROD",
        'status': conn.status if conn.status is not None else "DISCONNECTED",
        'health': conn.health if conn.health is not None else "HEALTHY",
        'is_enabled': conn.is_enabled if conn.is_enabled is not None else False,
        'last_checked_at': conn.last_checked_at,
        'last_success_at': conn.last_success_at,
        'created_at': conn.created_at if conn.created_at is not None else datetime.now(timezone.utc),
        'updated_at': conn.updated_at,
        'url': url,
        'port': port
    }
    
    return ConnectionResponse.model_validate(conn_dict)


@router.get("/ai/models")
async def get_ai_models(
    provider: str,
    base_url: Optional[str] = None,
    current_user: User = Depends(get_admin_user)
):
    """Fetch available models for a given provider."""
    provider = provider.lower()
    models = []
    
    if "ollama" in provider:
        if not base_url:
             # Try to find a default or require it? 
             # For now return empty or error.
             return {"models": []}
        
        try:
            # Clean base_url - ensure no trailing slash
            base_url = base_url.rstrip("/")
            # Also ensure it has http/https
            if not base_url.startswith("http"):
                base_url = "http://" + base_url
                
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [model['name'] for model in data.get('models', [])]
        except Exception as e:
            logger.error(f"Error fetching Ollama models: {e}")
            pass
            
    elif "gemini" in provider:
        models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro"]
        
    elif "perplexity" in provider:
        models = [
            "llama-3.1-sonar-small-128k-online", 
            "llama-3.1-sonar-large-128k-online", 
            "llama-3.1-sonar-huge-128k-online",
            "llama-3.1-sonar-small-128k-chat", 
            "llama-3.1-sonar-large-128k-chat"
        ]
        
    return {"models": models}
