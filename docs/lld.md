# Low-Level Design (LLD)

## 1. Application Structure

The low-level application layout follows a clean, layered microservice structure implemented in Python using FastAPI.

```text
services/api/app/
├── main.py                 # Application entrypoint, FastAPI instance, middleware initialization
├── config.py               # Environment configuration and settings management
├── database.py             # PostgreSQL database connection pool and session manager
├── models/                 # SQLAlchemy ORM database models
│   ├── product.py
│   ├── category.py
│   ├── brand.py
│   ├── attribute.py
│   ├── user.py
│   └── activity.py
├── schemas/                # Pydantic data validation and serialization models
│   ├── product.py
│   ├── search.py
│   └── recommendation.py
├── routes/                 # API Endpoint controllers (HTTP route handlers)
│   ├── products.py
│   ├── search.py
│   └── recommendations.py
├── services/               # Business logic layer
│   ├── product_service.py
│   ├── search_service.py
│   └── recommendation_service.py
└── infrastructure/         # External service drivers and clients
    ├── redis_client.py
    ├── kafka_producer.py
    └── opensearch_client.py
```

---

## 2. API Layer

The API layer is responsible for HTTP request handling, endpoint routing, query parameter parsing, input validation via Pydantic schemas, and formatting HTTP responses.

* **`routes/products.py`**
  * Handlers: `POST /api/v1/products`, `GET /api/v1/products/{id}`, `PUT /api/v1/products/{id}`, `DELETE /api/v1/products/{id}`.
  * Responsibilities: Receives catalog mutation requests, validates payload schemas, delegates execution to `product_service.py`, and returns standard REST responses.

* **`routes/search.py`**
  * Handler: `GET /api/v1/search`.
  * Responsibilities: Parses query parameters (`q`, `category`, `brand`, `min_price`, `max_price`, `min_rating`, `availability`, `sort`, `page`, `size`), delegates lookup to `search_service.py`, and returns paginated search payloads.

* **`routes/recommendations.py`**
  * Handler: `GET /api/v1/recommendations/{user_id}`.
  * Responsibilities: Extracts user identity parameters, calls `recommendation_service.py`, and returns personalized product suggestion lists.

---

## 3. Service Layer

The Service Layer encapsulates all business rules, orchestration, database transaction boundaries, and event dispatch logic.

* **`services/product_service.py`**
  * Responsibilities:
    * Manages CRUD operations against PostgreSQL using ORM sessions.
    * Enforces business constraints (e.g., non-negative pricing, stock checks).
    * Publishes asynchronous catalog mutation events (`PRODUCT_CREATED`, `PRODUCT_UPDATED`, `PRODUCT_DELETED`) to Kafka via `kafka_producer.py` after PostgreSQL transactions commit.

* **`services/search_service.py`**
  * Responsibilities:
    * Coordinates search request processing.
    * Generates normalized Redis cache keys based on query arguments.
    * Queries `redis_client.py` for cache hits.
    * On cache miss, constructs OpenSearch DSL queries, executes search via `opensearch_client.py`, writes response to Redis with 60s TTL, and returns results.

