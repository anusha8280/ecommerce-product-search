from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ErrorResponse, ErrorDetail
from app.services.product_service import product_service

router = APIRouter(prefix="/api/v1/products", tags=["Products"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(product_in: ProductCreate, db: Session = Depends(get_db)):
    """
    Create a new product record in PostgreSQL and publish a PRODUCT_CREATED event to Kafka.
    """
    try:
        product = product_service.create_product(db, product_in)
        return product
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BAD_REQUEST", "message": str(e)}
        )


@router.get("/{id}", response_model=ProductResponse)
def get_product(id: int, db: Session = Depends(get_db)):
    """
    Retrieve product details by unique product ID.
    """
    product = product_service.get_product(db, id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PRODUCT_NOT_FOUND", "message": f"Product with ID {id} was not found."}
        )
    return product


@router.put("/{id}", response_model=ProductResponse)
def update_product(id: int, product_in: ProductUpdate, db: Session = Depends(get_db)):
    """
    Update an existing product in PostgreSQL and publish a PRODUCT_UPDATED event to Kafka.
    """
    updated_product = product_service.update_product(db, id, product_in)
    if not updated_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PRODUCT_NOT_FOUND", "message": f"Product with ID {id} was not found."}
        )
    return updated_product


@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_product(id: int, db: Session = Depends(get_db)):
    """
    Delete a product from PostgreSQL and publish a PRODUCT_DELETED event to Kafka.
    """
    success = product_service.delete_product(db, id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PRODUCT_NOT_FOUND", "message": f"Product with ID {id} was not found."}
        )
    return {"message": f"Product {id} successfully deleted."}
