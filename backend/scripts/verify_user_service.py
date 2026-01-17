import sys
import os
import asyncio
from datetime import datetime

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_router
from app.core.config import settings
from app.services.user_service import UserService
from app.models.user import User
from app.schemas.user import UserUpdate, PasswordChange
from fastapi import BackgroundTasks
import uuid

async def verify_service():
    print("Verifying UserService...")
    
    # Get DB session
    router = get_db_router(settings.DATA_DIR)
    auth_client = router.get_auth_db()
    if not auth_client:
        print("Failed to get auth DB client")
        return
        
    db = auth_client.get_session()
    service = UserService(db)
    
    try:
        # Create dummy user (using repo directly for setup)
        from app.repositories.user_repository import UserRepository
        repo = UserRepository()
        unique_id = str(uuid.uuid4())[:8]
        user = User(
            user_id=str(uuid.uuid4()),
            username=f"svc_test_{unique_id}",
            email=f"svc_{unique_id}@example.com",
            mobile=f"666{unique_id}",
            hashed_password="hashed_secret",
            role="user"
        )
        repo.create(db, user)
        print(f"Created setup user: {user.username}")
        
        # Test update_last_active
        print("Testing update_last_active...")
        updated_user = service.update_last_active(user)
        assert updated_user.last_active_at is not None
        print("update_last_active: OK")
        
        # Test update_profile (non-sensitive)
        print("Testing update_profile (non-sensitive)...")
        new_name = "Service Updated Name"
        update_data = UserUpdate(name=new_name)
        updated_user = await service.update_profile(user, update_data)
        assert updated_user.name == new_name
        print("update_profile: OK")
        
        # Test create_feedback
        print("Testing create_feedback...")
        feedback = service.create_feedback(user, "Test Subject", "Test Message")
        assert feedback.id is not None
        assert feedback.subject == "Test Subject"
        print("create_feedback: OK")
        
        # Note: Testing sensitive changes or features with background tasks is harder in a script 
        # without full async context for BackgroundTasks, but we can verify basic logic.
        
        # Cleanup
        db.delete(feedback)
        db.delete(user)
        db.commit()
        print("Cleanup: OK")
        
        print("UserService Verification PASSED")
        
    except Exception as e:
        print(f"UserService Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_service())
