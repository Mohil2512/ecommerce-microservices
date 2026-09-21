import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app

client = TestClient(app)


def _get_token():
    from jose import jwt
    return jwt.encode({"sub": "user@example.com"}, "supersecretkey", algorithm="HS256")


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_list_orders_empty():
    token = _get_token()
    resp = client.get("/api/orders/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_order_product_not_found():
    """If product-service returns 404, order creation should fail with 404."""
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        resp = client.post("/api/orders/", json={"items": [{"product_id": 999, "quantity": 1}]}, headers=headers)
        assert resp.status_code == 404


def test_create_order_insufficient_stock():
    """If stock < quantity, order should fail with 400."""
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 1, "name": "Widget", "stock": 2, "price": 5.0, "description": ""}
        mock_get.return_value = mock_resp

        resp = client.post("/api/orders/", json={"items": [{"product_id": 1, "quantity": 10}]}, headers=headers)
        assert resp.status_code == 400


def test_create_order_success():
    """Happy path: product exists, stock OK, order is created."""
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("app.routers.order.publish_order_created", new_callable=AsyncMock):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 1, "name": "Widget", "stock": 50, "price": 5.0, "description": ""}
        mock_get.return_value = mock_resp

        resp = client.post("/api/orders/", json={"items": [{"product_id": 1, "quantity": 2}]}, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["user_email"] == "user@example.com"

