from fastapi import APIRouter, HTTPException
from app.services.telegram_auth_service import TelegramAuthService
from app.schemas.telegram import OTPRequest, OTPRequestResponse, OTPVerify, OTPVerifyResponse

router = APIRouter()
auth_service = TelegramAuthService()

@router.post("/request-otp", response_model=OTPRequestResponse)
async def request_otp(data: OTPRequest):
    try:
        phone_code_hash, session_string = await auth_service.request_otp(data.api_id, data.api_hash, data.phone)
        return {
            "phone_code_hash": phone_code_hash, 
            "session_string": session_string,
            "message": "OTP sent successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/verify-otp", response_model=OTPVerifyResponse)
async def verify_otp(data: OTPVerify):
    try:
        print(f"Verifying OTP for {data.phone} with hash {data.phone_code_hash}")
        session_string = await auth_service.verify_otp(
            data.api_id, 
            data.api_hash, 
            data.phone, 
            data.code, 
            data.phone_code_hash,
            data.session_string, # Pass the temp session
            data.password
        )
        return {"session_string": session_string, "message": "Verification successful"}
    except Exception as e:
        print(f"VERIFY OTP ERROR: {str(e)}") # Force print to console for debugging
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
