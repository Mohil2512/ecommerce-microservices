from fastapi import FastAPI
import asyncio
from .routers import product_router, health_router
from .routers.product import consume_order_created

app = FastAPI(title="Product Service")

app.include_router(product_router)
app.include_router(health_router)


@app.on_event("startup")
async def startup_event():
    # Start RabbitMQ consumer in background
    asyncio.create_task(consume_order_created())
