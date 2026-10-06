# API Design Specification

## 1. Overview

This document specifies the RESTful API design for the **E-Commerce Product Search System**. All APIs adhere to standard REST conventions, using JSON for request and response payloads.

---

## 2. Global Conventions

* **Base Path**: `/api/v1`
* **Content-Type**: `application/json`
* **Character Encoding**: `UTF-8`
* **Timestamp Format**: ISO 8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`)

---

## 3. Product Update Workflow & Event Propagation

For all catalog mutation endpoints (`POST`, `PUT`, `DELETE`):

```text
Client Request
      |
      v
Product Service
      |
  1. Write / Update / Delete
      v
  PostgreSQL (Primary DB - Source of Truth)
      |
  2. Transaction Committed
      v
  Publish Event (ProductCreated / ProductUpdated / ProductDeleted)
      v
    Kafka
      |
  3. Consume Event
      v
 Search Indexer
      |
  4. Sync Index
      v
  OpenSearch Index
```

1. The Product Service writes directly to **PostgreSQL** first (authoritative storage).
2. Upon successful transaction commit, the service publishes an event (e.g., `ProductCreated`, `ProductUpdated`, `ProductDeleted`) to **Kafka**.
3. The **Search Indexer** asynchronously consumes the event from Kafka.
4. The Search Indexer updates or deletes the corresponding document in **OpenSearch**.

---

## 4. Search Query Caching Workflow

For `GET /api/v1/search`:

```text
Client Request
      |
      v
Search Service
      |
  1. Generate Cache Key (normalized query params)
      v
  Check Redis Cache
      |
      +---> Cache HIT -------------> Return Cached JSON Response
      |
      +---> Cache MISS
                |
            2. Query OpenSearch
                |
            3. Store Result in Redis (with TTL)
                |
            4. Return Search Response
