from datetime import datetime, timezone
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from app.models.telegram_channel import TelegramChannel, ChannelStatus

class TelegramRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_channel_by_id(self, channel_id: int) -> Optional[TelegramChannel]:
        return self.db.query(TelegramChannel).filter(TelegramChannel.id == channel_id).first()

    def get_channel_by_telegram_id(self, connection_id: int, telegram_id: int) -> Optional[TelegramChannel]:
        return self.db.query(TelegramChannel).filter(
            TelegramChannel.connection_id == connection_id,
            TelegramChannel.channel_id == telegram_id
        ).first()

    def get_channels_by_connection(self, connection_id: int) -> List[TelegramChannel]:
        return self.db.query(TelegramChannel).filter(
            TelegramChannel.connection_id == connection_id
        ).all()

    def create_channel(self, channel: TelegramChannel) -> TelegramChannel:
        self.db.add(channel)
        self.db.commit()
        self.db.refresh(channel)
        return channel

    def update_channel(self, channel: TelegramChannel) -> TelegramChannel:
        self.db.commit()
        self.db.refresh(channel)
        return channel

    def delete_channel(self, channel: TelegramChannel):
        self.db.delete(channel)
        self.db.commit()

    def get_channel_stats(self, channel_ids: List[int], table_name: str) -> Dict[int, int]:
        """
        Queries DuckDB for message counts for the given channel IDs for the current day (UTC).
        Returns dict: { channel_id_int: count }
        """
        from app.providers.shared_db import get_shared_db
        db = get_shared_db()
        counts = {}
        
        if not channel_ids:
            return counts

        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Use shared DB runner to avoid locks
            query = f"""
                SELECT telegram_chat_id, COUNT(*) 
                FROM {table_name} 
                WHERE received_at >= ?
                GROUP BY telegram_chat_id
            """
            results = db.run_listing_query(query, [today_start], fetch='all')
            
            if results:
                for row in results:
                    chat_id_str = row[0]
                    count = row[1]
                    try:
                        # Normalize: strip -100 prefix and get absolute value to match raw IDs in registration table
                        # Listener stores as "-10012345" or "-975074580"
                        # Registration stores as 12345 or 975074580
                        if str(chat_id_str).startswith("-100"):
                             raw_id_str = str(chat_id_str).replace("-100", "", 1)
                        else:
                             raw_id_str = str(chat_id_str)
                             
                        normalized_id = abs(int(raw_id_str))
                        if normalized_id in channel_ids:
                             counts[normalized_id] = count
                    except Exception as e:
                        print(f"Failed to normalize chat ID {chat_id_str}: {e}")
            
        except Exception as e:
            print(f"Error fetching stats from Shared DB: {e}")
                
        return counts
