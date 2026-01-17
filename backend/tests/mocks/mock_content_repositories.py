from typing import List, Dict, Optional, Any

class MockTelegramRepository:
    def __init__(self):
        self.channels = {}
        self.listeners = {}

    def get_channel_by_username(self, db, username: str):
        for c in self.channels.values():
            if c['username'] == username: return c
        return None

    def register_channel(self, db, channel_data: dict):
        cid = len(self.channels) + 1
        channel_data['id'] = cid
        self.channels[cid] = channel_data
        return channel_data

    def get_registered_channels(self, db):
        return list(self.channels.values())

    # Add other methods as needed by service logic
    def get_channel_stats(self, db, channel_id):
        return {'msg_count': 0}

class MockNewsRepository:
    def __init__(self):
        self.news = []

    def get_news(self, conn, limit=10, offset=0):
        return self.news[offset:offset+limit], len(self.news)
    
    def insert_news(self, conn, news_item):
        self.news.append(news_item)
        return True

    def get_db_connection(self):
        # Similar dummy connection pattern if needed
        class DummyConn:
            def close(self): pass
        return DummyConn()
    