* **`services/recommendation_service.py`**
  * Responsibilities:
    * Evaluates user browsing/search interaction history from `user_activities`.
    * Implements rule-based filtering (e.g., top-rated items matching user's recent category views).
    * Assembles recommendation payloads.

---

## 4. Infrastructure Layer

The Infrastructure Layer isolates low-level drivers, connection pools, and client SDKs for external systems.

* **`infrastructure/redis_client.py`**
  * Responsibilities: Manages Redis connection pool, handles key serialization/deserialization, executes `GET`/`SETEX` operations for search query caching, and handles cache eviction/invalidation.

* **`infrastructure/kafka_producer.py`**
  * Responsibilities: Initializes Kafka producer instance, serializes product mutation payloads (`event_id`, `event_type`, `product_id`, `timestamp`), partitions messages by `product_id`, and publishes events to `product-events` topic.

* **`infrastructure/opensearch_client.py`**
  * Responsibilities: Wraps OpenSearch Python client, manages cluster connection pooling, builds boolean queries, range filters, aggregations, and sorting definitions for OpenSearch indexes.

---

## 5. Product Creation Flow

```text
HTTP POST /api/v1/products
        |
        v
  routes/products.py (Validate Request Body)
        |
        v
  services/product_service.py
        |
   1. Write Record to PostgreSQL (Primary DB)
        |
   2. Transaction Committed
        |
   3. Publish PRODUCT_CREATED Event
        v
  infrastructure/kafka_producer.py
        |
        v
    Kafka (product-events topic)
        |
        v
  Search Indexer (Kafka Consumer)
        |
        v
  infrastructure/opensearch_client.py
        |
        v
    OpenSearch (Index Document)
```

1. Client submits product payload to `POST /api/v1/products`.
2. `routes/products.py` validates inputs and calls `product_service.create_product()`.
3. `product_service.py` inserts product row into PostgreSQL within an ACID transaction.
4. Upon successful commit, `product_service.py` calls `kafka_producer.send_event()` with a `PRODUCT_CREATED` payload.
5. The standalone Search Indexer consumes the event from Kafka and indexes the product document into OpenSearch.

---

## 6. Product Update Flow

```text
HTTP PUT /api/v1/products/{id}
        |
        v
  routes/products.py (Validate Request Body & Path Param)
        |
        v
  services/product_service.py
        |
   1. Update Record in PostgreSQL
        |
   2. Transaction Committed
        |
   3. Publish PRODUCT_UPDATED Event
        v
  infrastructure/kafka_producer.py
        |
        v
    Kafka (product-events topic)
        |
        v
  Search Indexer (Kafka Consumer)
        |
        v
  infrastructure/opensearch_client.py
        |
        v
    OpenSearch (Update Document by ID)
```

1. Client sends update payload to `PUT /api/v1/products/{id}`.
2. `product_service.py` updates the authoritative product record in PostgreSQL.
3. Upon commit, `product_service.py` dispatches a `PRODUCT_UPDATED` event to Kafka.
4. Search Indexer consumes the update event and updates the document in OpenSearch.

---

## 7. Product Search Flow

```text
HTTP GET /api/v1/search
        |
        v
  routes/search.py (Parse Query & Filter Params)
        |
        v
  services/search_service.py
        |
   1. Check Redis Cache Key
        |
   +----+-------------------------+
   |                              |
[Cache HIT]                   [Cache MISS]
   |                              |
   v                              v
Return Cached JSON           2. Query OpenSearch Index
   |                              |
   |                         3. Return Search Documents
   |                              |
   |                         4. Save to Redis (TTL: 60s)
   |                              |
   +----+-------------------------+
        |
        v
Return HTTP 200 Response
```

* **Cache HIT**: `search_service.py` retrieves cached JSON directly from `redis_client.py` and returns response immediately without touching OpenSearch.
* **Cache MISS**: `search_service.py` queries `opensearch_client.py`, fetches matching documents, writes JSON payload to Redis with 60-second TTL, and returns results.

---

## 8. Error Handling

The application enforces uniform exception handling across all layers:

* **400 Bad Request**: Raised when request validation fails (e.g., invalid query params, negative price, missing required schema fields).
* **404 Not Found**: Raised when target entity (`product_id` or `user_id`) does not exist in PostgreSQL.
* **409 Conflict**: Raised on unique constraint violations (e.g., duplicate category name or existing SKU).
* **429 Too Many Requests**: Triggered when client request rate exceeds API Gateway rate limits.
* **500 Internal Server Error**: Unhandled application exceptions, unexpected database query failures, or unrecoverable internal logic errors.
* **503 Service Unavailable**: Raised when downstream infrastructure (Redis, Kafka, or OpenSearch) is unreachable.

---

## 9. Scalability

* **Horizontal FastAPI Scaling**: API services run as stateless containers behind a load balancer, allowing independent horizontal scaling.
* **Redis Caching**: Offloads high-frequency read traffic from OpenSearch, maintaining sub-millisecond cache hits.
* **Kafka Partitions**: The `product-events` topic is partitioned by `product_id`, enabling parallel event ingestion across multiple broker nodes.
* **Search Indexer Consumer Scaling**: Multiple Search Indexer worker instances run inside consumer group `search-indexer-group`, distributing partition consumption evenly.
* **OpenSearch Replicas & Sharding**: Search cluster scales horizontally across multiple primary shards and read replicas for high query throughput.

---

## 10. Reliability

* **Redis Fallback**: If Redis experiences downtime, `search_service.py` catches connection errors and falls back directly to OpenSearch queries, degrading performance without causing system outage.
* **Kafka Retries**: Search Indexer implements exponential backoff retries when transient errors occur during OpenSearch index updates.
* **Kafka Dead-Letter Queue (DLQ)**: Poison-pill events that repeatedly fail after maximum retries are routed to `product-events-dlq` for isolated inspection.
* **Idempotent OpenSearch Indexing**: Indexer uses `product_id` as the document ID in OpenSearch (`PUT /products/_doc/{product_id}`), ensuring duplicate event processing produces idempotent index states.
* **Eventual Consistency**: PostgreSQL updates complete immediately; search index synchronization catches up asynchronously via Kafka event streams within milliseconds.
