# High-Level Design (HLD)

## 1. Overview

The E-Commerce Product Search System is designed to provide fast and scalable product discovery for an e-commerce platform containing millions of products.

The system supports:

* Product search
* Filtering
* Sorting
* Pagination
* Personalized product suggestions
* Product indexing
* Redis caching
* Real-time/near-real-time product updates
* High query traffic

The architecture separates transactional product data from search-optimized data. PostgreSQL acts as the authoritative source of product information, while OpenSearch provides fast search and filtering capabilities.

Apache Kafka is used for asynchronous product-update events, and Redis is used to reduce repeated search and product-data queries.

---

# 2. High-Level Architecture

The major components of the system are:

1. User
2. API Gateway
3. Product Service
4. Search Service
5. Recommendation Service
6. PostgreSQL
7. Redis
8. Apache Kafka
9. Search Indexer
10. OpenSearch

The high-level architecture is represented in:

```text
User
 |
 v
API Gateway
 |
 +-------------------+--------------------+
 |                   |                    |
 v                   v                    v
Product Service   Search Service   Recommendation Service
 |                   |                    |
 v                   v                    |
PostgreSQL          Redis                |
 |                   |                    |
 |                   v                    |
 |              OpenSearch               |
 |
 v
Kafka
 |
 v
Search Indexer
 |
 v
OpenSearch
```

---

# 3. Component Responsibilities

## 3.1 User

The user interacts with the system through search and product-discovery operations.

The user can:

* Search products
* Apply filters
* Sort results
* View product details
* Receive personalized suggestions

The user does not directly communicate with internal services.

All requests enter through the API Gateway.

---

# 3.2 API Gateway

The API Gateway acts as the main entry point for client requests.

Responsibilities:

* Request routing
* Authentication and authorization hooks
* Request validation
* Rate limiting
* Routing requests to appropriate services
* Providing a common API entry point

Example:

```text
User
 |
 v
API Gateway
 |
 +---- Search request ----------> Search Service
 |
 +---- Product request ---------> Product Service
 |
 +---- Recommendation request --> Recommendation Service
```

The API Gateway prevents clients from directly accessing internal services.

---

# 3.3 Product Service

The Product Service manages product information.

Responsibilities:

* Create product
* Retrieve product
* Update product
* Delete product
* Validate product information
* Store authoritative product data
* Publish product update events

The Product Service communicates with PostgreSQL for persistent product data.

Example:

```text
Product Service
      |
      v
PostgreSQL
```

After a successful product modification, an event is published to Kafka.

---

# 3.4 Search Service

The Search Service handles product-search operations.

Responsibilities:

* Keyword search
* Filtering
* Sorting
* Pagination
* Search-result retrieval
* Cache lookup
* Communication with OpenSearch

The Search Service first checks Redis for a cached result.

If the result is available:

```text
Search Service
      |
      v
    Redis
      |
   Cache Hit
      |
      v
   Response
```

If the result is not available:

```text
Search Service
      |
      v
    Redis
      |
   Cache Miss
      |
      v
  OpenSearch
      |
      v
Search Results
      |
      v
    Redis
      |
      v
   Response
```

This reduces unnecessary repeated queries to OpenSearch.

---

# 3.5 Recommendation Service

The Recommendation Service provides personalized product suggestions.

For the initial prototype, recommendations will use simple rule-based logic rather than a complex machine-learning model.

Possible inputs include:

* Previous searches
* Viewed products
* Purchased products
* Frequently viewed categories

Example:

```text
User searches:
Running shoes

User views:
Running socks

Recommendation Service
        |
        v

Recommended:
Sports accessories
Running socks
Sports watches
```

The architecture allows a more advanced recommendation system to be added later.

---

# 3.6 PostgreSQL

PostgreSQL is the primary transactional database and the authoritative source of product information.

It stores persistent information such as:

* Product details
* Categories
* Brands
* Product attributes
* Product availability

The search index is not treated as the source of truth.

The relationship is:

```text
PostgreSQL
    |
    | Authoritative data
    v
Product Service
```

---

# 3.7 Redis

Redis is used as a high-speed caching layer.

It can cache:

* Frequently requested search results
* Frequently accessed product information
* Short-lived data
* High-frequency request information

Example:

```text
Search Request
     |
     v
Search Service
     |
     v
   Redis
     |
     +---- HIT ----> Return cached result
     |
     +---- MISS ---> OpenSearch
```

Redis reduces latency and decreases the load on backend services and the search engine.

Redis is not the permanent source of truth for product information.

---

# 3.8 Apache Kafka

Apache Kafka acts as the asynchronous event-streaming backbone.

