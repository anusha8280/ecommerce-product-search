from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.product import SearchResponse
from app.services.search_service import search_service

router = APIRouter(prefix="/api/v1/search", tags=["Search"])


@router.get("", response_model=SearchResponse, status_code=status.HTTP_200_OK)
def search_products(
    q: Optional[str] = Query(None, description="Full-text search keyword query"),
    category: Optional[int] = Query(None, description="Filter by Category ID"),
    brand: Optional[int] = Query(None, description="Filter by Brand ID"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Minimum rating filter"),
    availability: Optional[bool] = Query(None, description="Filter by availability status"),
    sort: Optional[str] = Query("relevance", description="Sort order: relevance, price_asc, price_desc, rating, newest"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    Execute product search, filtering, and sorting backed by Redis caching and OpenSearch indexing.
    """
    return search_service.search(
        db=db,
        q=q,
        category=category,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        availability=availability,
        sort=sort,
        page=page,
        size=size
    )
