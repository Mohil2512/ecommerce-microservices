from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict
import json
import aio_pika
from .. import security
from ..config import PRODUCT_SERVICE_URL, RABBITMQ_URL
import httpx

router = APIRouter(prefix="/api/orders", tags=["orders"])

# In-memory order store
_fake_orders: Dict[int, dict] = {}
_next_id: int = 1


class OrderItem(BaseModel):
    product_id: int
    quantity: int


class OrderCreate(BaseModel):
    items: List[OrderItem]


class OrderOut(BaseModel):
    id: int
    user_email: str
    items: List[OrderItem]


def get_current_user(token: str = Depends(security.oauth2_scheme)):
    payload = security.decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload.get("sub")


async def publish_order_created(order_id: int, items: List[OrderItem]):
    """Publish order.created event to RabbitMQ."""
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue("order.created", durable=True)
            message = aio_pika.Message(
                body=json.dumps({
                    "order_id": order_id,
                    "items": [i.dict() for i in items],
                }).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await channel.default_exchange.publish(message, routing_key="order.created")
    except Exception as e:
        # Log but don't fail the request if RabbitMQ is unavailable
        print(f"[order-service] RabbitMQ publish failed: {e}")


@router.post("/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(order: OrderCreate, user_email: str = Depends(get_current_user)):
    global _next_id
    # Check stock for each item via product-service
    async with httpx.AsyncClient() as client:
        for item in order.items:
            resp = await client.get(f"{PRODUCT_SERVICE_URL}/api/products/{item.product_id}")
            if resp.status_code != 200:
                raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
            prod = resp.json()
            if prod["stock"] < item.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for product {item.product_id}")

    # Save order
    new_order = {"id": _next_id, "user_email": user_email, "items": [i.dict() for i in order.items]}
    _fake_orders[_next_id] = new_order
    _next_id += 1

    # Publish event to RabbitMQ (non-blocking, best-effort)
    await publish_order_created(new_order["id"], order.items)

    return OrderOut(**new_order)


@router.get("/", response_model=List[OrderOut])
async def list_orders(user_email: str = Depends(get_current_user)):
    return [OrderOut(**o) for o in _fake_orders.values() if o["user_email"] == user_email]
