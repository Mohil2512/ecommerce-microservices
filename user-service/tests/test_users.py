import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register():
    resp = client.post("/api/users/register", json={
        "email": "test@example.com",
        "password": "secret123",
        "full_name": "Test User"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


def test_register_duplicate():
    client.post("/api/users/register", json={"email": "dup@example.com", "password": "pass"})
    resp = client.post("/api/users/register", json={"email": "dup@example.com", "password": "pass"})
    assert resp.status_code == 400


def test_login_and_me():
    client.post("/api/users/register", json={"email": "login@example.com", "password": "mypass"})
    resp = client.post("/api/users/login", data={"username": "login@example.com", "password": "mypass"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "login@example.com"


def test_login_wrong_password():
    client.post("/api/users/register", json={"email": "bad@example.com", "password": "rightpass"})
    resp = client.post("/api/users/login", data={"username": "bad@example.com", "password": "wrongpass"})
    assert resp.status_code == 400

