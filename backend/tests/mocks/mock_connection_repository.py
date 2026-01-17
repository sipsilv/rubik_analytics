from typing import List, Optional
from app.models.connection import Connection

class MockConnectionRepository:
    def __init__(self):
        self.connections = {}
        self.next_id = 1

    def get_all(self, db, skip=0, limit=100) -> List[Connection]:
        return list(self.connections.values())[skip:skip+limit]

    def get_by_id(self, db, connection_id: int) -> Optional[Connection]:
        return self.connections.get(connection_id)

    def create(self, db, connection: Connection) -> Connection:
        connection.id = self.next_id
        if connection.is_enabled is None:
            connection.is_enabled = True
        self.connections[self.next_id] = connection
        self.next_id += 1
        return connection

    def update(self, db, connection: Connection) -> Connection:
        self.connections[connection.id] = connection
        return connection

    def delete(self, db, connection_id: int) -> bool:
        if connection_id in self.connections:
            del self.connections[connection_id]
            return True
        return False
