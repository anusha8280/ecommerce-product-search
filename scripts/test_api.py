"""
Integration tests for the E-Commerce Product Search System.

Strategy:
- All external infrastructure (Redis, Kafka, OpenSearch) is mocked via
  unittest.mock.patch so no real network connections are attempted.
- A temporary SQLite database is used in place of PostgreSQL.
- Tests run entirely offline with no Docker required.
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure the API package is importable
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "api"))
)

# ---------------------------------------------------------------------------
# Build mock objects that will replace the real infrastructure singletons
# ---------------------------------------------------------------------------
_mock_redis = MagicMock(name="redis_client")
_mock_redis.get.return_value = None        # always cache miss → fall through to DB
_mock_redis.setex.return_value = True
_mock_redis.delete.return_value = True
_mock_redis.is_healthy.return_value = False

_mock_kafka = MagicMock(name="kafka_producer")
_mock_kafka.publish_product_event.return_value = True
_mock_kafka.is_healthy.return_value = False

_mock_opensearch = MagicMock(name="opensearch_client")
_mock_opensearch.is_healthy.return_value = False
_mock_opensearch.index_product.return_value = True
_mock_opensearch.delete_product.return_value = True
# Returning 0 results forces search_service to use the SQLite fallback path
_mock_opensearch.search_products.return_value = {
    "products": [], "total": 0, "page": 1, "size": 20, "total_pages": 0
}

# ---------------------------------------------------------------------------
# Patch infrastructure singletons at the locations where they are *used*
# (i.e. where they are imported INTO, not where they are defined)
# ---------------------------------------------------------------------------
PATCHES = [
    patch("app.services.product_service.kafka_producer",    _mock_kafka),
    patch("app.services.product_service.opensearch_client", _mock_opensearch),
    patch("app.services.product_service.redis_client",      _mock_redis),
    patch("app.services.search_service.redis_client",       _mock_redis),
    patch("app.services.search_service.opensearch_client",  _mock_opensearch),
    # Patch the infra module singletons too (used by the health endpoint)
    patch("app.infrastructure.kafka_producer.kafka_producer",       _mock_kafka),
    patch("app.infrastructure.redis_client.redis_client",           _mock_redis),
    patch("app.infrastructure.opensearch_client.opensearch_client", _mock_opensearch),
]


@pytest.fixture(scope="session", autouse=True)
def apply_patches():
    """Start all infrastructure patches for the entire test session."""
    started = [p.start() for p in PATCHES]
    yield
    for p in PATCHES:
        try:
            p.stop()
        except RuntimeError:
            pass


# ---------------------------------------------------------------------------
# Import app AFTER patches are defined (patches start lazily inside fixture,
# but we need the imports available now — that is fine because we patch the
# *attribute* on already-imported modules, not the module import itself)
# ---------------------------------------------------------------------------
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine       # noqa: E402
from sqlalchemy.orm import sessionmaker    # noqa: E402

from app.main import app           # noqa: E402
from app.database import Base, get_db  # noqa: E402

# ---------------------------------------------------------------------------
# Override the database dependency to use an in-memory SQLite DB
# ---------------------------------------------------------------------------
TEST_DB_PATH = "test_ecommerce.db"
TEST_DATABASE_URL = f"sqlite:///./{TEST_DB_PATH}"

_test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest.fixture(scope="session")
def client(apply_patches):   # ensure patches are active before client is built
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_product(client, **kwargs):
    payload = {
        "name":           kwargs.pop("name", "Test Product"),
        "price":          kwargs.pop("price", 99.99),
        "stock_quantity": kwargs.pop("stock", 50),
        "is_available":   kwargs.pop("available", True),
        **kwargs,
    }
    return client.post("/api/v1/products", json=payload)


# ===========================================================================
# 1 · Health Check
# ===========================================================================
class TestHealthCheck:
    def test_returns_200(self, client):
        assert client.get("/health").status_code == 200

    def test_status_is_healthy(self, client):
        assert client.get("/health").json()["status"] == "healthy"

    def test_infrastructure_section_present(self, client):
        infra = client.get("/health").json()["infrastructure"]
        assert "redis" in infra and "kafka" in infra and "opensearch" in infra


# ===========================================================================
# 2 · Product Creation  POST /api/v1/products
# ===========================================================================
class TestProductCreation:
    def test_create_returns_201(self, client):
        assert _make_product(client, name="Sony WH-1000XM5", price=399.99).status_code == 201

    def test_create_returns_correct_fields(self, client):
        data = _make_product(client, name="Logitech MX Master 3S", price=99.99, stock=200).json()
        assert data["name"] == "Logitech MX Master 3S"
        assert float(data["price"]) == 99.99
        assert data["stock_quantity"] == 200
        assert "id" in data and "created_at" in data

    def test_create_with_attributes(self, client):
        r = client.post("/api/v1/products", json={
            "name": "Apple Watch Series 9", "price": 429.00, "stock_quantity": 50,
            "attributes": [
                {"attribute_name": "Color", "attribute_value": "Midnight"},
                {"attribute_name": "Size",  "attribute_value": "45mm"},
            ],
        })
        assert r.status_code == 201
        assert len(r.json()["attributes"]) == 2

    def test_default_rating_is_zero(self, client):
        assert float(_make_product(client).json()["rating"]) == 0.0

    def test_negative_price_rejected(self, client):
        r = client.post("/api/v1/products", json={"name": "Bad", "price": -5.0, "stock_quantity": 10})
        assert r.status_code == 422

    def test_missing_price_rejected(self, client):
        assert client.post("/api/v1/products", json={"name": "No Price"}).status_code == 422

    def test_kafka_event_on_create(self, client):
        _mock_kafka.publish_product_event.reset_mock()
        _make_product(client, name="Kafka Test", price=49.99)
        _mock_kafka.publish_product_event.assert_called_once()
        assert _mock_kafka.publish_product_event.call_args[0][0] == "PRODUCT_CREATED"

    def test_opensearch_indexed_on_create(self, client):
        _mock_opensearch.index_product.reset_mock()
        _make_product(client, name="OpenSearch Test", price=59.99)
        _mock_opensearch.index_product.assert_called_once()


# ===========================================================================
# 3 · Get Product by ID  GET /api/v1/products/{id}
# ===========================================================================
class TestGetProduct:
    @pytest.fixture(scope="class")
    def product_id(self, client):
        return _make_product(client, name="Samsung Galaxy Watch6", price=379.99).json()["id"]

    def test_get_returns_200(self, client, product_id):
        assert client.get(f"/api/v1/products/{product_id}").status_code == 200

    def test_get_returns_correct_data(self, client, product_id):
        data = client.get(f"/api/v1/products/{product_id}").json()
        assert data["name"] == "Samsung Galaxy Watch6"
        assert float(data["price"]) == 379.99

    def test_nonexistent_returns_404(self, client):
        assert client.get("/api/v1/products/999999").status_code == 404

    def test_404_has_error_code(self, client):
        assert client.get("/api/v1/products/999999").json()["detail"]["code"] == "PRODUCT_NOT_FOUND"


# ===========================================================================
# 4 · Update Product  PUT /api/v1/products/{id}
# ===========================================================================
class TestUpdateProduct:
    @pytest.fixture(scope="class")
    def product_id(self, client):
        return _make_product(client, name="Original", price=49.99).json()["id"]

    def test_update_returns_200(self, client, product_id):
        assert client.put(f"/api/v1/products/{product_id}", json={"name": "Updated", "price": 59.99}).status_code == 200

    def test_update_reflects_changes(self, client, product_id):
        client.put(f"/api/v1/products/{product_id}", json={"name": "Final", "price": 79.99, "is_available": False})
        data = client.get(f"/api/v1/products/{product_id}").json()
        assert data["name"] == "Final" and float(data["price"]) == 79.99 and data["is_available"] is False

    def test_update_nonexistent_returns_404(self, client):
        assert client.put("/api/v1/products/999999", json={"name": "Ghost"}).status_code == 404

    def test_kafka_event_on_update(self, client, product_id):
        _mock_kafka.publish_product_event.reset_mock()
        client.put(f"/api/v1/products/{product_id}", json={"price": 89.99})
        _mock_kafka.publish_product_event.assert_called_once()
        assert _mock_kafka.publish_product_event.call_args[0][0] == "PRODUCT_UPDATED"


# ===========================================================================
# 5 · Delete Product  DELETE /api/v1/products/{id}
# ===========================================================================
class TestDeleteProduct:
    @pytest.fixture(scope="class")
    def product_id(self, client):
        return _make_product(client, name="To Be Deleted", price=19.99).json()["id"]

    def test_delete_returns_200(self, client, product_id):
        assert client.delete(f"/api/v1/products/{product_id}").status_code == 200

    def test_deleted_product_is_gone(self, client, product_id):
        assert client.get(f"/api/v1/products/{product_id}").status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        assert client.delete("/api/v1/products/999999").status_code == 404

    def test_kafka_event_on_delete(self, client):
        pid = _make_product(client, name="Delete Kafka Test", price=29.99).json()["id"]
        _mock_kafka.publish_product_event.reset_mock()
        client.delete(f"/api/v1/products/{pid}")
        _mock_kafka.publish_product_event.assert_called_once()
        assert _mock_kafka.publish_product_event.call_args[0][0] == "PRODUCT_DELETED"


# ===========================================================================
# 6 · Product Search  GET /api/v1/search   (SQLite fallback path)
# ===========================================================================
class TestProductSearch:
    @pytest.fixture(scope="class", autouse=True)
    def seed_products(self, client):
        _make_product(client, name="Wireless Noise Canceling Headphones", price=299.99, stock=50,  available=True)
        _make_product(client, name="Wired Gaming Headset",                price=79.99,  stock=100, available=True)
        _make_product(client, name="Bluetooth Speaker Pro",               price=149.99, stock=0,   available=False)
        _make_product(client, name="Budget USB Keyboard",                 price=29.99,  stock=200, available=True)

    def test_search_returns_200(self, client):
        assert client.get("/api/v1/search").status_code == 200

    def test_search_has_required_fields(self, client):
        data = client.get("/api/v1/search").json()
        for field in ("products", "total", "page", "size", "total_pages"):
            assert field in data

    def test_pagination_limits_results(self, client):
        data = client.get("/api/v1/search?page=1&size=2").json()
        assert data["page"] == 1 and len(data["products"]) <= 2

    def test_keyword_search_headphones(self, client):
        data = client.get("/api/v1/search?q=headphones").json()
        assert data["total"] >= 1
        assert any("headphone" in p["name"].lower() for p in data["products"])

    def test_sort_price_asc(self, client):
        prices = [p["price"] for p in client.get("/api/v1/search?sort=price_asc").json()["products"]]
        assert prices == sorted(prices)

    def test_sort_price_desc(self, client):
        prices = [p["price"] for p in client.get("/api/v1/search?sort=price_desc").json()["products"]]
        assert prices == sorted(prices, reverse=True)

    def test_filter_available_only(self, client):
        for p in client.get("/api/v1/search?availability=true").json()["products"]:
            assert p["is_available"] is True

    def test_filter_price_range(self, client):
        for p in client.get("/api/v1/search?min_price=50&max_price=200").json()["products"]:
            assert 50.0 <= p["price"] <= 200.0

    def test_cache_miss_checked(self, client):
        _mock_redis.get.reset_mock()
        client.get("/api/v1/search?q=keyboard")
        _mock_redis.get.assert_called_once()

    def test_result_written_to_cache(self, client):
        _mock_redis.setex.reset_mock()
        client.get("/api/v1/search?q=speaker")
        _mock_redis.setex.assert_called_once()

    def test_page_zero_rejected(self, client):
        assert client.get("/api/v1/search?page=0").status_code == 422

    def test_size_too_large_rejected(self, client):
        assert client.get("/api/v1/search?size=999").status_code == 422


# ===========================================================================
# 7 · Recommendations  GET /api/v1/recommendations/{user_id}
# ===========================================================================
class TestRecommendations:
    def test_returns_200(self, client):
        assert client.get("/api/v1/recommendations/1").status_code == 200

    def test_response_structure(self, client):
        data = client.get("/api/v1/recommendations/1").json()
        assert "user_id" in data
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)

    def test_user_id_matches(self, client):
        assert client.get("/api/v1/recommendations/42").json()["user_id"] == 42

    def test_items_have_required_fields(self, client):
        for item in client.get("/api/v1/recommendations/1").json()["recommendations"]:
            for field in ("id", "name", "price", "rating", "reason"):
                assert field in item
