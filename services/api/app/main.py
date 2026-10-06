import uuid
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.routes import products_router, search_router, recommendations_router
from app.infrastructure import redis_client, kafka_producer, opensearch_client

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="E-Commerce Product Search System API with Redis caching, Kafka event propagation, PostgreSQL persistence, and OpenSearch full-text search.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    print(f"Starting {settings.PROJECT_NAME} API...")
    init_db()


@app.get("/health", tags=["Health"])
def health_check():
    """
    Health check endpoint returning API service status and downstream infrastructure health.
    """
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENV,
        "infrastructure": {
            "redis": "healthy" if redis_client.is_healthy() else "unreachable/degraded",
            "kafka": "healthy" if kafka_producer.is_healthy() else "unreachable/degraded",
            "opensearch": "healthy" if opensearch_client.is_healthy() else "unreachable/degraded"
        }
    }


# Standard Error Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = f"req-{uuid.uuid4()}"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(exc) if settings.ENV == "development" else "An unexpected error occurred.",
                "request_id": request_id
            }
        }
    )


# Register Routers
app.include_router(products_router)
app.include_router(search_router)
app.include_router(recommendations_router)
