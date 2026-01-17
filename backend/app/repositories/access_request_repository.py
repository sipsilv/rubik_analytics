from sqlalchemy.orm import Session
from app.models.access_request import AccessRequest
from typing import List, Optional

class AccessRequestRepository:
    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[AccessRequest]:
        return db.query(AccessRequest).offset(skip).limit(limit).all()

    def get_pending(self, db: Session) -> List[AccessRequest]:
        return db.query(AccessRequest).filter(AccessRequest.status == "PENDING").all()
    
    def get_by_id(self, db: Session, request_id: int) -> Optional[AccessRequest]:
        return db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    
    def get_by_user_id(self, db: Session, user_id: int) -> List[AccessRequest]:
        return db.query(AccessRequest).filter(AccessRequest.user_id == user_id).all()

    def create(self, db: Session, request: AccessRequest) -> AccessRequest:
        db.add(request)
        db.commit()
        db.refresh(request)
        return request
    
    def update(self, db: Session, request: AccessRequest) -> AccessRequest:
        db.commit()
        db.refresh(request)
        return request
    
    def delete(self, db: Session, request_id: int) -> bool:
        request = self.get_by_id(db, request_id)
        if request:
            db.delete(request)
            db.commit()
            return True
        return False
