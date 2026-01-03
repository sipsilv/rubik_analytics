from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.models.user import User
from typing import Optional, Dict, Any
import json

def log_audit_event(
    db: Session,
    user_id: int,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    old_value: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
):
    """
    Helper function to log audit events (backward compatibility wrapper).
    Converts to AuditService.log_action format.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        print(f"[ERROR] Cannot log audit event: User {user_id} not found")
        return
    
    old_value_str = json.dumps(old_value) if old_value else None
    new_value_str = json.dumps(details) if details else None
    
    AuditService.log_action(
        db=db,
        action=action,
        performer=user,
        target_id=str(target_id) if target_id else None,
        target_type=target_type,
        old_value=old_value_str,
        new_value=new_value_str,
        details=details
    )

class AuditService:
    @staticmethod
    def log_action(
        db: Session,
        action: str,
        performer: User,
        target_id: Optional[str] = None,
        target_type: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ):
        """
        Log an audit event to the database.
        """
        try:
            log_entry = AuditLog(
                action=action,
                performer_id=performer.id,
                target_id=target_id,
                target_type=target_type,
                old_value=old_value,
                new_value=new_value,
                details=json.dumps(details) if details else None,
                ip_address=ip_address
            )
            db.add(log_entry)
            db.commit()
            print(f"[AUDIT] {action} by {performer.username} on {target_type}:{target_id}")
        except Exception as e:
            print(f"[ERROR] Failed to write audit log: {e}")
            # Do not rollback main transaction for logging failure, but log it
            # In production, this might fallback to a file log
