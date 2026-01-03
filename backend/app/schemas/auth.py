from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional, Any

class LoginRequest(BaseModel):
    # Primary field - required
    identifier: str = Field(..., description="Can be email, mobile, user_id, or username")
    password: str
    
    # Legacy field - will be ignored but accepted for backward compatibility
    username: Optional[str] = Field(None, exclude=True, description="Legacy - use 'identifier' instead")
    
    @model_validator(mode='before')
    @classmethod
    def map_username_field(cls, data: Any) -> Any:
        """
        Map 'username' field to 'identifier' before validation.
        This allows backward compatibility with old clients that send 'username'.
        """
        if isinstance(data, dict):
            # If 'username' is provided but 'identifier' is not, copy it
            if 'username' in data and data.get('username') and 'identifier' not in data:
                data['identifier'] = data['username']
            # Remove username from data to avoid confusion (it's excluded anyway)
            data.pop('username', None)
        return data

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ForgotPasswordResponse(BaseModel):
    message: str
