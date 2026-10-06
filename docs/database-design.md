# Database Design Document

## 1. Overview

This document outlines the database design for the **E-Commerce Product Search System**. PostgreSQL serves as the primary, authoritative relational database (source of truth) for all system entities including users, products, categories, brands, product attributes, and user activity tracking.

---

## 2. Database Schema

### 2.1 `users`
Stores user profile information.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `BIGSERIAL` | `PRIMARY KEY` | Unique identifier for the user |
| `name` | `VARCHAR(100)` | | User's full name |
| `email` | `VARCHAR(255)` | `UNIQUE`, `NOT NULL` | User's unique email address |
| `created_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Account creation timestamp |

### 2.2 `categories`
Organizes products into hierarchical or flat catalog categories.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `BIGSERIAL` | `PRIMARY KEY` | Unique category identifier |
| `name` | `VARCHAR(100)` | `UNIQUE`, `NOT NULL` | Category name |
| `description` | `TEXT` | | Detailed category description |
| `created_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Category creation timestamp |

### 2.3 `brands`
Stores manufacturer or brand information.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `BIGSERIAL` | `PRIMARY KEY` | Unique brand identifier |
| `name` | `VARCHAR(100)` | `UNIQUE`, `NOT NULL` | Brand name |
| `description` | `TEXT` | | Detailed brand description |

### 2.4 `products`
Core table containing authoritative product metadata and inventory states.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `BIGSERIAL` | `PRIMARY KEY` | Unique product identifier |
| `name` | `VARCHAR(255)` | `NOT NULL` | Product display name |
| `description` | `TEXT` | | Full product description |
| `price` | `DECIMAL(12,2)` | `NOT NULL` | Unit price |
| `category_id` | `BIGINT` | `REFERENCES categories(id)` | Foreign key to `categories` |
| `brand_id` | `BIGINT` | `REFERENCES brands(id)` | Foreign key to `brands` |
| `rating` | `DECIMAL(2,1)` | | Average customer rating (0.0 - 5.0) |
| `stock_quantity` | `INTEGER` | `NOT NULL` | Current available inventory count |
| `is_available` | `BOOLEAN` | `DEFAULT TRUE` | Availability flag |
| `created_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Record creation timestamp |
| `updated_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Record last updated timestamp |

### 2.5 `product_attributes`
Dynamic key-value pairs representing category-specific or variable product properties (e.g., Size, Color, Weight, Material).

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `BIGSERIAL` | `PRIMARY KEY` | Attribute entry identifier |
| `product_id` | `BIGINT` | `REFERENCES products(id)` | Foreign key linking to parent product |
| `attribute_name` | `VARCHAR(100)` | `NOT NULL` | Property key (e.g., "Color") |
| `attribute_value` | `VARCHAR(255)` | `NOT NULL` | Property value (e.g., "Red") |

### 2.6 `user_activities`
Captures user interaction history for rule-based recommendation logic and analytics.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `BIGSERIAL` | `PRIMARY KEY` | Activity event identifier |
| `user_id` | `BIGINT` | `REFERENCES users(id)` | Foreign key linking to user |
| `product_id` | `BIGINT` | `REFERENCES products(id)` | Foreign key linking to product |
| `activity_type` | `VARCHAR(50)` | `NOT NULL` | Activity action (e.g., `SEARCH`, `VIEW`, `PURCHASE`) |
| `created_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Event timestamp |

---

## 3. Entity Relationships

```text
  +------------------+         1:N         +------------------+
  |    categories    | ------------------->|     products     |
  +------------------+                     +------------------+
                                                    ^
  +------------------+         1:N                  |
  |      brands      | -----------------------------+
  +------------------+                              |
                                                    | 1:N
  +------------------+         1:N                  v
  |    products      | ------------------->+------------------+
  +------------------+                     |product_attributes|
                                           +------------------+
  +------------------+         1:N
  |      users       | ------------------->+------------------+
  +------------------+                     | user_activities  |
                                           +------------------+
  +------------------+         1:N                  ^
  |    products      | -----------------------------+
  +------------------+
