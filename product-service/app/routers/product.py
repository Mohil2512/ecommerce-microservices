from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict
import json
import asyncio
import aio_pika
from .. import security
from ..config import RABBITMQ_URL

router = APIRouter(prefix="/api/products", tags=["products"])

# In-memory product store
_fake_products: Dict[int, dict] = {}
_next_id: int = 1


class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    stock: int


class Product(BaseModel):
    id: int
    name: str
    description: str
    price: float
    stock: int


def get_current_user(token: str = Depends(security.oauth2_scheme)):
    payload = security.decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload.get("sub")


@router.get("/", response_model=List[Product])
async def list_products():
    return list(_fake_products.values())


@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: int):
    prod = _fake_products.get(product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    return prod


@router.post("/", response_model=Product, status_code=status.HTTP_201_CREATED)
async def create_product(prod: ProductCreate, user=Depends(get_current_user)):
    global _next_id
    product = {"id": _next_id, **prod.dict()}
    _fake_products[_next_id] = product
    _next_id += 1
    return product


@router.put("/{product_id}", response_model=Product)
async def update_product(product_id: int, prod: ProductCreate, user=Depends(get_current_user)):
    if product_id not in _fake_products:
        raise HTTPException(status_code=404, detail="Product not found")
    updated = {"id": product_id, **prod.dict()}
    _fake_products[product_id] = updated
    return updated


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, user=Depends(get_current_user)):
    if product_id not in _fake_products:
        raise HTTPException(status_code=404, detail="Product not found")
    del _fake_products[product_id]


# ---------------------------------------------------------------------------
# RabbitMQ consumer – reduces stock when order.created is received
# ---------------------------------------------------------------------------

def handle_order_created(data: dict):
    """Reduce stock for each item in an order.created event."""
    for item in data.get("items", []):
        pid = item["product_id"]
        qty = item["quantity"]
        if pid in _fake_products:
            _fake_products[pid]["stock"] = max(0, _fake_products[pid]["stock"] - qty)


async def consume_order_created():
    """Background task: listen to order.created queue and reduce stock."""
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue("order.created", durable=True)

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        data = json.loads(message.body)
                        handle_order_created(data)
    except Exception as e:
        print(f"[product-service] RabbitMQ consumer error: {e}")
