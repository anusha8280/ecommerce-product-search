# E-Commerce Product Search and High-Concurrency Purchase System

A design-first architecture and prototype designed for high-throughput product discovery and resilient flash-sale purchase workflows at scale.

---

## 1. Problem Statement

Modern e-commerce systems face two distinct architectural challenges:

1. **Read-Heavy Scale & Discovery**: Querying millions of products with complex filtering, sorting, full-text search, and recommendations under heavy query traffic causes database overload and slow latency if relying solely on transactional databases.
2. **Write-Heavy Concurrency & Flash Sales**: Flash-sale events introduce extreme traffic spikes focused on limited inventory. Unprotected systems suffer from race conditions, inventory overselling, database locks, duplicate order submissions, and catastrophic system failures.

---

## 2. Project Objectives

- **High-Performance Search & Discovery**: Deliver fast product search, rich filtering/sorting, and personalized recommendations across millions of items.
- **Real-Time Catalog Synchronization**: Propagate catalog updates in real-time to search indexes and caches using event streaming.
- **Overselling Prevention**: Guarantee zero inventory overselling under extreme flash-sale purchase concurrency using atomic reservation mechanisms.
- **Duplicate Request Protection**: Ensure strict idempotency for purchase requests to prevent duplicate charging or order creation.
- **Asynchronous Decoupling**: Decouple order creation, inventory reservation, and payment processing for high availability and throughput.
- **Design-First Prototype**: Demonstrate core critical flows and end-to-end event streams cleanly without unnecessary enterprise boilerplate.

---

## 3. Planned Services

The architecture is designed as a set of lightweight, modular services:

* **Product Search & Catalog Service**
  * Serves high-throughput query requests (search, filter, sort, recommendations).
  * Implements multi-tier caching (Redis read-aside).
  * Consumes catalog update events from Kafka to sync OpenSearch/Elasticsearch indexes and invalidate caches in real-time.

* **Inventory & Flash-Sale Service**
  * Handles high-concurrency purchase traffic and inventory reservation.
  * Uses Redis (atomic Lua scripts / memory counters) for fast pre-reservation and lock-free inventory decrementing.
  * Validates idempotency keys to drop duplicate submit requests.

* **Order Service**
  * Manages order creation and lifecycle status states.
  * Emits order events to Kafka for downstream payment processing and inventory reconciliation.

* **Payment Processing Service**
  * Listens to order creation events from Kafka.
  * Asynchronously processes payment transactions and publishes payment result events (`PaymentSucceeded`, `PaymentFailed`).

---

## 4. Planned Infrastructure

* **Redis**: Distributed read caching for product catalog, atomic memory counters/Lua scripts for high-concurrency inventory reservation, and idempotency key registry.
* **Apache Kafka**: Event streaming backbone for real-time product updates, inventory sync, order lifecycle state changes, and payment processing triggers.
* **PostgreSQL**: Transactional storage for product catalog, master inventory counts, order histories, and payment logs.
* **OpenSearch / Elasticsearch**: Distributed search engine optimized for full-text product search, faceted filtering, sorting, and recommendation scoring.
* **Docker & Docker Compose**: Containerized environment for local development, orchestration, and infrastructure deployment.

---

## 5. Development Phases

1. **Phase 1: Project & Infrastructure Foundation**
   * Establish modular service project structure and Docker Compose environment for Redis, Kafka, PostgreSQL, and OpenSearch.
2. **Phase 2: Product Search & Real-Time Sync**
   * Seed catalog into PostgreSQL & OpenSearch.
   * Build search query pipeline with Redis caching.
   * Implement Kafka event stream to process real-time product updates into search index.
3. **Phase 3: High-Concurrency Flash Sale & Inventory Reservation**
   * Implement idempotency protection in Redis.
   * Develop atomic inventory reservation using Redis Lua scripts and database sync.
   * Verify race condition handling and zero-overselling under concurrent load.
4. **Phase 4: Order Creation & Async Payment Processing**
   * Implement event-driven order creation pipeline via Kafka.
   * Add payment processing workflow and state management.
5. **Phase 5: Critical Flow End-to-End Validation**
   * Verify end-to-end integration across search, reservation, order generation, and payment handling.

---

## 6. Important Architectural Constraints

* **Design-First Architectural Focus**: Prioritize clear data models, explicit event contracts, and modular boundary isolation over detailed business logic implementation.
* **Strict Overselling Prevention**: Inventory reservations must be atomic before order confirmation. Reservations occurring in fast-memory (Redis) must be backed by transactional reconciliation in PostgreSQL.
* **Mandatory Idempotency**: All purchase and payment endpoints must require a unique idempotency key checked against Redis before processing.
* **Asynchronous Event-Driven Decoupling**: Avoid synchronous inter-service HTTP chains during purchase paths; rely on Kafka for event propagation.
* **Eventual Consistency for Search**: Search indexing and cache invalidation are asynchronously synchronized via Kafka event streams.
