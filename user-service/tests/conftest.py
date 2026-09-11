import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.routers.user import _fake_users

client = TestClient(app)


def get_token():
    """Helper: register + login, return token."""
    client.post("/api/users/register", json={"email": "prod_tester@example.com", "password": "pass123"})
    r = client.post("/api/users/login", data={"username": "prod_tester@example.com", "password": "pass123"})
    return r.json()["access_token"]

