from typing import Optional, List
from app.models.user import User
from app.repositories.user_repository import UserRepository

class MockUserRepository(UserRepository):
    def __init__(self):
        self.users = {}
        self.next_id = 1

    def get_by_email(self, email: str) -> Optional[User]:
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.users.get(user_id)

    def create(self, user_data: dict) -> User:
        user = User(**user_data)
        user.id = self.next_id
        self.users[self.next_id] = user
        self.next_id += 1
        return user

    def update(self, user: User) -> User:
        self.users[user.id] = user
        return user

    def delete(self, user: User) -> None:
        if user.id in self.users:
            del self.users[user.id]

    def get_all(self, skip: int = 0, limit: int = 100) -> List[User]:
        return list(self.users.values())[skip : skip + limit]

    def count(self) -> int:
        return len(self.users)
