import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app("testing")
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_login_rate_limit(client):
    for i in range(10):
        client.post("/auth/login", json={"username": "test", "password": "test"})

    response = client.post("/auth/login", json={"username": "test", "password": "test"})
    assert response.status_code == 429

def test_register_rate_limit(client):
    for i in range(5):
        client.post("/auth/register", json={
            "username": f"user{i}", "email": f"user{i}@test.com", "password": "test"
        })

    response = client.post("/auth/register", json={
        "username": "overflow", "email": "overflow@test.com", "password": "test"
    })
    assert response.status_code == 429