Kafka is used to communicate product changes between services without tightly coupling the Product Service and Search Indexer.

Example events include:

```text
ProductCreated
ProductUpdated
ProductDeleted
InventoryUpdated
```

The product-update flow is:

```text
Product Service
      |
      v
    Kafka
      |
      v
Search Indexer
      |
      v
 OpenSearch
```

Kafka also provides durable event handling so that temporary downstream failures do not necessarily cause product-update events to be lost.

---

# 3.9 Search Indexer

The Search Indexer consumes product events from Kafka.

Responsibilities:

* Consume product events
* Transform product data into search documents
* Create search documents
* Update search documents
* Delete search documents
* Maintain synchronization between PostgreSQL data changes and the OpenSearch index

Example:

```text
Kafka
  |
  | ProductUpdated
  v
Search Indexer
  |
  v
OpenSearch
```

---

# 3.10 OpenSearch

OpenSearch is the search-optimized product index.

It is responsible for:

* Keyword search
* Full-text search
* Filtering
* Sorting
* Relevance-based ranking
* Pagination

The search service queries OpenSearch rather than scanning millions of product records in PostgreSQL.

Example:

```text
User
 |
 | "running shoes"
 v
Search Service
 |
 v
OpenSearch
 |
 v
Relevant Products
```

---

# 4. Main System Flows

## 4.1 Product Search — Cache Hit

When a user searches for a frequently requested query:

```text
User
 |
 v
API Gateway
 |
 v
Search Service
 |
 v
Redis
 |
 | Cache Hit
 v
Search Results
 |
 v
User
```

This provides a fast response without querying OpenSearch.

---

## 4.2 Product Search — Cache Miss

When the requested search result is not available in Redis:

```text
User
 |
 v
API Gateway
 |
 v
Search Service
 |
 v
Redis
 |
 | Cache Miss
 v
OpenSearch
 |
 v
Search Results
 |
 +----> Redis
 |
 v
User
```

The result can be cached for future identical or equivalent requests.

---

# 5. Product Update Flow

When an administrator creates or updates a product:

```text
Product Admin
      |
      v
API Gateway
      |
      v
Product Service
      |
      +--------> PostgreSQL
      |
      v
    Kafka
      |
      v
Search Indexer
      |
      v
OpenSearch
```

PostgreSQL is updated first because it is the authoritative data store.

The Product Service then publishes an event to Kafka.

The Search Indexer consumes the event and updates OpenSearch.

This provides near-real-time propagation of product changes to the search system.

---

# 6. Product Deletion Flow

When a product is deleted:

```text
Product Service
      |
      +--------> PostgreSQL
      |
      v
ProductDeleted Event
      |
      v
Kafka
      |
      v
Search Indexer
      |
      v
OpenSearch
```

The corresponding search document is removed from OpenSearch.

---

# 7. Communication Model

The system uses two communication models.

## 7.1 Synchronous Communication

Synchronous communication is used when the client requires an immediate response.

Examples:

```text
User
  |
  v
API Gateway
  |
  v
Search Service
  |
  v
Redis / OpenSearch
```

The user waits for the response.

---

## 7.2 Asynchronous Communication

Asynchronous communication is used for product-update propagation.

Example:

```text
Product Service
      |
      v
    Kafka
      |
      v
Search Indexer
      |
      v
OpenSearch
```

The Product Service does not need to wait for the Search Indexer to finish before completing the initial product operation.

---

# 8. Caching Strategy

Redis is used to reduce repeated computation and search requests.

A typical cache key can be based on the normalized search request.

Example:

```text
search:running-shoes:shoes:nike:2000-5000:rating-desc
```

The cache should have a suitable expiration time.

When product information changes, affected cached data may need to be invalidated or allowed to expire.

The caching strategy is:

```text
Request
   |
   v
Redis
   |
   +---- Hit ----> Return
   |
   +---- Miss
          |
          v
      OpenSearch
          |
          v
       Redis
          |
          v
       Return
```

---

# 9. Search Indexing Strategy

The product database and search index have different purposes.

## PostgreSQL

Used for:

* Authoritative product data
* Transactional operations
* Persistent storage

## OpenSearch

Used for:

* Fast search
* Filtering
* Sorting
* Relevance ranking

The system therefore maintains a searchable copy of product data in OpenSearch.

The synchronization mechanism is:

```text
PostgreSQL
    |
    v
Product Service
    |
    v
Kafka
    |
    v
Search Indexer
    |
    v
OpenSearch
```

---

# 10. Scalability Strategy

The system is designed for high query traffic and millions of products.

## API Gateway

Multiple gateway instances can be deployed behind a load balancer.

## Search Service

The Search Service can be horizontally scaled.

