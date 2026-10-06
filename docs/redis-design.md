# Redis Design

## 1. Purpose

Redis is used as a high-speed caching layer in the E-Commerce Product Search System.

The primary purpose of Redis is to reduce repeated queries to OpenSearch and improve search response latency for frequently repeated queries.

Redis is not the source of truth for product data.

PostgreSQL remains the authoritative data store.

---

## 2. Redis Usage

Redis will primarily cache search results.

The search flow is:

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
 +---- Cache HIT ----> Return cached results
 |
 +---- Cache MISS
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
        User
```

---

## 3. Cache Key

The cache key is generated from the normalized search request.

Example:

```text
search:q=running-shoes:category=footwear:brand=nike:min=2000:max=8000:sort=relevance:page=1:size=20
```

The key should include all parameters that can change the search result.

Important parameters include:

* Search query
* Category
* Brand
* Minimum price
* Maximum price
* Minimum rating
* Availability
* Sort order
* Page
* Page size

This prevents different search requests from incorrectly sharing the same cached result.

---

## 4. Cache Value

The cached value contains the search response.

Example:

```json
{
  "products": [
    {
      "id": 101,
      "name": "Nike Air Max",
      "price": 5999,
      "rating": 4.5
    }
  ],
  "total": 1,
  "page": 1,
  "size": 20,
  "total_pages": 1
}
```

The value can be serialized as JSON before being stored in Redis.

---

## 5. TTL

The initial cache TTL will be:

```text
60 seconds
```

A short TTL is used because product information, price, stock and availability can change.

The TTL can be adjusted after measuring the cache hit rate and product-update frequency.

---

## 6. Cache Hit

When a search request arrives:

1. Search Service generates the cache key.
2. Search Service checks Redis.
3. If the key exists, Redis returns the cached result.
4. Search Service returns the result to the client.
5. OpenSearch is not queried.

Flow:

```text
Search Request
      |
      v
Search Service
      |
      v
Redis
      |
   HIT
      |
      v
Search Response
```

---

## 7. Cache Miss

If the cache key does not exist:

1. Search Service checks Redis.
2. Redis returns a cache miss.
3. Search Service queries OpenSearch.
4. OpenSearch returns search results.
5. Search Service stores the result in Redis.
6. Search Service returns the result to the client.

Flow:

```text
Search Request
      |
      v
Search Service
      |
      v
Redis
      |
    MISS
      |
      v
OpenSearch
      |
      v
Search Results
      |
      +------> Redis
      |
      v
    Client
```

---

## 8. Cache Invalidation

Product changes can make cached search results stale.

The system uses two mechanisms:

### TTL expiration

Cached search results automatically expire after 60 seconds.

### Event-driven invalidation

When important product changes occur, the system can invalidate affected cache entries.

Example:

```text
Product Updated
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

The system can also remove related cached search results when required.

For the initial implementation, TTL-based expiration will be the primary mechanism to keep the implementation simple.

---

## 9. Redis Failure Handling

Redis is a performance optimization and not the source of truth.

If Redis becomes unavailable:

```text
Search Service
      |
      X
    Redis
      |
      v
OpenSearch
```

The Search Service should continue querying OpenSearch directly.

Therefore, Redis failure should degrade performance rather than make the entire search system unavailable.

The application should log Redis failures for monitoring.

---

## 10. Cache Stampede Protection

If a very popular cache entry expires, many requests may simultaneously query OpenSearch.

For the initial implementation, this risk can be reduced by:

* Short request timeouts
* Reasonable TTLs
* Limiting unnecessary repeated queries

A distributed locking or request-coalescing mechanism can be added later if load testing demonstrates the need.

---

## 11. Redis Data Lifecycle

```text
Search Request
      |
      v
Generate Cache Key
      |
      v
Check Redis
      |
  +---+---+
  |       |
 HIT     MISS
  |       |
  |       v
  |   OpenSearch
  |       |
  |       v
  |     Redis
  |       |
  +---+---+
      |
      v
Return Response
```

---

## 12. Design Summary

| Property              | Decision                |
| --------------------- | ----------------------- |
| Purpose               | Search-result caching   |
| Primary data source   | PostgreSQL              |
| Search source         | OpenSearch              |
| Cache                 | Redis                   |
| Initial TTL           | 60 seconds              |
| Cache format          | JSON                    |
| Cache miss            | Query OpenSearch        |
| Redis failure         | Fall back to OpenSearch |
| Primary invalidation  | TTL                     |
| Optional invalidation | Event-driven            |

Redis is therefore used to improve performance without becoming a dependency for data correctness.
