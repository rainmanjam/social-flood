"""
Migration Example: Converting from APIRouter to BaseRouter

This file demonstrates how to migrate an existing API module from using FastAPI's
APIRouter to the new BaseRouter class. It shows both the original and migrated code
with explanations of the changes.

This is for demonstration purposes only and is not meant to be imported or used directly.
"""

# =============================================================================
# ORIGINAL VERSION USING FASTAPI'S APIROUTER
# =============================================================================

"""
# Original version using FastAPI's APIRouter

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from pydantic import BaseModel

from app.core.auth import get_api_key

# Define models
class Product(BaseModel):
    id: int
    name: str
    price: float
    in_stock: bool

class ProductCreate(BaseModel):
    name: str
    price: float
    in_stock: bool = True

# Create router
products_router = APIRouter()

# Define routes
@products_router.get("/products/", response_model=List[Product])
async def list_products(
    in_stock: Optional[bool] = Query(None, description="Filter by stock status")
):
    products = [
        {"id": 1, "name": "Product 1", "price": 19.99, "in_stock": True},
        {"id": 2, "name": "Product 2", "price": 29.99, "in_stock": False}
    ]
    
    if in_stock is not None:
        products = [p for p in products if p["in_stock"] == in_stock]
        
    return products

@products_router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: int):
    products = {
        1: {"id": 1, "name": "Product 1", "price": 19.99, "in_stock": True},
        2: {"id": 2, "name": "Product 2", "price": 29.99, "in_stock": False}
    }
    
    if product_id not in products:
        raise HTTPException(
            status_code=404,
            detail=f"Product with ID {product_id} not found"
        )
        
    return products[product_id]

@products_router.post("/products/", response_model=Product, status_code=201)
async def create_product(product: ProductCreate):
    if product.price <= 0:
        raise HTTPException(
            status_code=400,
            detail="Price must be greater than zero"
        )
        
    new_product = {
        "id": 3,
        **product.dict()
    }
    
    return new_product

# In main.py
# app.include_router(
#     products_router,
#     prefix="/store",
#     tags=["Store"],
#     dependencies=[Depends(get_api_key)]
# )
"""

# =============================================================================
# MIGRATED VERSION USING BASEROUTER
# =============================================================================

"""
# Migrated version using BaseRouter

from fastapi import Query
from typing import List, Optional
from pydantic import BaseModel

from app.core.base_router import BaseRouter

# Define models
class Product(BaseModel):
    id: int
    name: str
    price: float
    in_stock: bool

class ProductCreate(BaseModel):
    name: str
    price: float
    in_stock: bool = True

# Create router with prefix and auto-derived service_name
products_router = BaseRouter(
    prefix="/store",
    # service_name is automatically derived as "store"
    responses={
        # Custom response for 400 errors
        400: {
            "description": "Invalid product data",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://socialflood.com/problems/validation_error",
                        "title": "Invalid Product Data",
                        "status": 400,
                        "detail": "The provided product data is invalid"
                    }
                }
            }
        }
    }
)

# Define routes - note that the prefix is now part of the router, not in include_router
@products_router.get("/products/", response_model=List[Product])
async def list_products(
    in_stock: Optional[bool] = Query(None, description="Filter by stock status")
):
    products = [
        {"id": 1, "name": "Product 1", "price": 19.99, "in_stock": True},
        {"id": 2, "name": "Product 2", "price": 29.99, "in_stock": False}
    ]
    
    if in_stock is not None:
        products = [p for p in products if p["in_stock"] == in_stock]
        
    return products

@products_router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: int):
    products = {
        1: {"id": 1, "name": "Product 1", "price": 19.99, "in_stock": True},
        2: {"id": 2, "name": "Product 2", "price": 29.99, "in_stock": False}
    }
    
    if product_id not in products:
        # Use the standardized error handling method
        products_router.raise_not_found_error("Product", product_id)
        
    return products[product_id]

@products_router.post("/products/", response_model=Product, status_code=201)
async def create_product(product: ProductCreate):
    if product.price <= 0:
        # Use the standardized error handling method with field information
        products_router.raise_validation_error(
            "Price must be greater than zero",
            field="price"
        )
        
    new_product = {
        "id": 3,
        **product.dict()
    }
    
    return new_product

# In main.py - much simpler now
# app.include_router(products_router())
"""

# =============================================================================
# KEY DIFFERENCES AND BENEFITS
# =============================================================================

"""
Key Differences and Benefits:

1. Router Creation:
   - Before: Created with APIRouter() and configured in include_router()
   - After: Created with BaseRouter(prefix="/store") with configuration at creation time

2. Error Handling:
   - Before: Used HTTPException directly with status_code and detail
   - After: Used specialized methods like raise_not_found_error() and raise_validation_error()
   - Benefit: Standardized RFC7807 error responses with proper Content-Type headers

3. Authentication:
   - Before: Added via dependencies=[Depends(get_api_key)] in include_router()
   - After: Automatically applied by BaseRouter to all routes
   - Benefit: Cannot forget to add authentication to a router

4. OpenAPI Documentation:
   - Before: Limited response documentation
   - After: Comprehensive response schemas for all status codes
   - Benefit: Better API documentation and client code generation

5. Service Name:
   - Before: Manually specified as tags=["Store"] in include_router()
   - After: Automatically derived from prefix or explicitly provided
   - Benefit: Consistent naming and grouping in API documentation

6. App Integration:
   - Before: app.include_router(router, prefix="/store", tags=["Store"], dependencies=[...])
   - After: app.include_router(router())
   - Benefit: Simpler integration with less duplication

7. Error Response Format:
   - Before: Simple string detail
   - After: Structured RFC7807 Problem Details format
   - Benefit: More information for API clients to handle errors properly
"""
