from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from app.core.config import settings

# Bcrypt configuration - using 12 rounds for better security (default is 10)
BCRYPT_ROUNDS = 12

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a bcrypt hash.
    Handles both new bcrypt hashes and old passlib-style hashes for backward compatibility.
    """
    try:
        # Direct bcrypt verification
        # If hash is already a bytes object, use it directly; otherwise decode it
        if isinstance(hashed_password, bytes):
            hash_bytes = hashed_password
        else:
            hash_bytes = hashed_password.encode('utf-8')
        
        # Convert plain password to bytes
        password_bytes = plain_password.encode('utf-8')
        
        # Use bcrypt to verify
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        print(f"[SECURITY] Password verification error: {e}")
        return False

def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    Returns the hash as a string for database storage.
    """
    try:
        # Convert password to bytes
        password_bytes = password.encode('utf-8')
        
        # Generate salt and hash the password
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password_bytes, salt)
        
        # Return as string for database storage
        return hashed.decode('utf-8')
    except Exception as e:
        print(f"[SECURITY] Password hashing error: {e}")
        raise

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None, is_system: bool = False) -> str:
    """Create JWT access token for users or system services"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    # Use different secret for system tokens
    secret_key = settings.JWT_SYSTEM_SECRET_KEY if is_system else settings.JWT_SECRET_KEY
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str, is_system: bool = False) -> Optional[dict]:
    """Decode JWT access token - tries both user and system secrets"""
    try:
        # Try user secret first
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        # Log the specific error for debugging
        print(f"[SECURITY] Token decode failed: {e}")
        try:
            # Try system secret
            payload = jwt.decode(token, settings.JWT_SYSTEM_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except JWTError as e2:
            print(f"[SECURITY] System token decode also failed: {e2}")
            return None

def create_system_token(service_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT token for system/service-to-service communication"""
    data = {
        "sub": service_id,
        "role": "system",
        "type": "system"
    }
    if expires_delta is None:
        expires_delta = timedelta(hours=24)  # System tokens last 24 hours
    return create_access_token(data, expires_delta=expires_delta, is_system=True)

def validate_system_token(token: str) -> bool:
    """Validate that token is a system token"""
    payload = decode_access_token(token, is_system=True)
    if payload and payload.get("role") == "system" and payload.get("type") == "system":
        return True
    return False
from cryptography.fernet import Fernet

def get_fernet() -> Fernet:
    """Get Fernet instance with key from settings"""
    try:
        return Fernet(settings.ENCRYPTION_KEY.encode())
    except Exception as e:
        print(f"[SECURITY] Invalid encryption key: {e}")
        raise ValueError("Invalid encryption key configuration")

def encrypt_data(data: str) -> str:
    """Encrypt string data"""
    if not data:
        return ""
    try:
        f = get_fernet()
        return f.encrypt(data.encode()).decode()
    except Exception as e:
        print(f"[SECURITY] Encryption failed: {e}")
        raise

def decrypt_data(token: str) -> str:
    """Decrypt string data"""
    if not token:
        return ""
    try:
        f = get_fernet()
        return f.decrypt(token.encode()).decode()
    except Exception as e:
        print(f"[SECURITY] Decryption failed: {e}")
        raise
