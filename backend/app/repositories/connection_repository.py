from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.connection import Connection

class ConnectionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, category: Optional[str] = None) -> List[Connection]:
        query = self.db.query(Connection)
        if category:
            query = query.filter(Connection.connection_type == category)
        return query.all()

    def get_by_id(self, id: int) -> Optional[Connection]:
        return self.db.query(Connection).filter(Connection.id == id).first()

    def get_by_name(self, name: str) -> Optional[Connection]:
        return self.db.query(Connection).filter(Connection.name == name).first()
        
    def get_existing_by_name_insensitive(self, name: str) -> Optional[Connection]:
        # SQLite case-insensitive check
        all_connections = self.db.query(Connection).all()
        normalized_name = name.strip().lower()
        for conn in all_connections:
            if conn.name.strip().lower() == normalized_name:
                return conn
        return None

    def create(self, connection: Connection) -> Connection:
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def update(self, connection: Connection) -> Connection:
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def delete(self, connection: Connection):
        self.db.delete(connection)
        self.db.commit()
