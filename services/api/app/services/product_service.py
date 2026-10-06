from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.models.product import Product, ProductAttribute
from app.schemas.product import ProductCreate, ProductUpdate
from app.infrastructure.kafka_producer import kafka_producer
from app.infrastructure.opensearch_client import opensearch_client
from app.infrastructure.redis_client import redis_client


class ProductService:
    def get_product(self, db: Session, product_id: int) -> Optional[Product]:
        return db.query(Product).filter(Product.id == product_id).first()

    def create_product(self, db: Session, product_in: ProductCreate) -> Product:
        db_product = Product(
            name=product_in.name,
            description=product_in.description,
            price=product_in.price,
            category_id=product_in.category_id,
            brand_id=product_in.brand_id,
            stock_quantity=product_in.stock_quantity,
            is_available=product_in.is_available,
            rating=0.0
        )
        db.add(db_product)
        db.commit()
        db.refresh(db_product)

        if product_in.attributes:
            for attr in product_in.attributes:
                db_attr = ProductAttribute(
                    product_id=db_product.id,
                    attribute_name=attr.attribute_name,
                    attribute_value=attr.attribute_value
                )
                db.add(db_attr)
            db.commit()
            db.refresh(db_product)

        product_dict = self._product_to_dict(db_product)

        # 1. Directly index in OpenSearch for prototype synchronization
        opensearch_client.index_product(product_dict)

        # 2. Publish PRODUCT_CREATED event to Kafka
        kafka_producer.publish_product_event("PRODUCT_CREATED", db_product.id, extra_data=product_dict)

        return db_product

    def update_product(self, db: Session, product_id: int, product_in: ProductUpdate) -> Optional[Product]:
        db_product = self.get_product(db, product_id)
        if not db_product:
            return None

        update_data = product_in.model_dump(exclude_unset=True)
        attributes_data = update_data.pop("attributes", None)

        for field, value in update_data.items():
            setattr(db_product, field, value)

        if attributes_data is not None:
            db.query(ProductAttribute).filter(ProductAttribute.product_id == product_id).delete()
            for attr in attributes_data:
                db_attr = ProductAttribute(
                    product_id=product_id,
                    attribute_name=attr["attribute_name"],
                    attribute_value=attr["attribute_value"]
                )
                db.add(db_attr)

        db.commit()
        db.refresh(db_product)

        product_dict = self._product_to_dict(db_product)

        # 1. Update OpenSearch document
        opensearch_client.index_product(product_dict)

        # 2. Publish PRODUCT_UPDATED event to Kafka
        kafka_producer.publish_product_event("PRODUCT_UPDATED", product_id, extra_data=product_dict)

        return db_product

    def delete_product(self, db: Session, product_id: int) -> bool:
        db_product = self.get_product(db, product_id)
        if not db_product:
            return False

        db.delete(db_product)
        db.commit()

        # 1. Remove document from OpenSearch
        opensearch_client.delete_product(product_id)

        # 2. Publish PRODUCT_DELETED event to Kafka
        kafka_producer.publish_product_event("PRODUCT_DELETED", product_id)

        return True

    def _product_to_dict(self, product: Product) -> Dict[str, Any]:
        return {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": float(product.price) if product.price is not None else 0.0,
            "category_id": product.category_id,
            "brand_id": product.brand_id,
            "rating": float(product.rating) if product.rating is not None else 0.0,
            "stock_quantity": product.stock_quantity,
            "is_available": product.is_available,
            "created_at": product.created_at.isoformat() if product.created_at else None
        }


product_service = ProductService()