Example:

```text
             Load Balancer
                  |
       +----------+----------+
       |          |          |
       v          v          v
    Search     Search     Search
   Instance   Instance   Instance
```

All instances can use the same Redis and OpenSearch infrastructure.

## Redis

Redis can be scaled using replication or clustering when required.

## Kafka

Kafka supports multiple consumers and partitions to process product events concurrently.

## OpenSearch

OpenSearch can be scaled using multiple nodes and shards for large product indexes.

---

# 11. Failure Handling

The system assumes that individual components may temporarily fail.

## Search Service Failure

Multiple Search Service instances can be deployed.

If one instance fails, traffic can be routed to another instance.

## Search Indexer Failure

If the Search Indexer temporarily fails:

```text
Product Service
      |
      v
    Kafka
      |
      X
Search Indexer unavailable
```

The product event remains in Kafka until it can be processed according to the configured retention and consumer behavior.

After recovery:

```text
Kafka
  |
  v
Search Indexer
  |
  v
OpenSearch
```

The search index can then catch up with product changes.

---

# 12. Consistency Model

The system uses different consistency models for different components.

## PostgreSQL

Strong source-of-truth consistency for product data.

## OpenSearch

Eventually consistent with PostgreSQL.

There may be a short delay between:

```text
PostgreSQL updated
```

and:

```text
OpenSearch updated
```

This is acceptable because the system prioritizes scalable search performance while maintaining PostgreSQL as the authoritative source.

---

# 13. Security Considerations

The system should include:

* HTTPS communication
* Authentication
* Authorization
* Input validation
* Rate limiting
* Secure credential management
* Protection against malformed search queries
* Restricted access to internal services
* Secure Kafka and database credentials

Administrative product-management APIs should require appropriate authorization.

---

# 14. Observability

The system should monitor:

### Application metrics

* Request count
* Response latency
* Error rate
* Search latency

### Redis metrics

* Cache hit rate
* Cache miss rate
* Memory usage

### Kafka metrics

* Consumer lag
* Event processing rate
* Failed messages

### OpenSearch metrics

* Query latency
* Indexing latency
* Cluster health

### Logging

Services should generate structured logs that include:

* Request ID
* Service name
* Timestamp
* Operation
* Status
* Error information

---

# 15. Architectural Trade-offs

## PostgreSQL + OpenSearch

Using both databases introduces data duplication and synchronization complexity.

However, it allows PostgreSQL to remain the source of truth while OpenSearch provides optimized search performance.

## Redis

Caching improves latency and reduces backend load but introduces cache invalidation and stale-data considerations.

## Kafka

Kafka provides asynchronous processing and decoupling but introduces additional infrastructure and event-processing complexity.

## Microservices

Separating Product, Search and Recommendation responsibilities improves scalability and independent deployment but adds service-to-service communication complexity.

For an individual hackathon prototype, the implementation should keep the number of independently deployed services limited while preserving these logical service boundaries.

---

# 16. Technology Summary

| Component       | Technology       | Purpose                             |
| --------------- | ---------------- | ----------------------------------- |
| API             | FastAPI          | Backend API                         |
| API Gateway     | Gateway layer    | Request routing                     |
| Product Data    | PostgreSQL       | Source of truth                     |
| Cache           | Redis            | Low-latency caching                 |
| Event Streaming | Apache Kafka     | Asynchronous events                 |
| Search          | OpenSearch       | Product search                      |
| Indexing        | Search Indexer   | Kafka-to-OpenSearch synchronization |
| Development     | Antigravity      | Development environment             |
| Containers      | Docker           | Local infrastructure                |
| Testing         | Postman / Locust | API and load testing                |
| Version Control | Git / GitHub     | Source control                      |

---

# 17. Summary

The architecture separates transactional operations from search operations.

The overall flow is:

```text
User
 |
 v
API Gateway
 |
 +-------------------+----------------------+
 |                   |                      |
 v                   v                      v
Product Service   Search Service     Recommendation Service
 |                   |
 v                   v
PostgreSQL          Redis
 |                   |
 v                   v
Kafka              OpenSearch
 |
 v
Search Indexer
 |
 v
OpenSearch
```

The key architectural principles are:

1. PostgreSQL is the source of truth.
2. OpenSearch is optimized for product search.
3. Redis reduces repeated search and product-data requests.
4. Kafka decouples product updates from search-index updates.
5. Search requests are handled synchronously.
6. Product-index updates are handled asynchronously.
7. Services can be horizontally scaled.
8. The search index is eventually consistent with the primary database.
9. Failure recovery is supported through redundant services and Kafka-based event processing.
10. The architecture is designed to support millions of products and high query traffic.
