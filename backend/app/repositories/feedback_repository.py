from sqlalchemy.orm import Session
from app.models.feedback import Feedback
from typing import Optional, List

class FeedbackRepository:
    def create(self, db: Session, feedback: Feedback) -> Feedback:
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback
        
    def get_by_user(self, db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[Feedback]:
         return db.query(Feedback).filter(Feedback.user_id == user_id).offset(skip).limit(limit).all()

    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[Feedback]:
         return db.query(Feedback).offset(skip).limit(limit).all()
