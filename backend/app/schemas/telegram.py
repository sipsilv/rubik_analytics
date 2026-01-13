from pydantic import BaseModel
from typing import Optional

class OTPRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str

class OTPRequestResponse(BaseModel):
    phone_code_hash: str
    session_string: str
    message: str

class OTPVerify(BaseModel):
    api_id: int
    api_hash: str
    phone: str
    code: str
    phone_code_hash: str
    session_string: str
    password: Optional[str] = None

class OTPVerifyResponse(BaseModel):
    session_string: str
    message: str
