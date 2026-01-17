import sys
import os
# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_router
from app.core.config import settings
from app.repositories.user_repository import UserRepository
from app.models.user import User
import uuid

def verify_repo():
    print("Verifying UserRepository...")
    
    # Get DB session
    router = get_db_router(settings.DATA_DIR)
    auth_client = router.get_auth_db()
    if not auth_client:
        print("Failed to get auth DB client")
        return
        
    db = auth_client.get_session()
    repo = UserRepository()
    
    try:
        # Create dummy user
        unique_id = str(uuid.uuid4())[:8]
        user = User(
            user_id=str(uuid.uuid4()),
            username=f"test_user_{unique_id}",
            email=f"test_{unique_id}@example.com",
            mobile=f"555{unique_id}",
            hashed_password="hashed_secret",
            role="user"
        )
        
        print(f"Creating user: {user.username}")
        created_user = repo.create(db, user)
        print(f"User created with ID: {created_user.id}")
        
        # Get by ID
        fetched_user = repo.get_by_id(db, created_user.id)
        assert fetched_user is not None
        assert fetched_user.username == user.username
        print("Get by ID: OK")
        
        # Get by Email
        fetched_email = repo.get_by_email(db, user.email)
        assert fetched_email is not None
        assert fetched_email.id == user.id
        print("Get by Email: OK")
        
        # Update
        created_user.name = "Updated Name"
        updated_user = repo.update(db, created_user)
        assert updated_user.name == "Updated Name"
        print("Update: OK")
        
        # Cleanup (optional, or just leave it)
        db.delete(created_user)
        db.commit()
        print("Cleanup: OK")
        
        print("UserRepository Verification PASSED")
        
    except Exception as e:
        print(f"UserRepository Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verify_repo()