```

### Relationship Breakdown
* **Category (1) : Product (N)** — A single category contains multiple products; each product belongs to one primary category.
* **Brand (1) : Product (N)** — A single brand manufactures multiple products; each product is associated with one brand.
* **Product (1) : ProductAttribute (N)** — A product can have multiple dynamic attributes (e.g., size, color, RAM, storage); each attribute entry belongs to a single product.
* **User (1) : UserActivity (N)** — A user generates multiple activity records over time; each activity belongs to one user.
* **Product (1) : UserActivity (N)** — A product can be targeted in multiple user activities; each activity records an interaction with one product.

### Primary & Foreign Keys Explanation
* **Primary Key (PK)**: A unique column (`id`) assigned to every record in each table to uniquely identify rows and enforce entity integrity.
* **Foreign Key (FK)**: Referential constraints (`category_id`, `brand_id`, `product_id`, `user_id`) linking child rows to parent rows. FKs guarantee referential integrity by preventing orphaned records when parents are deleted or updated.

---

## 4. Role of PostgreSQL as the Source of Truth

PostgreSQL serves as the **single source of truth (SoT)** in this system for the following critical reasons:

1. **ACID Transactions**: Guarantees Atomicity, Consistency, Isolation, and Durability during data mutations (e.g., inventory updates, price revisions).
2. **Data Integrity & Schema Enforcement**: Enforces data types, uniqueness (`email`, category/brand names), non-null constraints, and foreign key relationships at the storage layer.
3. **Auditability & Persistence**: Provides durable disk persistence and reliable transaction logs (Write-Ahead Logging) for reliable data restoration and audit tracking.
4. **Authoritative Master Copy**: All catalog updates originate in PostgreSQL first. External engines (OpenSearch, Redis) consume state changes asynchronously via Kafka events published after PostgreSQL commits.

---

## 5. Dual-Database Strategy: PostgreSQL vs. OpenSearch

| Architectural Aspect | PostgreSQL (Source of Truth) | OpenSearch (Search Engine) |
| :--- | :--- | :--- |
| **Primary Purpose** | Transactional CRUD, data persistence, schema enforcement | Full-text search, fuzzy matching, filtering, facet aggregation |
| **Data Structure** | Normalized relational tables | Inverted index & JSON document store |
| **Consistency Model** | Immediate / Strong Consistency (ACID) | Eventual Consistency (via Kafka sync stream) |
| **Query Performance** | Fast for PK lookup; slow for multi-attribute pattern matching | Sub-second full-text queries over millions of products |
| **Write Pattern** | Direct transactional writes from Product Service | Asynchronous bulk indexing from Search Indexer |

### Why OpenSearch is Required
Querying millions of products with keyword matches, multi-category filters, range filtering (price, rating), and dynamic sorting directly against PostgreSQL requires expensive table scans or massive composite indexes. OpenSearch utilizes inverted indexes optimized for multi-dimensional filtering, keyword tokenization, and high-concurrency read traffic.

---

## 6. Data Usage Analysis

### 6.1 Fields Used for Search & Filtering
The following fields are synchronized to OpenSearch to drive product discovery:

* **Full-Text Keyword Search**: `products.name`, `products.description`, `brands.name`, `categories.name`.
* **Filtering Dimensions**:
  * `category_id` (Category filter)
  * `brand_id` (Brand filter)
  * `price` (Price range filter)
  * `rating` (Minimum rating filter)
  * `is_available` (In-stock / availability filter)
  * `product_attributes.attribute_name` & `product_attributes.attribute_value` (Facet filtering e.g., Color=Red)
* **Sorting Dimensions**:
  * `price` (Low to High / High to Low)
  * `rating` (Rating High to Low)
  * `created_at` (Newest arrivals)

### 6.2 Data Used by Recommendation Service
The initial rule-based Recommendation Service utilizes:

* `user_activities.user_id`, `user_activities.product_id`, `user_activities.activity_type`: Analyzes user browsing and search history (e.g., `VIEW`, `SEARCH`).
* `products.category_id` & `products.brand_id`: Identifies frequently browsed or purchased categories and brands per user.
* `products.rating` & `products.is_available`: Filters recommendations to top-rated, available products within preferred categories.

---

## 7. PostgreSQL Indexing Strategy

To support fast lookups, join performance, and efficient event indexing:

1. **Foreign Key Indexes**:
   * `CREATE INDEX idx_products_category_id ON products(category_id);`
   * `CREATE INDEX idx_products_brand_id ON products(brand_id);`
   * `CREATE INDEX idx_product_attributes_product_id ON product_attributes(product_id);`
   * `CREATE INDEX idx_user_activities_user_id ON user_activities(user_id);`
   * `CREATE INDEX idx_user_activities_product_id ON user_activities(product_id);`

2. **Temporal & Activity Indexes**:
   * `CREATE INDEX idx_products_updated_at ON products(updated_at);` — Assists out-of-sync recovery jobs querying recently modified records.
   * `CREATE INDEX idx_user_activities_user_activity ON user_activities(user_id, activity_type, created_at DESC);` — Optimized for fetching recent user interaction patterns.

---

## 8. Data Integrity & Constraints

* **Entity Uniqueness**:
  * `users(email)` must be unique.
  * `categories(name)` and `brands(name)` must be unique.
* **Non-Null Guarantees**:
  * Mandatory fields (`name`, `price`, `stock_quantity`, `activity_type`) enforce non-null values.
* **Range & Logical Validation**:
  * `price` >= 0.00
  * `stock_quantity` >= 0
  * `rating` BETWEEN 0.0 AND 5.0
* **Referential Integrity**:
  * Foreign key constraints (`ON DELETE RESTRICT` or `ON DELETE CASCADE` where applicable) prevent orphaned data across products, attributes, categories, brands, and activities.
