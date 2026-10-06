# Kafka Design

## 1. Purpose

Apache Kafka is used as the asynchronous event-streaming layer for product updates.

The main purpose is to decouple product-management operations from search-index updates.

The Product Service writes product information to PostgreSQL and publishes a product event to Kafka.

The Search Indexer consumes the event and updates OpenSearch.

---

## 2. Product Update Architecture

```text
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

PostgreSQL remains the source of truth.

OpenSearch contains a search-optimized copy of product information.

---

# 3. Kafka Topic

The initial Kafka topic will be:

```text
product-events
```

This topic contains events related to product changes.

Supported event types:

```text
PRODUCT_CREATED
PRODUCT_UPDATED
PRODUCT_DELETED
```

---

# 4. Product Event Structure

A product event will use JSON.

Example:

```json
{
  "event_id": "evt-12345",
  "event_type": "PRODUCT_UPDATED",
  "product_id": 101,
  "timestamp": "2026-10-05T10:30:00Z"
}
```

Fields:

| Field      | Purpose                       |
| ---------- | ----------------------------- |
| event_id   | Unique event identifier       |
| event_type | Type of product operation     |
| product_id | Product affected by the event |
| timestamp  | Event creation time           |

The initial event contains the product ID rather than duplicating the complete product record.

The Search Indexer can retrieve the current product information when required.

---

# 5. Product Created Flow

When a new product is created:

```text
Product API
     |
     v
Product Service
     |
     +------> PostgreSQL
     |
     v
PRODUCT_CREATED
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

The product becomes available for search after the indexing event has been successfully processed.

---

# 6. Product Updated Flow

When a product is updated:

```text
Product Service
      |
      +------> PostgreSQL
      |
      v
PRODUCT_UPDATED
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

The Search Indexer updates the corresponding OpenSearch document.

---

# 7. Product Deleted Flow

When a product is deleted:

```text
Product Service
      |
      +------> PostgreSQL
      |
      v
PRODUCT_DELETED
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

The Search Indexer removes the corresponding document from OpenSearch.

---

# 8. Partition Strategy

The `product-events` topic will initially use multiple partitions so product events can be processed in parallel.

The product ID should be used as the Kafka message key.

Example:

```text
Key:
product_id = 101
```

Using the product ID as the key helps ensure events for the same product are routed consistently to the same partition.

This is important for maintaining event ordering for a particular product.

The exact number of partitions will be determined during implementation and load testing.

---

# 9. Consumer Group

The Search Indexer will use a consumer group:

```text
search-indexer-group
```

Example:

```text
Kafka
 |
 | product-events
 |
 +---- Partition 0 ----> Search Indexer
 |
 +---- Partition 1 ----> Search Indexer
 |
 +---- Partition 2 ----> Search Indexer
```

Multiple Search Indexer instances can belong to the same consumer group.

Kafka distributes partitions across the instances.

This allows indexing throughput to scale horizontally.

---

# 10. Retry Strategy

Temporary failures can occur when OpenSearch is unavailable.

If processing an event fails:

```text
Kafka
  |
  v
Search Indexer
  |
  X
OpenSearch unavailable
```

The event should not be treated as successfully processed.

The consumer can retry processing according to the configured retry policy.

The initial implementation will use limited retries with increasing delays.

---

# 11. Dead-Letter Topic

Events that repeatedly fail processing should be moved to a dead-letter topic.

Topic:

```text
product-events-dlq
```

Flow:

```text
product-events
      |
      v
Search Indexer
      |
   Processing
      |
   +--+--+
   |     |
Success Failure
   |     |
   |     v
   |   Retry
   |     |
   |     v
   |  Repeated failure
   |     |
   |     v
   | product-events-dlq
   |
   v
OpenSearch
```

The dead-letter topic allows failed events to be investigated and reprocessed later.

---

# 12. Consumer Offset

The Search Indexer should commit the Kafka offset only after the event has been successfully processed.

Conceptually:

```text
Consume Event
     |
     v
Process Event
     |
     v
Update OpenSearch
     |
     v
Commit Offset
```

If OpenSearch processing fails before the offset is committed, the event can be processed again.

---

# 13. Idempotency

The Search Indexer should be designed to safely process the same event more than once.

For example:

```text
PRODUCT_UPDATED
product_id = 101
```

If the same event is received again, updating the same OpenSearch document should not produce incorrect duplicate product documents.

The product ID will be used as the OpenSearch document identifier.

This provides a simple mechanism for idempotent indexing.

---

# 14. Eventual Consistency

PostgreSQL and OpenSearch are not updated atomically.

Therefore:

```text
PostgreSQL updated
       |
       | short propagation delay
       v
Kafka
       |
       v
Search Indexer
       |
       v
OpenSearch updated
```

During this short period, PostgreSQL may contain newer information than OpenSearch.

This is an intentional eventual-consistency trade-off.

---

# 15. Kafka Failure Handling

If Kafka becomes temporarily unavailable when a product update occurs, the Product Service must not silently lose the event.

The implementation should use a reliable event-publication strategy.

For the initial project, product database operations and event publication should be monitored carefully.

A production implementation could use the Transactional Outbox Pattern to reliably coordinate database changes and event publication.

The Outbox Pattern can be introduced later if required by the system's reliability requirements.

---

# 16. Kafka and Redis Interaction

Kafka and Redis have different responsibilities.

### Kafka

Handles:

```text
Product update events
```

### Redis

Handles:

```text
Search-result caching
```

They are not replacements for each other.

Overall:

```text
                    Product Update
                         |
                         v
                  Product Service
                    /         \
                   /           \
                  v             v
            PostgreSQL        Kafka
                               |
                               v
                         Search Indexer
                               |
                               v
                          OpenSearch
                               ^
                               |
                         Search Service
                               ^
                               |
                             Redis
                               ^
                               |
                             User
```

---

# 17. Design Summary

| Property               | Decision                    |
| ---------------------- | --------------------------- |
| Topic                  | `product-events`            |
| Consumer group         | `search-indexer-group`      |
| Event types            | CREATED, UPDATED, DELETED   |
| Message key            | Product ID                  |
| Search indexer         | Kafka consumer              |
| Failed events          | Retry                       |
| Repeated failures      | `product-events-dlq`        |
| Offset commit          | After successful processing |
| OpenSearch document ID | Product ID                  |
| Consistency            | Eventual                    |
| Primary database       | PostgreSQL                  |

Kafka therefore provides asynchronous, scalable and decoupled propagation of product changes from PostgreSQL to OpenSearch.