```

1. Search Service inspects **Redis** using a hashed/normalized cache key representing search parameters.
2. **On Cache Hit**: Returns the cached response immediately.
3. **On Cache Miss**: Queries **OpenSearch** with full-text search, filters, pagination, and sorting parameters.
4. Stores the resulting dataset in **Redis** with a configurable TTL (Time-to-Live).
5. Returns the search response payload to the client.

---

## 5. Endpoints Specification

### 5.1 Product Management APIs

#### 5.1.1 Create Product
`POST /api/v1/products`

* **Purpose**: Creates a new product record in PostgreSQL and emits a `ProductCreated` event to Kafka.
* **Request Body**:
  ```json
  {
    "name": "Wireless Noise-Canceling Headphones",
    "description": "Premium over-ear headphones with active noise cancellation and 30-hour battery life.",
    "price": 299.99,
    "category_id": 5,
    "brand_id": 12,
    "stock_quantity": 150,
    "is_available": true,
    "attributes": [
      { "attribute_name": "Color", "attribute_value": "Black" },
      { "attribute_name": "Connectivity", "attribute_value": "Bluetooth 5.2" }
    ]
  }
  ```
* **Success Response (`201 Created`)**:
  ```json
  {
    "id": 1001,
    "name": "Wireless Noise-Canceling Headphones",
    "description": "Premium over-ear headphones with active noise cancellation and 30-hour battery life.",
    "price": 299.99,
    "category_id": 5,
    "brand_id": 12,
    "rating": 0.0,
    "stock_quantity": 150,
    "is_available": true,
    "attributes": [
      { "attribute_name": "Color", "attribute_value": "Black" },
      { "attribute_name": "Connectivity", "attribute_value": "Bluetooth 5.2" }
    ],
    "created_at": "2026-10-05T10:00:00Z",
    "updated_at": "2026-10-05T10:00:00Z"
  }
  ```
* **Status Codes**: `201 Created`, `400 Bad Request`, `401 Unauthorized`, `409 Conflict`, `500 Internal Server Error`.

---

#### 5.1.2 Get Product by ID
`GET /api/v1/products/{id}`

* **Purpose**: Retrieves full product details by unique product identifier.
* **Path Parameters**: `id` (integer) - Unique product ID.
* **Success Response (`200 OK`)**:
  ```json
  {
    "id": 1001,
    "name": "Wireless Noise-Canceling Headphones",
    "description": "Premium over-ear headphones with active noise cancellation and 30-hour battery life.",
    "price": 299.99,
    "category_id": 5,
    "brand_id": 12,
    "rating": 4.7,
    "stock_quantity": 150,
    "is_available": true,
    "attributes": [
      { "attribute_name": "Color", "attribute_value": "Black" },
      { "attribute_name": "Connectivity", "attribute_value": "Bluetooth 5.2" }
    ],
    "created_at": "2026-10-05T10:00:00Z",
    "updated_at": "2026-10-05T10:00:00Z"
  }
  ```
* **Status Codes**: `200 OK`, `404 Not Found`, `500 Internal Server Error`.

---

#### 5.1.3 Update Product
`PUT /api/v1/products/{id}`

* **Purpose**: Updates an existing product in PostgreSQL and emits a `ProductUpdated` event to Kafka.
* **Path Parameters**: `id` (integer) - Unique product ID.
* **Request Body**:
  ```json
  {
    "name": "Wireless Noise-Canceling Headphones v2",
    "description": "Updated model with active noise cancellation and 40-hour battery life.",
    "price": 279.99,
    "category_id": 5,
    "brand_id": 12,
    "stock_quantity": 120,
    "is_available": true
  }
  ```
* **Success Response (`200 OK`)**:
  ```json
  {
    "id": 1001,
    "name": "Wireless Noise-Canceling Headphones v2",
    "description": "Updated model with active noise cancellation and 40-hour battery life.",
    "price": 279.99,
    "category_id": 5,
    "brand_id": 12,
    "rating": 4.7,
    "stock_quantity": 120,
    "is_available": true,
    "created_at": "2026-10-05T10:00:00Z",
    "updated_at": "2026-10-05T10:30:00Z"
  }
  ```
* **Status Codes**: `200 OK`, `400 Bad Request`, `401 Unauthorized`, `404 Not Found`, `500 Internal Server Error`.

---

#### 5.1.4 Delete Product
`DELETE /api/v1/products/{id}`

* **Purpose**: Deletes a product from PostgreSQL and emits a `ProductDeleted` event to Kafka to purge OpenSearch and cache entries.
* **Path Parameters**: `id` (integer) - Unique product ID.
* **Success Response (`200 OK` or `204 No Content`)**:
  ```json
  {
    "message": "Product 1001 successfully deleted."
  }
  ```
* **Status Codes**: `200 OK`, `401 Unauthorized`, `404 Not Found`, `500 Internal Server Error`.

---

### 5.2 Product Search API

#### 5.2.1 Search Products
`GET /api/v1/search`

* **Purpose**: Executes keyword search, faceted filtering, pagination, and multi-field sorting. Supported by Redis caching and OpenSearch indexing.
* **Query Parameters**:
  * `q` (string, optional): Full-text keyword search term (e.g., `"wireless headphones"`).
  * `category` (integer, optional): Category ID filter.
  * `brand` (integer, optional): Brand ID filter.
  * `min_price` (decimal, optional): Minimum price threshold.
  * `max_price` (decimal, optional): Maximum price threshold.
  * `min_rating` (decimal, optional): Minimum product rating threshold (0.0 - 5.0).
  * `availability` (boolean, optional): Filter by stock availability (`true`/`false`).
  * `sort` (string, optional): Sorting dimension.
    * Supported values: `relevance` (default), `price_asc`, `price_desc`, `rating`, `newest`.
  * `page` (integer, default `1`): Page number (1-indexed).
  * `size` (integer, default `20`): Page size / item count per page (max `100`).

* **Success Response (`200 OK`)**:
  ```json
  {
    "products": [
      {
        "id": 1001,
        "name": "Wireless Noise-Canceling Headphones",
        "description": "Premium over-ear headphones with active noise cancellation.",
        "price": 299.99,
        "category_id": 5,
        "brand_id": 12,
        "rating": 4.7,
        "stock_quantity": 150,
        "is_available": true
      },
      {
        "id": 1008,
        "name": "True Wireless Earbuds",
        "description": "Compact in-ear wireless earbuds with charging case.",
        "price": 149.99,
        "category_id": 5,
        "brand_id": 12,
        "rating": 4.5,
        "stock_quantity": 80,
        "is_available": true
      }
    ],
    "total": 42,
    "page": 1,
    "size": 20,
    "total_pages": 3
  }
  ```
* **Status Codes**: `200 OK`, `400 Bad Request`, `500 Internal Server Error`, `503 Service Unavailable`.

---

### 5.3 Recommendation API

#### 5.3.1 Get Personalized Product Recommendations
`GET /api/v1/recommendations/{user_id}`

* **Purpose**: Fetches personalized product suggestions based on initial simple rule-based logic (e.g., matching user's recent category interactions, top-rated items in browsed brands, or frequently viewed products).
* **Path Parameters**: `user_id` (integer) - ID of the target user.
* **Success Response (`200 OK`)**:
  ```json
  {
    "user_id": 45,
    "recommendations": [
      {
        "id": 1005,
        "name": "Bluetooth Speaker Pro",
        "price": 119.99,
        "category_id": 5,
        "brand_id": 12,
        "rating": 4.8,
        "reason": "Popular in your frequently viewed Audio category"
      },
      {
        "id": 1012,
        "name": "Wireless Charging Pad",
        "price": 29.99,
        "category_id": 8,
        "brand_id": 3,
        "rating": 4.6,
        "reason": "Frequently bought together with Wireless Headphones"
      }
    ]
  }
  ```
* **Status Codes**: `200 OK`, `404 Not Found`, `500 Internal Server Error`.

---

## 6. Error Handling & Standard Error Response

All API errors return a uniform JSON error payload.

### Standard Error JSON Schema
```json
{
  "error": {
    "code": "ERROR_CODE_STRING",
    "message": "Human-readable description of the error.",
    "request_id": "req-8f92a11b-3c4d-4e5f-9a01-2b3c4d5e6f7a"
  }
}
```

### Common HTTP Status Codes & Error Codes

| HTTP Status | Error Code (`code`) | Description / Typical Trigger |
| :--- | :--- | :--- |
| **400 Bad Request** | `INVALID_PARAMETER` | Malformed JSON, negative price, invalid page parameter |
| **401 Unauthorized** | `UNAUTHORIZED` | Missing or invalid API key / authentication token |
| **403 Forbidden** | `FORBIDDEN` | User lacks permission for administrative endpoints |
| **404 Not Found** | `PRODUCT_NOT_FOUND` | Requested product ID does not exist |
| **409 Conflict** | `DUPLICATE_PRODUCT` | Unique constraint violation (e.g., duplicate SKU/product) |
| **429 Too Many Requests**| `RATE_LIMIT_EXCEEDED` | Request frequency exceeds client rate limit |
| **500 Internal Error** | `INTERNAL_SERVER_ERROR` | Unexpected backend or database exception |
| **503 Unavailable** | `SERVICE_UNAVAILABLE` | Search engine or search indexer temporarily unreachable |

---

## 7. Concrete Request & Response Examples

### 1. Creating a Product
* **Request**: `POST /api/v1/products`
  ```json
  {
    "name": "Ergonomic Gaming Mouse",
    "description": "High precision 26K DPI optical gaming mouse with customizable RGB.",
    "price": 79.99,
    "category_id": 3,
    "brand_id": 7,
    "stock_quantity": 250,
    "is_available": true
  }
  ```
* **Response (`201 Created`)**:
  ```json
  {
    "id": 2045,
    "name": "Ergonomic Gaming Mouse",
    "description": "High precision 26K DPI optical gaming mouse with customizable RGB.",
    "price": 79.99,
    "category_id": 3,
    "brand_id": 7,
    "rating": 0.0,
    "stock_quantity": 250,
    "is_available": true,
    "created_at": "2026-10-05T10:45:00Z",
    "updated_at": "2026-10-05T10:45:00Z"
  }
  ```

---

### 2. Getting a Product
* **Request**: `GET /api/v1/products/2045`
* **Response (`200 OK`)**:
  ```json
  {
    "id": 2045,
    "name": "Ergonomic Gaming Mouse",
    "description": "High precision 26K DPI optical gaming mouse with customizable RGB.",
    "price": 79.99,
    "category_id": 3,
    "brand_id": 7,
    "rating": 4.9,
    "stock_quantity": 250,
    "is_available": true,
    "created_at": "2026-10-05T10:45:00Z",
    "updated_at": "2026-10-05T10:45:00Z"
  }
  ```

---

### 3. Searching Products (Keyword Match)
* **Request**: `GET /api/v1/search?q=gaming+mouse`
* **Response (`200 OK`)**:
  ```json
  {
    "products": [
      {
        "id": 2045,
        "name": "Ergonomic Gaming Mouse",
        "description": "High precision 26K DPI optical gaming mouse with customizable RGB.",
        "price": 79.99,
        "category_id": 3,
        "brand_id": 7,
        "rating": 4.9,
        "stock_quantity": 250,
        "is_available": true
      }
    ],
    "total": 1,
    "page": 1,
    "size": 20,
    "total_pages": 1
  }
  ```

---

### 4. Filtering Products
* **Request**: `GET /api/v1/search?category=3&min_price=50.00&max_price=100.00&min_rating=4.5&availability=true`
* **Response (`200 OK`)**:
  ```json
  {
    "products": [
      {
        "id": 2045,
        "name": "Ergonomic Gaming Mouse",
        "description": "High precision 26K DPI optical gaming mouse with customizable RGB.",
        "price": 79.99,
        "category_id": 3,
        "brand_id": 7,
        "rating": 4.9,
        "stock_quantity": 250,
        "is_available": true
      }
    ],
    "total": 1,
    "page": 1,
    "size": 20,
    "total_pages": 1
  }
  ```

---

### 5. Sorting Products
* **Request**: `GET /api/v1/search?category=3&sort=price_asc&page=1&size=2`
* **Response (`200 OK`)**:
  ```json
  {
    "products": [
      {
        "id": 1102,
        "name": "Standard Office Mouse",
        "price": 19.99,
        "category_id": 3,
        "brand_id": 2,
        "rating": 4.2,
        "stock_quantity": 500,
        "is_available": true
      },
      {
        "id": 2045,
        "name": "Ergonomic Gaming Mouse",
        "price": 79.99,
        "category_id": 3,
        "brand_id": 7,
        "rating": 4.9,
        "stock_quantity": 250,
        "is_available": true
      }
    ],
    "total": 14,
    "page": 1,
    "size": 2,
    "total_pages": 7
  }
  ```

---

### 6. Getting Recommendations
* **Request**: `GET /api/v1/recommendations/45`
* **Response (`200 OK`)**:
  ```json
  {
    "user_id": 45,
    "recommendations": [
      {
        "id": 2045,
        "name": "Ergonomic Gaming Mouse",
        "price": 79.99,
        "category_id": 3,
        "brand_id": 7,
        "rating": 4.9,
        "reason": "Based on your recent interest in PC peripherals"
      }
    ]
  }
  ```

---

### 7. Product Not Found Error
* **Request**: `GET /api/v1/products/999999`
* **Response (`404 Not Found`)**:
  ```json
  {
    "error": {
      "code": "PRODUCT_NOT_FOUND",
      "message": "Product with ID 999999 was not found.",
      "request_id": "req-e3f4a5b6-7c8d-9e0f-1a2b-3c4d5e6f7a8b"
    }
  }
  ```
