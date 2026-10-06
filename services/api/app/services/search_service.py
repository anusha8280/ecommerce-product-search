import hashlib
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.config import settings
from app.models.product import Product
from app.infrastructure.redis_client import redis_client
from app.infrastructure.opensearch_client import opensearch_client


class SearchService:
    def search(
        self,
        db: Session,
        q: Optional[str] = None,
        category: Optional[int] = None,
        brand: Optional[int] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        availability: Optional[bool] = None,
        sort: Optional[str] = "relevance",
        page: int = 1,
        size: int = 20
    ) -> Dict[str, Any]:
        # 1. Build normalized cache key
        cache_key = self._generate_cache_key(
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

        # 2. Check Redis cache
        cached_result = redis_client.get(cache_key)
        if cached_result:
            return cached_result

        # 3. Query OpenSearch
        result = opensearch_client.search_products(
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

        # Fallback to PostgreSQL if OpenSearch index is empty or unavailable
        if not result["products"] and result["total"] == 0:
            result = self._search_postgres_fallback(
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

        # 4. Cache search result in Redis with TTL (60 seconds)
        redis_client.setex(cache_key, settings.REDIS_TTL, result)

        # 5. Return search response
        return result

    def _generate_cache_key(self, **kwargs) -> str:
        param_str = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None)
        hashed = hashlib.md5(param_str.encode("utf-8")).hexdigest()
        return f"search:{hashed}"

    def _search_postgres_fallback(
        self,
        db: Session,
        q: Optional[str] = None,
        category: Optional[int] = None,
        brand: Optional[int] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        availability: Optional[bool] = None,
        sort: Optional[str] = "relevance",
        page: int = 1,
        size: int = 20
    ) -> Dict[str, Any]:
        query = db.query(Product)

        if q:
            query = query.filter(Product.name.ilike(f"%{q}%") | Product.description.ilike(f"%{q}%"))
        if category is not None:
            query = query.filter(Product.category_id == category)
        if brand is not None:
            query = query.filter(Product.brand_id == brand)
        if availability is not None:
            query = query.filter(Product.is_available == availability)
        if min_price is not None:
            query = query.filter(Product.price >= min_price)
        if max_price is not None:
            query = query.filter(Product.price <= max_price)
        if min_rating is not None:
            query = query.filter(Product.rating >= min_rating)

        if sort == "price_asc":
            query = query.order_by(Product.price.asc())
        elif sort == "price_desc":
            query = query.order_by(Product.price.desc())
        elif sort == "rating":
            query = query.order_by(Product.rating.desc())
        elif sort == "newest":
            query = query.order_by(Product.created_at.desc())
        else:
            query = query.order_by(Product.id.desc())

        total = query.count()
        offset = (page - 1) * size
        products = query.offset(offset).limit(size).all()

        total_pages = (total + size - 1) // size if size > 0 else 1

        products_list = [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "price": float(p.price) if p.price is not None else 0.0,
                "category_id": p.category_id,
                "brand_id": p.brand_id,
                "rating": float(p.rating) if p.rating is not None else 0.0,
                "stock_quantity": p.stock_quantity,
                "is_available": p.is_available
            }
            for p in products
        ]

        return {
            "products": products_list,
            "total": total,
            "page": page,
            "size": size,
            "total_pages": total_pages
        }


search_service = SearchService()
