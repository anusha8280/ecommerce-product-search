from typing import Optional, Dict, Any, List
from opensearchpy import OpenSearch
from app.config import settings


class OpenSearchClientWrapper:
    def __init__(self):
        self.client: Optional[OpenSearch] = None
        self.index_name = settings.OPENSEARCH_INDEX_PRODUCTS
        self._available: Optional[bool] = None  # None=untried, False=known unavailable

    def connect(self):
        try:
            self.client = OpenSearch(
                hosts=[{"host": settings.OPENSEARCH_HOST, "port": settings.OPENSEARCH_PORT}],
                http_compress=True,
                use_ssl=False,
                verify_certs=False,
                timeout=3
            )
            self._available = True
            print(f"[OpenSearch] Connected to {settings.OPENSEARCH_HOST}:{settings.OPENSEARCH_PORT}")
            self.ensure_index_exists()
        except Exception as e:
            self._available = False
            print(f"[Warning] OpenSearch connection failed ({settings.OPENSEARCH_HOST}:{settings.OPENSEARCH_PORT}): {e}")
            self.client = None

    def ensure_index_exists(self):
        if not self.client:
            return
        try:
            if not self.client.indices.exists(index=self.index_name):
                mapping = {
                    "mappings": {
                        "properties": {
                            "id": {"type": "long"},
                            "name": {"type": "text", "analyzer": "standard"},
                            "description": {"type": "text"},
                            "price": {"type": "double"},
                            "category_id": {"type": "long"},
                            "brand_id": {"type": "long"},
                            "rating": {"type": "double"},
                            "stock_quantity": {"type": "integer"},
                            "is_available": {"type": "boolean"},
                            "created_at": {"type": "date"}
                        }
                    }
                }
                self.client.indices.create(index=self.index_name, body=mapping)
                print(f"[OpenSearch] Index '{self.index_name}' created successfully.")
        except Exception as e:
            print(f"[Warning] OpenSearch ensure_index_exists error: {e}")

    def search_products(
        self,
        q: Optional[str] = None,
        category: Optional[int] = None,
        brand: Optional[int] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        availability: Optional[bool] = None,
        sort: Optional[str] = "relevance",
        page: int = 1,
        size: int = 20
    ) -> Dict[str, Any]:
        if not self.client:
            self.connect()
        if not self.client:
            return {"products": [], "total": 0, "page": page, "size": size, "total_pages": 0}

        must_clause: List[Dict[str, Any]] = []
        filter_clause: List[Dict[str, Any]] = []

        if q:
            must_clause.append({
                "multi_match": {
                    "query": q,
                    "fields": ["name^3", "description"],
                    "fuzziness": "AUTO"
                }
            })
        else:
            must_clause.append({"match_all": {}})

        if category is not None:
            filter_clause.append({"term": {"category_id": category}})

        if brand is not None:
            filter_clause.append({"term": {"brand_id": brand}})

        if availability is not None:
            filter_clause.append({"term": {"is_available": availability}})

        price_range: Dict[str, Any] = {}
        if min_price is not None:
            price_range["gte"] = min_price
        if max_price is not None:
            price_range["lte"] = max_price
        if price_range:
            filter_clause.append({"range": {"price": price_range}})

        if min_rating is not None:
            filter_clause.append({"range": {"rating": {"gte": min_rating}}})

        sort_clause: List[Dict[str, Any]] = []
        if sort == "price_asc":
            sort_clause.append({"price": {"order": "asc"}})
        elif sort == "price_desc":
            sort_clause.append({"price": {"order": "desc"}})
        elif sort == "rating":
            sort_clause.append({"rating": {"order": "desc"}})
        elif sort == "newest":
            sort_clause.append({"created_at": {"order": "desc"}})
        else:
            sort_clause.append({"_score": {"order": "desc"}})

        from_idx = (page - 1) * size

        body = {
            "query": {
                "bool": {
                    "must": must_clause,
                    "filter": filter_clause
                }
            },
            "sort": sort_clause,
            "from": from_idx,
            "size": size
        }

        try:
            res = self.client.search(index=self.index_name, body=body)
            hits = res["hits"]["hits"]
            total = res["hits"]["total"]["value"]
            products = [hit["_source"] for hit in hits]
            total_pages = (total + size - 1) // size if size > 0 else 1

            return {
                "products": products,
                "total": total,
                "page": page,
                "size": size,
                "total_pages": total_pages
            }
        except Exception as e:
            print(f"[Warning] OpenSearch search query failed: {e}")
            return {"products": [], "total": 0, "page": page, "size": size, "total_pages": 0}

    def index_product(self, product_data: Dict[str, Any]) -> bool:
        if not self.client:
            self.connect()
        if not self.client:
            return False
        try:
            doc_id = str(product_data["id"])
            self.client.index(index=self.index_name, id=doc_id, body=product_data, refresh=True)
            return True
        except Exception as e:
            print(f"[Warning] OpenSearch index_product failed for ID {product_data.get('id')}: {e}")
            return False

    def delete_product(self, product_id: int) -> bool:
        if not self.client:
            self.connect()
        if not self.client:
            return False
        try:
            self.client.delete(index=self.index_name, id=str(product_id), refresh=True)
            return True
        except Exception as e:
            print(f"[Warning] OpenSearch delete_product failed for ID {product_id}: {e}")
            return False

    def is_healthy(self) -> bool:
        if self._available is False:
            return False
        if not self.client and self._available is None:
            self.connect()
        if not self.client:
            return False
        try:
            return bool(self.client.ping())
        except Exception:
            self._available = False
            return False


opensearch_client = OpenSearchClientWrapper()
