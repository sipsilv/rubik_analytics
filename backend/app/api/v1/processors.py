from fastapi import APIRouter, Depends
from app.services.telegram_extractor.db import get_global_stats
from app.core.permissions import get_current_user
from app.models.user import User

router = APIRouter()

# AI enrichment removed

@router.get("/stats", response_model=dict)
def get_processor_stats(
    current_user: User = Depends(get_current_user)
):
    """
    Get global processing statistics for the News pipeline.
    """
    # Get Extraction Stats
    stats = get_global_stats()
    
    # Get AI Stats
    # AI stats removed
    
    # Merge
    # Merge
    # stats.update(ai_stats) - AI removed
    
    return stats

from app.services.telegram_extractor.db import get_recent_extractions
from app.services.news_scoring.db import get_recent_scores
from app.services.news_ai.db import get_recent_enrichments

@router.get("/data/{table_type}")
def get_processor_data(
    table_type: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """
    Get recent data rows for a specific table type.
    """
    if table_type == 'extraction':
        return get_recent_extractions(limit)
    elif table_type == 'scoring':
        return get_recent_scores(limit)
    elif table_type == 'enrichment':
        return get_recent_enrichments(limit)
    else:
        return []
