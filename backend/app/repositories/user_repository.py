from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from typing import Optional, List

class UserRepository:
    def get_by_id(self, db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    def get_by_user_id(self, db: Session, user_id: str) -> Optional[User]:
        return db.query(User).filter(User.user_id == user_id).first()

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    def get_by_mobile(self, db: Session, mobile: str) -> Optional[User]:
        return db.query(User).filter(User.mobile == mobile).first()
    
    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        return db.query(User).filter(User.username == username).first()

    def create(self, db: Session, user: User) -> User:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def update(self, db: Session, user: User) -> User:
        db.commit()
        db.refresh(user)
        return user
        
    def count(self, db: Session) -> int:
        return db.query(User).count()
        
    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[User]:
         return db.query(User).offset(skip).limit(limit).all()
