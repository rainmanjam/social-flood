"""
Simple test script for the BaseRouter class.
"""
from fastapi import FastAPI
from app.core.base_router import BaseRouter

# Create a FastAPI app
app = FastAPI()

# Create a router with auto-derived service_name
router1 = BaseRouter(prefix="/google-ads")
print(f"Router 1 service_name: {router1.service_name}")

# Create a router with explicit service_name
router2 = BaseRouter(prefix="/google-ads", service_name="google-ads-service")
print(f"Router 2 service_name: {router2.service_name}")

# Create a router with API versioned prefix
router3 = BaseRouter(prefix="/api/v1/google-ads")
print(f"Router 3 service_name: {router3.service_name}")

# Create a router with custom responses
custom_responses = {
    200: {"description": "Success"},
    400: {"description": "Bad Request"}
}
router4 = BaseRouter(prefix="/google-ads", responses=custom_responses)
print(f"Router 4 responses: {router4.router.responses}")

# Include the routers in the app
app.include_router(router1())
app.include_router(router2())
app.include_router(router3())
app.include_router(router4())

print("All routers included successfully!")
