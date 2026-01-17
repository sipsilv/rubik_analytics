def test_login_success(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": "user@example.com", "password": "user123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["username"] == "user"

def test_login_failure(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": "user@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401

def test_get_current_user(client, user_token):
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
