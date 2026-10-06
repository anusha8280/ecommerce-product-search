from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.product import Product, UserActivity


class RecommendationService:
    def get_recommendations(self, db: Session, user_id: int) -> Dict[str, Any]:
        # Simple rule-based logic:
        # 1. Fetch user's most recent activity
        recent_activity = db.query(UserActivity).filter(UserActivity.user_id == user_id).order_by(UserActivity.created_at.desc()).first()

        category_id = None
        if recent_activity and recent_activity.product:
            category_id = recent_activity.product.category_id

        # 2. Query top-rated available products in that category or overall top-rated
        query = db.query(Product).filter(Product.is_available == True)
        if category_id:
            query = query.filter(Product.category_id == category_id)

        recommendations = query.order_by(Product.rating.desc(), Product.created_at.desc()).limit(5).all()

        rec_items = [
            {
                "id": p.id,
                "name": p.name,
                "price": float(p.price) if p.price is not None else 0.0,
                "category_id": p.category_id,
                "brand_id": p.brand_id,
                "rating": float(p.rating) if p.rating is not None else 0.0,
                "reason": "Based on your recent browsing history" if category_id else "Popular top-rated product"
            }
            for p in recommendations
        ]

        return {
            "user_id": user_id,
            "recommendations": rec_items
        }


recommendation_service = RecommendationService()
