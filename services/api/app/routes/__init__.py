from app.routes.products import router as products_router
from app.routes.search import router as search_router
from app.routes.recommendations import router as recommendations_router

__all__ = ["products_router", "search_router", "recommendations_router"]
