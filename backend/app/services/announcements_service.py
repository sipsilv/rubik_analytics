"""
Corporate Announcements Service
Handles storage, retrieval, and ingestion of corporate announcements from TrueData
"""
import logging
import csv
import io
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.providers.truedata_api import get_truedata_api_service
from app.repositories.announcements_repository import AnnouncementsRepository

logger = logging.getLogger(__name__)

class AnnouncementsService:
    def __init__(self):
        self.repo = AnnouncementsRepository()

    def insert_announcement(self, announcement: Dict[str, Any]) -> bool:
        return self.repo.insert_announcement(announcement)

    def get_announcements(self, **kwargs) -> tuple[List[Dict[str, Any]], int]:
        return self.repo.get_announcements(**kwargs)

    def get_announcement_by_id(self, announcement_id: str) -> Optional[Dict[str, Any]]:
        return self.repo.get_announcement(announcement_id)

    def store_attachment(self, announcement_id: str, attachment_data: bytes, content_type: str) -> bool:
        # Verify existence
        if not self.repo.get_announcement(announcement_id):
            logger.warning(f"Announcement {announcement_id} not found, cannot store attachment")
            return False
        return self.repo.update_attachment(announcement_id, attachment_data, content_type)

    def get_attachment(self, announcement_id: str) -> Optional[Dict[str, Any]]:
        return self.repo.get_attachment(announcement_id)
    
    def get_descriptor_metadata(self, descriptor_id: int) -> Optional[Dict[str, Any]]:
        return self.repo.get_descriptor_metadata(descriptor_id)

    def get_descriptor_metadata_batch(self, descriptor_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        return self.repo.get_descriptor_metadata_batch(descriptor_ids)
        
    def fetch_descriptors_from_truedata(self, connection_id: int):
        try:
            api_service = get_truedata_api_service(connection_id)
            response = api_service.call_corporate_api("getdescriptors")
            descriptors = response
            if isinstance(response, dict) and "data" in response:
                descriptors = response["data"]
            elif not isinstance(descriptors, list):
                descriptors = [descriptors]
            self.repo.cache_descriptor_metadata(descriptors)
        except Exception as e:
            logger.error(f"Error fetching descriptors from TrueData: {e}")
            raise

    def fetch_from_truedata_rest(self, connection_id: int, from_date: Optional[str] = None, to_date: Optional[str] = None, symbol: Optional[str] = None, top_n: Optional[int] = None) -> int:
        try:
            api_service = get_truedata_api_service(connection_id)
            params = {}
            if from_date: params["from"] = from_date
            if to_date: params["to"] = to_date
            if symbol: params["symbol"] = symbol
            if top_n: params["top"] = top_n
            
            endpoint_names = ["getAnnouncements", "announcements", "annoucements", "getCorporateAnnouncements", "corporateAnnouncements"]
            response = None
            last_error = None
            
            for endpoint in endpoint_names:
                try:
                    response = api_service.call_corporate_api(endpoint, params=params)
                    if not response: continue
                    logger.info(f"Successfully called TrueData endpoint: {endpoint}")
                    break
                except Exception as e:
                    last_error = e
                    continue
            
            if response is None:
                raise Exception(f"TrueData announcements endpoint not available. Last error: {last_error}")

            if isinstance(response, dict) and response.get("_format") == "csv":
                announcements_data = self._parse_csv_announcements(response.get("_data", ""))
            else:
                announcements_data = response
                if isinstance(response, dict):
                    if "data" in response: announcements_data = response["data"]
                    elif "result" in response: announcements_data = response["result"]
                if not isinstance(announcements_data, list):
                    announcements_data = [announcements_data] if announcements_data else []

            cnt = 0
            for ann_data in announcements_data:
                try:
                    ann = self._map_truedata_to_schema(ann_data)
                    if self.insert_announcement(ann): cnt += 1
                except Exception as e:
                     logger.warning(f"Error processing announcement: {e}")
            return cnt
        except Exception as e:
            logger.error(f"Error fetching from TrueData REST API: {e}")
            raise

    def _parse_csv_announcements(self, csv_data: str) -> List[Dict[str, Any]]:
        announcements = []
        try:
            reader = csv.DictReader(io.StringIO(csv_data))
            for row in reader:
                try:
                    sc = None
                    if row.get("scrip_code"):
                         try: sc = int(row["scrip_code"].strip())
                         except: pass
                    did = None
                    if row.get("news_descriptor"):
                         try: did = int(row["news_descriptor"].strip())
                         except: pass
                    
                    ann = {
                        "id": str(row.get("id", "")).strip(),
                        "trade_date": row.get("trade_date", "").strip() or None,
                        "script_code": sc,
                        "symbol_nse": row.get("symbol_nse", "").strip() or None,
                        "symbol_bse": row.get("symbol_bse", "").strip() or None,
                        "company_name": row.get("company_name", "").strip() or None,
                        "file_status": row.get("file_status", "").strip() or None,
                        "news_headline": row.get("news_headline", "").strip() or None,
                        "news_subhead": row.get("news_subhead", "").strip() or None,
                        "news_body": row.get("news_body", "").strip() or None,
                        "descriptor_id": did,
                        "announcement_type": row.get("announcement_type", "").strip() or None,
                        "meeting_type": row.get("meeting_type", "").strip() or None,
                        "date_of_meeting": row.get("date_of_meeting", "").strip() or None
                    }
                    if ann["id"]: announcements.append(ann)
                except: continue
            return announcements
        except Exception as e:
            logger.error(f"CSV Parse error: {e}")
            raise

    def _map_truedata_to_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        def get_first(*keys):
            lower_keys = {k.lower(): v for k,v in data.items()}
            for k in keys:
                if data.get(k) is not None and data.get(k) != "": return data[k]
                if lower_keys.get(k.lower()) is not None and lower_keys.get(k.lower()) != "": return lower_keys[k.lower()]
            return None
        
        def convert_date(d):
            if not d or not isinstance(d, str): return None
            for fmt in ["%d/%m/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
                try: return datetime.strptime(d.strip(), fmt).strftime("%Y-%m-%d %H:%M:%S")
                except: pass
            return d

        aid = get_first("id", "newsid", "news_id", "Id", "ID")
        if not aid: raise ValueError("Missing ID")
        
        sc = get_first("script_code", "SCRIP_CD", "scrip_code", "scripcode")
        try: sc = int(sc) if sc else None
        except: sc = None
        
        did = get_first("descriptor_id", "DescriptorID", "news_descriptor")
        try: did = int(did) if did else None
        except: did = None

        return {
            "id": str(aid).strip(),
            "trade_date": convert_date(get_first("trade_date", "Tradedate", "date", "timestamp")),
            "script_code": sc,
            "symbol_nse": get_first("symbol_nse", "Symbol_Nse", "SymbolNSE"),
            "symbol_bse": get_first("symbol_bse", "Symbol_Bse", "SymbolBSE"),
            "company_name": get_first("company_name", "CompanyName", "company"),
            "file_status": get_first("file_status", "Filestatus"),
            "news_headline": get_first("news_headline", "HeadLine", "headline", "title"),
            "news_subhead": get_first("news_subhead", "NewsSub", "subhead"),
            "news_body": get_first("news_body", "NewsBody", "body", "content"),
            "descriptor_id": did,
            "announcement_type": get_first("announcement_type", "TypeofAnnounce", "type"),
            "meeting_type": get_first("meeting_type", "TypeofMeeting"),
            "date_of_meeting": convert_date(get_first("date_of_meeting", "DateofMeeting"))
        }

def get_announcements_service() -> AnnouncementsService:
    return AnnouncementsService()
