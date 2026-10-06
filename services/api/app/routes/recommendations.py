from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.product import RecommendationResponse
from app.services.recommendation_service import recommendation_service

router = APIRouter(prefix="/api/v1/recommendations", tags=["Recommendations"])


@router.get("/{user_id}", response_model=RecommendationResponse, status_code=status.HTTP_200_OK)
def get_recommendations(user_id: int, db: Session = Depends(get_db)):
    """
    Retrieve rule-based personalized product recommendations for a user.
    """
    return recommendation_service.get_recommendations(db, user_id)
