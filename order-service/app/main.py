from fastapi import FastAPI
from .routers import order_router, health_router

app = FastAPI(title="Order Service")

app.include_router(order_router)
app.include_router(health_router)
