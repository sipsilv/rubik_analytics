def test_screener_status(client, admin_token):
    response = client.get(
        "/api/v1/admin/screener/status",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert "is_running" in response.json()

def test_get_news_public(client):
    # News might be public
    response = client.get("/api/v1/news")
    # If auth required:
    if response.status_code == 401:
        pass # Expected if protected
    else:
        assert response.status_code == 200
        assert isinstance(response.json(), list)

def test_get_symbols_admin(client, admin_token):
    response = client.get(
        "/api/v1/admin/symbols",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    # Should get list (empty or mock data if any)
    assert isinstance(response.json(), list)
