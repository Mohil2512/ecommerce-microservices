import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

PRODUCT_PAYLOAD = {
    "name": "Test Widget",
    "description": "A widget for testing",
    "price": 9.99,
    "stock": 100
}


def _get_token():
    """Create a fake JWT using the same secret as the service."""
    from jose import jwt
    return jwt.encode({"sub": "admin@example.com"}, "supersecretkey", algorithm="HS256")


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_list_products_empty():
    resp = client.get("/api/products/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_product_requires_auth():
    resp = client.post("/api/products/", json=PRODUCT_PAYLOAD)
    assert resp.status_code == 401


def test_create_and_get_product():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post("/api/products/", json=PRODUCT_PAYLOAD, headers=headers)
    assert create.status_code == 201
    prod_id = create.json()["id"]

    get = client.get(f"/api/products/{prod_id}")
    assert get.status_code == 200
    assert get.json()["name"] == "Test Widget"


def test_update_product():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post("/api/products/", json=PRODUCT_PAYLOAD, headers=headers)
    prod_id = create.json()["id"]

    updated = {**PRODUCT_PAYLOAD, "stock": 50}
    resp = client.put(f"/api/products/{prod_id}", json=updated, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["stock"] == 50


def test_delete_product():
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post("/api/products/", json=PRODUCT_PAYLOAD, headers=headers)
    prod_id = create.json()["id"]

    resp = client.delete(f"/api/products/{prod_id}", headers=headers)
    assert resp.status_code == 204


def test_consume_order_created_reduces_stock():
    from app.routers.product import handle_order_created
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post("/api/products/", json={**PRODUCT_PAYLOAD, "stock": 10}, headers=headers)
    assert create.status_code == 201
    prod_id = create.json()["id"]

    handle_order_created({"order_id": 1, "items": [{"product_id": prod_id, "quantity": 3}]})

    get = client.get(f"/api/products/{prod_id}")
    assert get.status_code == 200
    assert get.json()["stock"] == 7

