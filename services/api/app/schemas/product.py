from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ProductAttributeSchema(BaseModel):
    attribute_name: str
    attribute_value: str

    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    name: str = Field(..., example="Wireless Headphones")
    description: Optional[str] = Field(None, example="High quality wireless noise cancelling headphones.")
    price: float = Field(..., gt=0, example=199.99)
    category_id: Optional[int] = Field(None, example=1)
    brand_id: Optional[int] = Field(None, example=1)
    stock_quantity: int = Field(0, ge=0, example=100)
    is_available: bool = Field(True, example=True)
    attributes: Optional[List[ProductAttributeSchema]] = Field(default=[], example=[{"attribute_name": "Color", "attribute_value": "Black"}])


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    rating: Optional[float] = Field(None, ge=0, le=5)
    stock_quantity: Optional[int] = Field(None, ge=0)
    is_available: Optional[bool] = None
    attributes: Optional[List[ProductAttributeSchema]] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    rating: float = 0.0
    stock_quantity: int = 0
    is_available: bool = True
    attributes: List[ProductAttributeSchema] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SearchProductItem(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    rating: float = 0.0
    stock_quantity: int = 0
    is_available: bool = True

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    products: List[SearchProductItem]
    total: int
    page: int
    size: int
    total_pages: int


class RecommendationItem(BaseModel):
    id: int
    name: str
    price: float
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    rating: float = 0.0
    reason: str


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: List[RecommendationItem]


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
