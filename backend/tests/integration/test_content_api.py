def test_get_announcements(client, admin_token):
    # Public or Protected? usually public or authenticated. 
    # Try public first
    response = client.get("/api/v1/announcements")
    if response.status_code == 401:
         response = client.get("/api/v1/announcements", headers={"Authorization": f"Bearer {admin_token}"})
    
    assert response.status_code == 200
    # Should return list/paginated
    data = response.json()
    assert "items" in data or isinstance(data, list)

def test_get_news(client):
    response = client.get("/api/v1/news")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list) or "items" in data

def test_telegram_channel_list(client, admin_token):
    response = client.get("/api/v1/telegram/channels", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
