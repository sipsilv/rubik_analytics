from typing import List, Optional
from app.models.access_request import AccessRequest
from app.models.feedback import Feedback
from app.models.feature_request import FeatureRequest

class MockAccessRequestRepository:
    def __init__(self):
        self.requests = {}
        self.next_id = 1

    def get_all(self, db, skip=0, limit=100) -> List[AccessRequest]:
        return list(self.requests.values())[skip:skip+limit]

    def get_pending(self, db) -> List[AccessRequest]:
        return [r for r in self.requests.values() if r.status == "PENDING"]

    def get_by_id(self, db, request_id: int) -> Optional[AccessRequest]:
        return self.requests.get(request_id)

    def get_by_user_id(self, db, user_id: int) -> List[AccessRequest]:
        return [r for r in self.requests.values() if r.user_id == user_id]

    def create(self, db, request: AccessRequest) -> AccessRequest:
        request.id = self.next_id
        if not request.status:
             request.status = "PENDING"
        self.requests[self.next_id] = request
        self.next_id += 1
        return request

    def update(self, db, request: AccessRequest) -> AccessRequest:
        self.requests[request.id] = request
        return request

    def delete(self, db, request_id: int) -> bool:
        if request_id in self.requests:
            del self.requests[request_id]
            return True
        return False

class MockFeedbackRepository:
    def __init__(self):
        self.items = {}
        self.next_id = 1

    def create(self, db, feedback: Feedback) -> Feedback:
        feedback.id = self.next_id
        self.items[self.next_id] = feedback
        self.next_id += 1
        return feedback

    def get_by_user(self, db, user_id, skip=0, limit=100) -> List[Feedback]:
        return [f for f in self.items.values() if f.user_id == user_id][skip:skip+limit]

    def get_all(self, db, skip=0, limit=100) -> List[Feedback]:
        return list(self.items.values())[skip:skip+limit]

class MockFeatureRequestRepository:
    def __init__(self):
        self.items = {}
        self.next_id = 1

    def create(self, db, feature_request: FeatureRequest) -> FeatureRequest:
        feature_request.id = self.next_id
        self.items[self.next_id] = feature_request
        self.next_id += 1
        return feature_request

    def get_by_id(self, db, request_id: int) -> Optional[FeatureRequest]:
        return self.items.get(request_id)

    def get_by_user(self, db, user_id, skip=0, limit=100) -> List[FeatureRequest]:
        return [f for f in self.items.values() if f.user_id == user_id][skip:skip+limit]

    def get_all(self, db, skip=0, limit=100) -> List[FeatureRequest]:
        return list(self.items.values())[skip:skip+limit]

    def update(self, db, feature_request: FeatureRequest) -> FeatureRequest:
        self.items[feature_request.id] = feature_request
        return feature_request
