from sqlalchemy.orm import Session
from app.models.feature_request import FeatureRequest
from typing import Optional, List

class FeatureRequestRepository:
    def create(self, db: Session, feature_request: FeatureRequest) -> FeatureRequest:
        db.add(feature_request)
        db.commit()
        db.refresh(feature_request)
        return feature_request
        
    def get_by_id(self, db: Session, request_id: int) -> Optional[FeatureRequest]:
        return db.query(FeatureRequest).filter(FeatureRequest.id == request_id).first()

    def get_by_user(self, db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[FeatureRequest]:
         return db.query(FeatureRequest).filter(FeatureRequest.user_id == user_id).order_by(FeatureRequest.created_at.desc()).offset(skip).limit(limit).all()

    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[FeatureRequest]:
         return db.query(FeatureRequest).order_by(FeatureRequest.created_at.desc()).offset(skip).limit(limit).all()
    
    def update(self, db: Session, feature_request: FeatureRequest) -> FeatureRequest:
        db.commit()
        db.refresh(feature_request)
        return feature_request
